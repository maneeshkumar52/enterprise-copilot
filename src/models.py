from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
import uuid

class TenantUserContext(BaseModel):
    user_id: str
    tenant_id: str
    name: str
    email: str
    roles: List[str] = Field(default_factory=list)
    department: str = ""

class KnowledgeDocument(BaseModel):
    title: str
    content_snippet: str
    source: str  # "SharePoint", "Confluence", "Policy"
    relevance_score: float
    tenant_id: str

class UserMemory(BaseModel):
    user_id: str
    tenant_id: str
    recent_queries: List[str] = Field(default_factory=list)
    topic_frequencies: Dict[str, int] = Field(default_factory=dict)
    role: str = ""
    preferences: Dict[str, str] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.utcnow)

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=5)
    session_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))

class CopilotResponse(BaseModel):
    answer: str
    sources: List[str]
    confidence: str
    personalised: bool = False
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
