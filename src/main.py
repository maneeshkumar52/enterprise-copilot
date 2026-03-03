"""FastAPI entry point for Enterprise Knowledge Copilot."""
import logging, sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import structlog

structlog.configure(
    processors=[structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger(__name__)

from src.models import QueryRequest, CopilotResponse, TenantUserContext
from src.auth import get_current_user
from src.tenant_retriever import TenantIsolatedRetriever
from src.memory import UserMemoryManager
from src.generator import MemoryAugmentedGenerator

retriever: TenantIsolatedRetriever = None
memory_mgr: UserMemoryManager = None
generator: MemoryAugmentedGenerator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global retriever, memory_mgr, generator
    try:
        retriever = TenantIsolatedRetriever()
    except Exception as exc:
        logger.warning("retriever_init_failed", error=str(exc), fallback="mock_mode")
        retriever = None
    memory_mgr = UserMemoryManager()
    generator = MemoryAugmentedGenerator()
    logger.info("enterprise_copilot_starting")
    yield


app = FastAPI(
    title="Enterprise Knowledge Copilot",
    description="Multi-tenant enterprise AI copilot with memory — Project 7, Chapter 20, Prompt to Production",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "enterprise-copilot", "version": "1.0.0"}


@app.post("/api/v1/query", response_model=CopilotResponse)
async def query_knowledge(request: QueryRequest, user: TenantUserContext = Depends(get_current_user)) -> CopilotResponse:
    """Query enterprise knowledge base with personalised, tenant-isolated retrieval."""
    try:
        memory = await memory_mgr.get_context(user.user_id, user.tenant_id)
        docs = await retriever.search(request.question, user) if retriever else []
        answer, confidence, is_personalised = await generator.generate(request.question, docs, user, memory)
        await memory_mgr.update_memory(user.user_id, user.tenant_id, request.question, answer)
        logger.info("query_processed", user=user.user_id, tenant=user.tenant_id, confidence=confidence)
        return CopilotResponse(answer=answer, sources=[d.title for d in docs], confidence=confidence, personalised=is_personalised)
    except Exception as exc:
        logger.error("query_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/memory/{user_id}")
async def get_user_memory(user_id: str, user: TenantUserContext = Depends(get_current_user)) -> dict:
    """Retrieve memory context for a user (own memory only)."""
    if user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Cannot access another user's memory")
    memory = await memory_mgr.get_context(user.user_id, user.tenant_id)
    if not memory:
        return {"user_id": user_id, "tenant_id": user.tenant_id, "memory": None}
    return {"user_id": user_id, "tenant_id": user.tenant_id, "memory": memory.model_dump(mode="json")}
