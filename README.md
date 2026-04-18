<div align="center">

# Enterprise Knowledge Copilot

### Multi-Tenant AI Assistant with Tenant-Isolated Search, Per-User Memory, and Personalised Generation

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Azure OpenAI](https://img.shields.io/badge/Azure_OpenAI-GPT--4o-0078D4?logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
[![Azure AI Search](https://img.shields.io/badge/Azure_AI_Search-11.4-0078D4?logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/en-us/products/ai-services/ai-search)
[![Azure Cosmos DB](https://img.shields.io/badge/Cosmos_DB-4.7-0078D4?logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/en-us/products/cosmos-db)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*An enterprise-grade multi-tenant knowledge assistant that ingests documents from Confluence and SharePoint, performs hybrid vector + semantic + keyword search with mandatory tenant isolation, maintains per-user conversation memory with topic frequency tracking in Cosmos DB, and generates personalised responses by dynamically tailoring system prompts to each user's department, role, and frequently asked topics — with full graceful degradation when any Azure service is unavailable.*

[Architecture](#architecture) · [Quick Start](#quick-start) · [API Reference](#api-reference) · [Authentication](#authentication) · [Memory System](#memory-system) · [Deployment](#deployment)

</div>

---

## Why This Exists

Enterprise organisations need AI assistants that respect tenant boundaries, remember user context across sessions, and draw answers from internal knowledge sources — not public internet data. Most RAG implementations are single-tenant, stateless, and return the same generic answer regardless of who is asking.

This system solves three enterprise-specific problems simultaneously:

- **Tenant isolation at every layer** — search queries always include `tenant_id eq '{id}'` as an OData filter, memory uses composite keys `{tenant_id}::{user_id}`, and Cosmos DB partitions by tenant. Cross-tenant data leakage is architecturally impossible.
- **Per-user memory with topic tracking** — the system remembers each user's last 10 queries and tracks topic frequencies (stop-words removed, top 3 topics surfaced). A user who frequently asks about "cloud migration" gets cloud-contextualised responses automatically.
- **Multi-source knowledge ingestion** — documents from Confluence wikis and SharePoint sites are embedded with `text-embedding-3-large` (3072 dimensions) and indexed in Azure AI Search with hybrid retrieval (BM25 keyword + HNSW vector + semantic ranking).

---

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE KNOWLEDGE SOURCES                     │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │   Confluence      │  │   SharePoint      │  │  Direct Upload   │  │
│  │  (Wiki pages)     │  │  (Policies/Docs)  │  │  (Documents)     │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  │
│           │                     │                      │            │
│           ▼                     ▼                      ▼            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  indexer/index_documents.py                                  │   │
│  │  Embed (text-embedding-3-large, 3072d) → Index (AI Search)  │   │
│  │  Fields: id, title, content, source, tenant_id, category,   │   │
│  │          content_vector (3072-dim HNSW)                      │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
└─────────────────────────────────┼───────────────────────────────────┘
                                  │
                                  ▼
              ┌───────────────────────────────────────┐
              │    Azure AI Search                     │
              │    Index: "enterprise-knowledge"       │
              │    Hybrid: BM25 + HNSW + Semantic      │
              │    Tenant-partitioned via OData filter  │
              └───────────────────┬───────────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI Service (:8000)                           │
│                                                                     │
│  ┌─────────────┐   ┌──────────────────────┐   ┌─────────────────┐  │
│  │  auth.py     │──►│  JWT Token Decode     │──►│ TenantUser-     │  │
│  │  (HS256)     │   │  + MOCK_USERS lookup  │   │ Context         │  │
│  └──────┬──────┘   └──────────────────────┘   └────────┬────────┘  │
│         │                                               │           │
│         ▼                                               ▼           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  POST /api/v1/query                                          │   │
│  │                                                              │   │
│  │  1. Authenticate user (JWT → TenantUserContext)              │   │
│  │  2. Load conversation memory (memory.py → Cosmos DB)         │   │
│  │  3. Tenant-scoped search (tenant_retriever.py → AI Search)   │   │
│  │  4. Memory-augmented generation (generator.py → GPT-4o)      │   │
│  │  5. Persist query to memory (memory.py → Cosmos DB)          │   │
│  │  6. Return CopilotResponse                                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  GET /api/v1/memory/{user_id}  (own-only enforced, 403)      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  GET /health  (liveness probe)                                │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────┬───────────────────────┘
                           │                  │
                           ▼                  ▼
              ┌─────────────────┐  ┌─────────────────────┐
              │  Azure Cosmos DB │  │  Azure OpenAI        │
              │  DB: enterprise- │  │  gpt-4o (chat)       │
              │      copilot     │  │  text-embedding-     │
              │  Container:      │  │  3-large (embeddings)│
              │  user-memory     │  │                      │
              │  PK: tenant_id   │  │                      │
              └─────────────────┘  └─────────────────────┘
```

### Query Processing Flow

```
User Request                                       Response
    │                                                  ▲
    ▼                                                  │
┌─────────┐    ┌───────────┐    ┌──────────┐    ┌────────────┐
│  JWT     │───►│  Memory   │───►│  Search  │───►│ Generator  │
│  Auth    │    │  Load     │    │ (tenant  │    │ (GPT-4o    │
│          │    │ (Cosmos)  │    │  scoped) │    │  + memory) │
└─────────┘    └───────────┘    └──────────┘    └────────────┘
                                                       │
                                                       ▼
                                                ┌────────────┐
                                                │  Memory    │
                                                │  Update    │
                                                │ (Cosmos)   │
                                                └────────────┘
```

### Why Not a Generic RAG Chatbot?

| Dimension | Generic RAG/Chatbot | Enterprise Copilot |
|-----------|---------------------|--------------------|
| **Multi-tenancy** | Single tenant or no concept | Strict `tenant_id` filter on every search + Cosmos partition key |
| **Authentication** | None or simple API key | JWT + Azure Entra tenant validation with role/department |
| **Memory** | Stateless or simple session | Persistent per-user memory with topic frequency tracking (Cosmos DB) |
| **Personalisation** | Same prompt for everyone | System prompt dynamically tailored to user's name, department, role, top topics |
| **Knowledge sources** | Single document store | Multi-source ingestion (Confluence + SharePoint) with source attribution |
| **Search** | Simple vector similarity | Hybrid: BM25 keyword + HNSW vector (3072d) + Azure semantic ranking |
| **Confidence scoring** | None | Document-count based: High (≥3 docs), Medium (1-2), Low (0) |
| **Authorization** | All users see everything | Users can only view their own memory (HTTP 403 on cross-user access) |
| **Degradation** | Crashes without services | Full graceful degradation — works with zero Azure services |
| **Data isolation** | All users see all data | Architecturally impossible to return cross-tenant documents |

---

## Design Decisions

### Why Hybrid Search (BM25 + Vector + Semantic)?

```python
# tenant_retriever.py — Triple-layer search
results = await self._search_client.search(
    search_text=query,                     # BM25 keyword matching
    query_type="semantic",                 # Azure semantic re-ranking
    semantic_configuration_name="default",
    vector_queries=[VectorizedQuery(       # HNSW vector similarity
        vector=embedding,                  # 3072-dim from text-embedding-3-large
        k_nearest_neighbors=top_k,
        fields="content_vector"
    )],
    filter=f"tenant_id eq '{user.tenant_id}'"  # MANDATORY tenant isolation
)
```

| Search Type | Strengths | Weaknesses | Used Here |
|-------------|-----------|------------|-----------|
| Keyword (BM25) | Exact terms, acronyms, policy numbers | Misses synonyms | ✅ `search_text` |
| Vector (HNSW) | Semantic similarity, paraphrases | May miss exact terms | ✅ `vector_queries` |
| Semantic ranking | Contextual re-ranking of results | Requires both above | ✅ `query_type="semantic"` |
| **Combined** ✅ | All strengths, compensates all weaknesses | Slightly higher latency | ✅ |

### Why Composite Memory Keys (`tenant_id::user_id`)?

```python
def _memory_key(self, user_id: str, tenant_id: str) -> str:
    return f"{tenant_id}::{user_id}"
```

| Approach | Cross-Tenant Risk | Example |
|----------|-------------------|---------|
| `user_id` only | **HIGH** — `"alice"` in Tenant A reads `"alice"` in Tenant B | ❌ |
| `{tenant_id}::{user_id}` ✅ | **ZERO** — keys are unique per tenant | ✅ `"tenant-contoso::user-t1-001"` |

The in-process `MEMORY_STORE` dict uses this composite key, and Cosmos DB adds a second layer of isolation via `partition_key=tenant_id`.

### Why Topic Frequency Tracking Instead of Raw History?

```python
# memory.py — Topic extraction on each query
words = query.lower().split()
stop_words = {"what", "how", "is", "the", "a", "an", "does", "do", "in", "for"}
meaningful = [w for w in words if len(w) > 3 and w not in stop_words]
for word in meaningful[:3]:
    memory.topic_frequencies[word] = memory.topic_frequencies.get(word, 0) + 1
```

| Approach | Storage Cost | Personalisation Quality | Privacy |
|----------|-------------|------------------------|---------|
| Full conversation history | High | Highest | Lowest — stores all questions |
| **Topic frequencies** ✅ | Low (~20 words) | High — captures interests | Higher — only word counts |
| No memory | Zero | None | Highest |

The generator uses top 3 topics to personalise: *"This user frequently asks about: cloud, migration, access. Tailor your response to their role and interests."*

### Why Graceful Degradation Everywhere?

```python
# tenant_retriever.py — Search client may not initialize
try:
    self._search_client = SearchClient(...)
    self._search_available = True
except Exception:
    self._search_available = False  # Falls back to empty results

# memory.py — Cosmos may not be available
try:
    container.upsert_item(doc)
except Exception:
    logger.error("memory_cosmos_failed")  # In-process store continues working

# generator.py — LLM may fail
except Exception:
    return ("I'm unable to answer right now.", "Low", False)  # Graceful fallback
```

| Component | Unavailable Behavior | System Continues? |
|-----------|---------------------|-------------------|
| Azure AI Search | Returns empty document list | ✅ (generates from memory context) |
| Azure Cosmos DB | Uses in-process `MEMORY_STORE` dict | ✅ (full memory features, no persistence) |
| Azure OpenAI | Returns fallback message with Low confidence | ✅ (user gets informative error) |
| All three | Returns fallback answer, in-process memory, no docs | ✅ (fully operational) |

---

## Data Contracts

### 5 Pydantic v2 Models

```python
# ── Authentication Context ────────────────────────────────────────────
class TenantUserContext(BaseModel):
    user_id: str                    # "user-t1-001"
    tenant_id: str                  # "tenant-contoso"
    name: str                       # "Alice Johnson"
    email: str                      # "alice@contoso.com"
    roles: List[str] = []           # ["employee"] or ["manager"]
    department: str = ""            # "Engineering"

# ── Retrieved Document ────────────────────────────────────────────────
class KnowledgeDocument(BaseModel):
    title: str                      # "IT Security Policy 2024"
    content_snippet: str            # First 300 chars of matched content
    source: str                     # "SharePoint" | "Confluence"
    relevance_score: float          # Azure AI Search @search.score
    tenant_id: str                  # Document's owning tenant

# ── Per-User Memory ──────────────────────────────────────────────────
class UserMemory(BaseModel):
    user_id: str                            # "user-t1-001"
    tenant_id: str                          # "tenant-contoso"
    recent_queries: List[str] = []          # Last 10 queries (200 chars max each)
    topic_frequencies: Dict[str, int] = {}  # {"cloud": 5, "migration": 3}
    role: str = ""                          # User's role
    preferences: Dict[str, str] = {}        # User preferences
    last_updated: datetime = datetime.utcnow()

# ── Request ──────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str                           # min_length=5
    session_id: Optional[str] = uuid4()     # Auto-generated if not provided

# ── Response ─────────────────────────────────────────────────────────
class CopilotResponse(BaseModel):
    answer: str                     # Generated answer text
    sources: List[str]              # Source document titles
    confidence: str                 # "High" | "Medium" | "Low"
    personalised: bool = False      # Whether memory was used for personalisation
    query_id: str = uuid4()         # Unique query identifier
```

### Search Index Schema

| Field | Type | Properties | Description |
|-------|------|------------|-------------|
| `id` | String | Key | Document UUID |
| `title` | String | Searchable | Document title |
| `content` | String | Searchable | Full document text |
| `source` | String | Filterable | "SharePoint" or "Confluence" |
| `tenant_id` | String | Filterable | Owning tenant ID |
| `category` | String | Filterable | Document category |
| `content_vector` | Collection(Single) | Searchable, HNSW | 3072-dimensional embedding |

### Example API Exchange

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJ..." \
  -d '{"question": "What is our VPN policy for remote workers?"}'
```

**Response:**
```json
{
  "answer": "According to the IT Security Policy 2024, all employees must use VPN for remote access. Password requirements include 12+ characters with complexity enabled and 90-day rotation. MFA is required for all corporate systems.",
  "sources": ["IT Security Policy 2024"],
  "confidence": "High",
  "personalised": true,
  "query_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

---

## Features

| # | Feature | Description | Implementation |
|---|---------|-------------|----------------|
| 1 | **Multi-Tenant Isolation** | Every search query and memory operation filtered by tenant_id | OData filter + Cosmos partition key |
| 2 | **JWT Authentication** | HS256 JWT with Azure Entra tenant ID validation | `auth.py` |
| 3 | **Hybrid Search** | BM25 keyword + HNSW vector + semantic ranking | `tenant_retriever.py` |
| 4 | **3072-Dim Embeddings** | text-embedding-3-large for document and query vectors | OpenAI SDK |
| 5 | **Per-User Memory** | Persistent conversation history (last 10 queries) in Cosmos DB | `memory.py` |
| 6 | **Topic Frequency Tracking** | Extracts meaningful words, builds frequency map, surfaces top 3 | `UserMemoryManager.update_memory()` |
| 7 | **Dynamic Prompt Personalisation** | System prompt tailored to user's name, department, role, topics | `generator.py` |
| 8 | **Confidence Scoring** | High (≥3 docs), Medium (1-2 docs), Low (0 docs) | `MemoryAugmentedGenerator.generate()` |
| 9 | **Own-Only Memory Access** | HTTP 403 if user tries to read another user's memory | `GET /memory/{user_id}` |
| 10 | **Multi-Source Ingestion** | Confluence wiki + SharePoint policies indexed together | `indexer/` module |
| 11 | **Source Attribution** | Each response lists which documents were used | `sources` field in response |
| 12 | **Graceful Degradation** | Works without any Azure service via in-process fallbacks | All modules |
| 13 | **In-Process Memory Fallback** | `MEMORY_STORE` dict when Cosmos DB unavailable | `memory.py` |
| 14 | **Embedding-Optional Search** | Falls back to semantic text search if embedding fails | `tenant_retriever.py` |
| 15 | **Structured JSON Logging** | structlog with ISO timestamps, event names, context fields | `main.py` |
| 16 | **Settings Singleton** | `@lru_cache` pydantic-settings configuration | `config.py` |
| 17 | **CORS Middleware** | Cross-origin support for frontend integration | `CORSMiddleware` |
| 18 | **Health Endpoint** | Liveness probe for container orchestrators | `GET /health` |
| 19 | **Company Name Extraction** | Derives company name from tenant_id ("tenant-contoso" → "Contoso") | `generator.py` |
| 20 | **Mock Users** | 3 pre-defined test users across 2 tenants | `auth.py` |
| 21 | **Query Truncation** | Stored queries capped at 200 chars each | `memory.py` |
| 22 | **Stop Word Filtering** | Topic extraction removes 10 common words | `memory.py` |
| 23 | **6 Test Cases** | Memory CRUD, tenant isolation, JWT round-trip | `tests/test_memory.py` |
| 24 | **E2E Demo Script** | Full pipeline without FastAPI server | `demo_e2e.py` |
| 25 | **Docker Deployment** | Container-ready with deployment script | `infra/` |
| 26 | **Pydantic v2 Models** | 5 typed data contracts with validation | `models.py` |
| 27 | **Async Throughout** | All I/O operations use async/await | All modules |
| 28 | **Content Snippet Truncation** | Search results truncated to 300 chars for prompt efficiency | `tenant_retriever.py` |

---

## Authentication

### JWT-Based Multi-Tenant Auth

```
Authorization: Bearer <JWT>
         │
         ▼
┌─────────────────────────────────┐
│  JWT Payload                     │
│  {                               │
│    "sub": "user-t1-001",         │  ←── user_id
│    "tid": "tenant-contoso",      │  ←── tenant_id
│    "name": "Alice Johnson",      │  ←── display name
│    "email": "alice@contoso.com", │  ←── email
│    "roles": ["employee"],        │  ←── roles
│    "department": "Engineering"   │  ←── department
│  }                               │
└─────────────────────────────────┘
         │
         ▼
  TenantUserContext (Pydantic model)
```

### Mock Users (Development)

| User ID | Tenant | Name | Department | Roles |
|---------|--------|------|------------|-------|
| `user-t1-001` | `tenant-contoso` | Alice Johnson | Engineering | employee |
| `user-t1-002` | `tenant-contoso` | Bob Smith | Finance | manager |
| `user-t2-001` | `tenant-fabrikam` | Carol Lee | HR | employee |

### Authentication Fallback

When no `Authorization` header is provided, the system falls back to `MOCK_USERS["user-t1-001"]` (Alice Johnson) with a warning log. This enables zero-config development and testing.

```bash
# No auth header — falls back to Alice Johnson (tenant-contoso)
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is our VPN policy?"}'

# With explicit JWT
TOKEN=$(python -c "from src.auth import create_test_token; print(create_test_token('user-t1-002'))")
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question": "What are our procurement guidelines?"}'
```

---

## Memory System

### How Memory Personalisation Works

```
Query 1: "How do I set up cloud access?"
  → topic_frequencies: {"cloud": 1, "access": 1}

Query 2: "What is our cloud migration policy?"
  → topic_frequencies: {"cloud": 2, "migration": 1, "access": 1}

Query 3: "Cloud infrastructure standards?"
  → topic_frequencies: {"cloud": 3, "infrastructure": 1, "migration": 1, "access": 1}

                          ↓

System Prompt (on next query):
"You are an intelligent enterprise knowledge copilot for Contoso.
 Answer questions based on the provided knowledge base documents.
 Be concise, helpful, and cite your sources.
 If information is not in the provided documents, say so clearly.

 User context: Alice Johnson (Engineering, employee)
 This user frequently asks about: cloud, migration, infrastructure.
 Tailor your response to their role and interests."
```

### Memory Storage Architecture

```
┌─────────────────────────────────────┐
│  In-Process MEMORY_STORE (dict)      │  ← Fast cache (always available)
│  Key: "tenant-contoso::user-t1-001"  │
│  Value: UserMemory object            │
└────────────────┬────────────────────┘
                 │ sync on read/write
                 ▼
┌─────────────────────────────────────┐
│  Azure Cosmos DB                     │  ← Persistent storage (optional)
│  Database: enterprise-copilot        │
│  Container: user-memory              │
│  Partition Key: tenant_id            │
│  Item ID: user_id                    │
└─────────────────────────────────────┘
```

### Memory Constraints

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `MAX_QUERIES` | 10 | Caps recent query history |
| Query truncation | 200 chars | Prevents oversized memory entries |
| Stop words | 10 words (`what`, `how`, `is`, `the`, `a`, `an`, `does`, `do`, `in`, `for`) | Filters noise from topic extraction |
| Meaningful word length | >3 chars | Skips short words |
| Topics per query | Top 3 | Limits frequency map growth |

---

## Knowledge Sources

### Mock Document Library

#### SharePoint Documents (4)

| # | Title | Category | Content |
|---|-------|----------|---------|
| 1 | IT Security Policy 2024 | IT Policy | MFA for all corporate systems, VPN required for remote access, 12+ char passwords, 90-day rotation |
| 2 | Employee Handbook v5.2 | HR | Company culture, benefits, code of conduct, performance management, career development |
| 3 | Procurement Guidelines | Finance | £1,000 → manager approval, £10,000 → Director, £50,000 → Legal review |
| 4 | Azure Cloud Architecture Standards | Engineering | All new services on Azure, Container Apps for microservices, Monitor + App Insights required |

#### Confluence Pages (3)

| # | Title | Category | Content |
|---|-------|----------|---------|
| 1 | Engineering Onboarding Guide | Engineering | 5-step setup: IT portal laptop → GitHub access → clone repo → setup script → #engineering Slack |
| 2 | Incident Response Runbook | Operations | P1: page on-call immediately, SLA: 15 min acknowledge / 4 hour resolve, post-incident review in 48h |
| 3 | API Design Standards | Engineering | REST for external APIs, `/v1/` versioning, JSON error format, rate limit public endpoints |

### Indexing Pipeline

```bash
# Index documents for a tenant
python indexer/index_documents.py
```

The indexer:
1. Creates the Azure AI Search index with HNSW vector profile and semantic configuration
2. Fetches documents from both connectors (SharePoint + Confluence)
3. Embeds first 500 chars of each document via `text-embedding-3-large`
4. Uploads batch to Azure AI Search with `tenant_id` field

---

## Prerequisites

<details>
<summary><strong>macOS</strong></summary>

```bash
# Python 3.11+
brew install python@3.11

# Verify
python3.11 --version
# Python 3.11.x
```

</details>

<details>
<summary><strong>Windows</strong></summary>

```powershell
# Python 3.11+
winget install Python.Python.3.11

# Verify
python --version
# Python 3.11.x
```

</details>

<details>
<summary><strong>Linux (Ubuntu/Debian)</strong></summary>

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip

python3.11 --version
# Python 3.11.x
```

</details>

### Required Services

| Service | Required | Purpose | Free Tier |
|---------|----------|---------|-----------|
| **Azure OpenAI** | No (graceful fallback) | GPT-4o for generation, text-embedding-3-large for vectors | Pay-per-token |
| **Azure AI Search** | No (returns empty results) | Hybrid vector + semantic + keyword search | Free tier (3 indexes) |
| **Azure Cosmos DB** | No (in-process fallback) | Persistent per-user memory storage | 1000 RU/s free |
| **Azure Entra ID** | No (mock users) | JWT tenant validation | Free |

---

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/maneeshkumar52/enterprise-copilot.git
cd enterprise-copilot
```

**Expected output:**
```
Cloning into 'enterprise-copilot'...
remote: Enumerating objects: 42, done.
Receiving objects: 100% (42/42), done.
```

### 2. Create Virtual Environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Expected output:**
```
Collecting fastapi==0.111.0
Collecting uvicorn==0.30.0
Collecting openai==1.40.0
Collecting azure-search-documents==11.4.0
Collecting azure-cosmos==4.7.0
Collecting pydantic==2.7.0
Collecting pydantic-settings==2.3.0
Collecting structlog==24.2.0
Collecting python-jose[cryptography]==3.3.0
Successfully installed fastapi-0.111.0 uvicorn-0.30.0 ...
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your Azure credentials (or leave defaults for local development with fallbacks):

```env
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_API_KEY=your-search-key
AZURE_SEARCH_INDEX_NAME=enterprise-knowledge
COSMOS_ENDPOINT=https://your-cosmos.documents.azure.com:443/
COSMOS_KEY=your-cosmos-key
COSMOS_DATABASE=enterprise-copilot
COSMOS_MEMORY_CONTAINER=user-memory
ENTRA_TENANT_ID=your-entra-tenant-id
JWT_SECRET=dev-secret-change-in-production
LOG_LEVEL=INFO
```

### 5. Start the Server

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

**Expected output:**
```
{"event": "enterprise_copilot_starting", "level": "info", "timestamp": "2024-11-15T14:00:00Z"}
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345]
```

### 6. Health Check

```bash
curl http://localhost:8000/health
```

**Expected output:**
```json
{"status": "healthy", "service": "enterprise-copilot", "version": "1.0.0"}
```

### 7. Query the Copilot

```bash
# Default user (Alice Johnson, tenant-contoso)
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is our VPN policy for remote workers?"}'
```

**Expected output:**
```json
{
  "answer": "According to the IT Security Policy 2024, all employees must use VPN for remote access...",
  "sources": ["IT Security Policy 2024"],
  "confidence": "High",
  "personalised": false,
  "query_id": "a1b2c3d4-..."
}
```

### 8. Query with Different User

```bash
# Generate JWT for Bob Smith (Finance, tenant-contoso)
TOKEN=$(python -c "from src.auth import create_test_token; print(create_test_token('user-t1-002'))")

curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question": "What are procurement approval thresholds?"}'
```

### 9. Check User Memory

```bash
curl http://localhost:8000/api/v1/memory/user-t1-001
```

**Expected output:**
```json
{
  "user_id": "user-t1-001",
  "tenant_id": "tenant-contoso",
  "memory": {
    "user_id": "user-t1-001",
    "tenant_id": "tenant-contoso",
    "recent_queries": ["What is our VPN policy for remote workers?"],
    "topic_frequencies": {"policy": 1, "remote": 1, "workers": 1},
    "last_updated": "2024-11-15T14:05:00Z"
  }
}
```

### 10. Run E2E Demo (No Server Required)

```bash
python demo_e2e.py
```

Runs 4 standalone tests: memory CRUD, tenant isolation, JWT token round-trip, and connector data fetch.

---

## Project Structure

```
enterprise-copilot/
├── .env.example                          # 15 environment variables template
├── demo_e2e.py                           # E2E demo (4 tests, no server needed)
├── requirements.txt                      # 14 Python dependencies
│
├── src/                                  # Core application
│   ├── __init__.py
│   ├── main.py                           # FastAPI app, 3 endpoints, lifespan
│   ├── config.py                         # Settings singleton (pydantic-settings)
│   ├── models.py                         # 5 Pydantic v2 data models
│   ├── auth.py                           # JWT auth + 3 mock users
│   ├── tenant_retriever.py               # Tenant-isolated hybrid search
│   ├── memory.py                         # Per-user memory (Cosmos + in-process)
│   └── generator.py                      # Memory-augmented LLM generation
│
├── indexer/                              # Document ingestion
│   ├── index_documents.py                # Embedding + indexing pipeline
│   ├── sharepoint_connector.py           # 4 mock SharePoint documents
│   └── confluence_connector.py           # 3 mock Confluence pages
│
├── tests/                                # Test suite
│   ├── __init__.py
│   └── test_memory.py                    # 6 async test cases
│
└── infra/                                # Deployment
    ├── Dockerfile                        # Python 3.11-slim container
    └── azure-deploy.sh                   # Azure Container Apps deployment
```

### Module Responsibility Matrix

| Module | Lines | Responsibility | Key Exports |
|--------|-------|---------------|-------------|
| `src/main.py` | 78 | FastAPI app, 3 endpoints, structured logging, lifespan init | `app` |
| `src/config.py` | 28 | Configuration from env + `.env` file | `Settings`, `get_settings()` |
| `src/models.py` | 39 | 5 typed data contracts | All model classes |
| `src/auth.py` | 51 | JWT decode, mock users, token creation | `get_current_user()`, `create_test_token()` |
| `src/tenant_retriever.py` | 78 | Tenant-scoped hybrid search with graceful degradation | `TenantIsolatedRetriever` |
| `src/memory.py` | 100 | Per-user memory CRUD with Cosmos DB + in-process fallback | `UserMemoryManager` |
| `src/generator.py` | 55 | Dynamic prompt building + GPT-4o generation | `MemoryAugmentedGenerator` |
| `indexer/index_documents.py` | 66 | Search index creation + document embedding + upload | `index_tenant()` |
| `indexer/sharepoint_connector.py` | 24 | 4 mock SharePoint policy documents | `SharePointConnector` |
| `indexer/confluence_connector.py` | 23 | 3 mock Confluence wiki pages | `ConfluenceConnector` |
| `tests/test_memory.py` | 70 | 6 async tests: memory, isolation, JWT | All test functions |
| `demo_e2e.py` | 71 | 4 standalone demo tests | `main()` |

---

## API Reference

### Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/query` | JWT (optional in dev) | Query the knowledge copilot |
| `GET` | `/api/v1/memory/{user_id}` | JWT (own-only enforced) | Retrieve user's conversation memory |
| `GET` | `/health` | None | Liveness probe |

### `POST /api/v1/query`

**Request:**

| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| `question` | string | Yes | — | `min_length=5` |
| `session_id` | string | No | Auto-generated UUID | — |

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | Generated answer from GPT-4o |
| `sources` | string[] | Document titles used for generation |
| `confidence` | string | `"High"` (≥3 docs), `"Medium"` (1-2), `"Low"` (0) |
| `personalised` | boolean | Whether topic-based personalisation was applied |
| `query_id` | string | Unique query identifier |

### `GET /api/v1/memory/{user_id}`

- Returns the user's `UserMemory` object (recent_queries, topic_frequencies, timestamps)
- **403 Forbidden** if `user_id` does not match the authenticated user
- Returns `"memory": null` if no memory exists for the user

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `AZURE_OPENAI_ENDPOINT` | `https://your-openai.openai.azure.com/` | Azure OpenAI endpoint |
| `AZURE_OPENAI_API_KEY` | `your-key` | Azure OpenAI API key |
| `AZURE_OPENAI_API_VERSION` | `2024-02-01` | API version |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` | Chat model deployment |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | `text-embedding-3-large` | Embedding model deployment |
| `AZURE_SEARCH_ENDPOINT` | `https://your-search.search.windows.net` | AI Search endpoint |
| `AZURE_SEARCH_API_KEY` | `your-search-key` | AI Search API key |
| `AZURE_SEARCH_INDEX_NAME` | `enterprise-knowledge` | Search index name |
| `COSMOS_ENDPOINT` | `https://your-cosmos.documents.azure.com:443/` | Cosmos DB endpoint |
| `COSMOS_KEY` | `your-cosmos-key` | Cosmos DB key |
| `COSMOS_DATABASE` | `enterprise-copilot` | Database name |
| `COSMOS_MEMORY_CONTAINER` | `user-memory` | Memory container name |
| `ENTRA_TENANT_ID` | `your-entra-tenant-id` | Azure Entra tenant ID |
| `JWT_SECRET` | `dev-secret-change-in-production` | JWT signing secret |
| `LOG_LEVEL` | `INFO` | Application log level |

---

## Testing

### Run All Tests

```bash
pytest tests/ -v
```

**Expected output:**
```
========================= test session starts =========================
platform darwin -- Python 3.11.x, pytest-8.2.0, pluggy-1.5.0
plugins: asyncio-0.23.0
asyncio: mode=auto
collected 6 items

tests/test_memory.py::test_get_context_returns_none_for_new_user  PASSED  [ 16%]
tests/test_memory.py::test_update_memory_creates_entry            PASSED  [ 33%]
tests/test_memory.py::test_memory_tracks_topic_frequency          PASSED  [ 50%]
tests/test_memory.py::test_memory_tenant_isolation                PASSED  [ 66%]
tests/test_memory.py::test_memory_keeps_last_10_queries           PASSED  [ 83%]
tests/test_memory.py::test_create_test_token                      PASSED  [100%]

========================= 6 passed in 0.45s ============================
```

### Test Coverage

| Test | What It Verifies |
|------|-----------------|
| `test_get_context_returns_none_for_new_user` | New user has no memory (`result is None`) |
| `test_update_memory_creates_entry` | First query creates memory with correct fields |
| `test_memory_tracks_topic_frequency` | Repeated topic words increase frequency counter |
| `test_memory_tenant_isolation` | Same `user_id` in different tenants → separate memory |
| `test_memory_keeps_last_10_queries` | Memory capped at 10 queries after 15 inserts |
| `test_create_test_token` | JWT creation → decode round-trip returns correct user |

---

## Deployment

### Docker

```bash
cd infra
docker build -t enterprise-copilot .
docker run -p 8000:8000 --env-file ../.env enterprise-copilot
```

### Azure Container Apps

```bash
# Deploy to Azure (from infra/)
chmod +x azure-deploy.sh
./azure-deploy.sh
```

Creates resource group `rg-enterprise-copilot` in `uksouth` and deploys to Azure Container Apps with external ingress on port 8000.

---

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|---------|
| `openai.AuthenticationError` | Invalid Azure OpenAI key | Verify `AZURE_OPENAI_API_KEY` in `.env`; system continues with fallback answer |
| `retriever_init_failed` log | Azure AI Search SDK not available | Install `aiohttp`; or system runs with empty search results |
| `memory_cosmos_failed` log | Cosmos DB unreachable | System uses in-process `MEMORY_STORE`; memory persists only during app lifetime |
| `"confidence": "Low"` | No matching documents found | Index documents first via `python indexer/index_documents.py` |
| HTTP 401 `"Invalid token"` | JWT decode failed | Generate valid token: `python -c "from src.auth import create_test_token; print(create_test_token('user-t1-001'))"` |
| HTTP 401 `"Invalid auth scheme"` | Not using "Bearer" prefix | Use `Authorization: Bearer <token>` format |
| HTTP 403 on memory endpoint | Accessing another user's memory | Users can only access their own memory |
| `ModuleNotFoundError` | Dependencies not installed | Run `pip install -r requirements.txt` |
| `Connection refused :8000` | Server not running | Run `uvicorn src.main:app --port 8000` |
| `"personalised": false` | User has no topic history yet | Query multiple times to build topic frequency map |

---

## Azure Production Mapping

| Component | Azure Service | SKU/Tier | Purpose |
|-----------|--------------|----------|---------|
| **Chat LLM** | Azure OpenAI Service | GPT-4o deployment | Memory-augmented response generation |
| **Embeddings** | Azure OpenAI Service | text-embedding-3-large | 3072-dim document + query vectors |
| **Search** | Azure AI Search | Standard S1 | Hybrid vector + semantic + keyword search |
| **Memory Store** | Azure Cosmos DB | Serverless | Per-user conversation memory (partitioned by tenant) |
| **Identity** | Azure Entra ID | — | JWT tenant validation |
| **Container Host** | Azure Container Apps | Consumption | FastAPI application hosting |
| **Secrets** | Azure Key Vault | Standard | API keys, JWT secret, connection strings |
| **Monitoring** | Azure Monitor + App Insights | — | Structured log ingestion |
| **Registry** | Azure Container Registry | Basic | Docker image storage |

### Production Checklist

- [ ] **Change `JWT_SECRET`** from `dev-secret-change-in-production` to a strong random secret
- [ ] **Restrict CORS** from `["*"]` to specific frontend domains
- [ ] **Remove auth fallback** — disable the mock user fallback when no `Authorization` header
- [ ] **Add non-root user** to Dockerfile (`USER appuser`)
- [ ] **Deploy GPT-4o** and `text-embedding-3-large` models in Azure OpenAI
- [ ] **Create AI Search** index with HNSW profile and semantic configuration
- [ ] **Create Cosmos DB** account with `enterprise-copilot` database and `user-memory` container
- [ ] **Enable Managed Identity** for passwordless auth to all Azure services
- [ ] **Index real documents** from actual Confluence and SharePoint instances
- [ ] **Add rate limiting** on `/api/v1/query` endpoint
- [ ] **Configure App Insights** for structured log ingestion and query latency tracking

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | 0.111.0 | REST API framework |
| `uvicorn` | 0.30.0 | ASGI server |
| `openai` | 1.40.0 | Azure OpenAI client (chat + embeddings) |
| `azure-search-documents` | 11.4.0 | Azure AI Search SDK |
| `azure-identity` | 1.16.0 | Azure credential management |
| `azure-cosmos` | 4.7.0 | Cosmos DB SDK |
| `pydantic` | 2.7.0 | Data validation / typed models |
| `pydantic-settings` | 2.3.0 | Settings from environment |
| `structlog` | 24.2.0 | Structured JSON logging |
| `python-jose[cryptography]` | 3.3.0 | JWT encode/decode |
| `python-dotenv` | 1.0.1 | `.env` file loading |
| `httpx` | 0.27.0 | Async HTTP client |
| `pytest` | 8.2.0 | Test framework |
| `pytest-asyncio` | 0.23.0 | Async test support |

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<div align="center">

**[⬆ Back to Top](#enterprise-knowledge-copilot)**

*Part of [Prompt to Production](https://github.com/maneeshkumar52) — Chapter 20, Project 7*

</div>