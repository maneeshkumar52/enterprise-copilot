"""Memory-augmented response generation for enterprise copilot."""
import structlog
from typing import List, Tuple, Optional
from openai import AsyncAzureOpenAI
from src.config import get_settings
from src.models import KnowledgeDocument, TenantUserContext, UserMemory

logger = structlog.get_logger(__name__)

BASE_SYSTEM = """You are an intelligent enterprise knowledge copilot for {company_name}.
Answer questions based on the provided knowledge base documents.
Be concise, helpful, and cite your sources.
If information is not in the provided documents, say so clearly."""


class MemoryAugmentedGenerator:
    """Generates personalised responses using retrieved knowledge and user memory."""

    def __init__(self) -> None:
        s = get_settings()
        self.client = AsyncAzureOpenAI(azure_endpoint=s.azure_openai_endpoint, api_key=s.azure_openai_api_key, api_version=s.azure_openai_api_version, max_retries=3)
        self.settings = s

    def _build_system_prompt(self, user: TenantUserContext, memory: Optional[UserMemory]) -> str:
        """Build personalised system prompt using user memory."""
        prompt = BASE_SYSTEM.format(company_name=user.tenant_id.replace("tenant-", "").title())
        if memory and memory.topic_frequencies:
            top_topics = sorted(memory.topic_frequencies.items(), key=lambda x: x[1], reverse=True)[:3]
            topics_str = ", ".join(t for t, _ in top_topics)
            prompt += f"\n\nUser context: {user.name} ({user.department}, {user.roles[0] if user.roles else 'employee'})"
            prompt += f"\nThis user frequently asks about: {topics_str}. Tailor your response to their role and interests."
        elif user.department:
            prompt += f"\n\nUser: {user.name} from {user.department}. Tailor response to their role."
        return prompt

    async def generate(self, question: str, docs: List[KnowledgeDocument], user: TenantUserContext, memory: Optional[UserMemory]) -> Tuple[str, str, bool]:
        """Generate personalised answer from retrieved docs and user memory."""
        context = "\n".join(f"[{d.source}: {d.title}]\n{d.content_snippet}" for d in docs) or "No relevant documents found."
        system = self._build_system_prompt(user, memory)
        user_msg = f"Question: {question}\n\nKnowledge Base:\n{context}"
        is_personalised = bool(memory and memory.topic_frequencies)

        try:
            resp = await self.client.chat.completions.create(
                model=self.settings.azure_openai_deployment,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
                temperature=0.3,
                max_tokens=800,
            )
            answer = resp.choices[0].message.content or ""
            confidence = "High" if len(docs) >= 3 else "Medium" if docs else "Low"
            return answer, confidence, is_personalised
        except Exception as exc:
            logger.error("generation_failed", error=str(exc))
            return "I'm unable to answer right now. Please try again later.", "Low", False
