"""Per-user memory in Cosmos DB with tenant isolation."""
import structlog
from datetime import datetime
from typing import Optional
from src.config import get_settings
from src.models import UserMemory

logger = structlog.get_logger(__name__)

MEMORY_STORE = {}  # In-process fallback when Cosmos unavailable

MAX_QUERIES = 10


class UserMemoryManager:
    """Manages per-user conversational memory with tenant isolation."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def _memory_key(self, user_id: str, tenant_id: str) -> str:
        return f"{tenant_id}::{user_id}"

    async def get_context(self, user_id: str, tenant_id: str) -> Optional[UserMemory]:
        """
        Retrieve user memory context.

        Args:
            user_id: User identifier.
            tenant_id: Tenant identifier (partition key for strict isolation).

        Returns:
            UserMemory or None if no memory exists.
        """
        key = self._memory_key(user_id, tenant_id)
        if key in MEMORY_STORE:
            return UserMemory(**MEMORY_STORE[key])

        try:
            from azure.cosmos.aio import CosmosClient
            async with CosmosClient(url=self.settings.cosmos_endpoint, credential=self.settings.cosmos_key) as client:
                db = client.get_database_client(self.settings.cosmos_database)
                container = db.get_container_client(self.settings.cosmos_memory_container)
                item = await container.read_item(item=user_id, partition_key=tenant_id)
                memory = UserMemory(**item)
                MEMORY_STORE[key] = memory.model_dump()
                logger.info("memory_loaded", user_id=user_id, tenant_id=tenant_id)
                return memory
        except Exception:
            return None

    async def update_memory(self, user_id: str, tenant_id: str, query: str, response: str) -> UserMemory:
        """
        Update user memory with a new query/response pair.

        Args:
            user_id: User identifier.
            tenant_id: Tenant identifier.
            query: User's query text.
            response: System's response text.

        Returns:
            Updated UserMemory.
        """
        existing = await self.get_context(user_id, tenant_id)
        if existing:
            memory = existing
        else:
            memory = UserMemory(user_id=user_id, tenant_id=tenant_id)

        # Update recent queries (keep last 10)
        memory.recent_queries.append(query[:200])
        if len(memory.recent_queries) > MAX_QUERIES:
            memory.recent_queries = memory.recent_queries[-MAX_QUERIES:]

        # Update topic frequency
        words = set(query.lower().split()) - {"what", "how", "is", "the", "a", "an", "does", "do", "in", "for"}
        for word in list(words)[:3]:
            if len(word) > 3:
                memory.topic_frequencies[word] = memory.topic_frequencies.get(word, 0) + 1

        memory.last_updated = datetime.utcnow()
        key = self._memory_key(user_id, tenant_id)
        MEMORY_STORE[key] = memory.model_dump(mode="json")

        # Persist to Cosmos
        try:
            from azure.cosmos.aio import CosmosClient
            async with CosmosClient(url=self.settings.cosmos_endpoint, credential=self.settings.cosmos_key) as client:
                db = client.get_database_client(self.settings.cosmos_database)
                container = db.get_container_client(self.settings.cosmos_memory_container)
                doc = memory.model_dump(mode="json")
                doc["id"] = user_id
                doc["last_updated"] = memory.last_updated.isoformat()
                await container.upsert_item(body=doc)
                logger.info("memory_updated", user_id=user_id, tenant_id=tenant_id)
        except Exception as exc:
            logger.error("memory_cosmos_failed", error=str(exc))

        return memory
