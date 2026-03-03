"""Tenant-isolated Azure AI Search retrieval."""
import structlog
from typing import List
from openai import AsyncAzureOpenAI
from src.config import get_settings
from src.models import KnowledgeDocument, TenantUserContext

logger = structlog.get_logger(__name__)


class TenantIsolatedRetriever:
    """Retrieves knowledge documents with mandatory tenant_id isolation."""

    def __init__(self) -> None:
        s = get_settings()
        self.settings = s
        self.openai_client = AsyncAzureOpenAI(azure_endpoint=s.azure_openai_endpoint, api_key=s.azure_openai_api_key, api_version=s.azure_openai_api_version)
        # Lazy initialise the search client so startup doesn't fail if aiohttp is missing
        self.search_client = None
        self._search_available = False
        try:
            from azure.search.documents.aio import SearchClient
            from azure.core.credentials import AzureKeyCredential
            self.search_client = SearchClient(endpoint=s.azure_search_endpoint, index_name=s.azure_search_index_name, credential=AzureKeyCredential(s.azure_search_api_key))
            self._search_available = True
        except Exception as exc:
            logger.warning("search_client_init_failed", error=str(exc), fallback="empty_results")

    async def _embed(self, text: str) -> List[float]:
        try:
            resp = await self.openai_client.embeddings.create(input=text, model=self.settings.azure_openai_embedding_deployment)
            return resp.data[0].embedding
        except Exception as exc:
            logger.error("embed_failed", error=str(exc))
            return []

    async def search(self, query: str, user: TenantUserContext, top_k: int = 5) -> List[KnowledgeDocument]:
        """
        Search knowledge base with mandatory tenant_id filter.
        Every query MUST include tenant_id filter — no cross-tenant data leakage.
        """
        logger.info("tenant_search", tenant=user.tenant_id, query_len=len(query))
        if not self._search_available or self.search_client is None:
            logger.warning("tenant_search_unavailable", reason="search_client_not_initialised")
            return []
        try:
            embedding = await self._embed(query)
            tenant_filter = f"tenant_id eq '{user.tenant_id}'"
            kwargs = {
                "search_text": query,
                "top": top_k,
                "filter": tenant_filter,
                "select": ["title", "content", "source", "tenant_id"],
                "query_type": "semantic",
                "semantic_configuration_name": "default",
            }
            if embedding:
                try:
                    from azure.search.documents.models import VectorizedQuery
                    kwargs["vector_queries"] = [VectorizedQuery(vector=embedding, k_nearest_neighbors=top_k, fields="content_vector")]
                except Exception:
                    pass

            results = []
            async with self.search_client as client:
                async for doc in await client.search(**kwargs):
                    results.append(KnowledgeDocument(
                        title=doc.get("title", "Knowledge Article"),
                        content_snippet=doc.get("content", "")[:300],
                        source=doc.get("source", "Internal"),
                        relevance_score=doc.get("@search.score", 0.0),
                        tenant_id=doc.get("tenant_id", user.tenant_id),
                    ))
            logger.info("tenant_search_done", results=len(results))
            return results
        except Exception as exc:
            logger.error("tenant_search_failed", error=str(exc))
            return []
