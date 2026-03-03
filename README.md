# Enterprise Knowledge Copilot

**Project 7, Chapter 20 of "Prompt to Production" by Maneesh Kumar**

A production-ready, multi-tenant enterprise AI copilot that answers questions from your company's knowledge base (SharePoint, Confluence, policy documents) with strict data isolation, per-user memory, and personalised responses.

---

## Architecture Overview

```
User Request
     │
     ▼
FastAPI (src/main.py)
     │
     ├── Auth (src/auth.py)          ← JWT validation, Entra ID, tenant extraction
     │
     ├── Memory (src/memory.py)      ← Per-user context from Cosmos DB
     │
     ├── Retriever (src/tenant_retriever.py)  ← Azure AI Search with tenant_id filter
     │
     └── Generator (src/generator.py)         ← Azure OpenAI GPT-4o with memory context
```

### Key Design Principles

1. **Multi-tenant isolation**: Every Azure AI Search query includes a mandatory `tenant_id eq '<tenant>'` filter. No cross-tenant data can ever be returned.
2. **Per-user memory**: Recent queries and topic frequencies are stored in Cosmos DB, partitioned by `tenant_id` for strict isolation. Memory personalises the system prompt for each user.
3. **Knowledge sources**: SharePoint and Confluence connectors (mock for local dev, swap for real MS Graph / Confluence API calls in production).
4. **Structured logging**: All events logged as structured JSON via `structlog` for observability.
5. **Graceful degradation**: All Azure service calls are wrapped in try/except — the system continues with reduced capability if Cosmos or Search is unavailable.

---

## Project Structure

```
enterprise-copilot/
├── src/
│   ├── __init__.py
│   ├── main.py               # FastAPI app, lifespan, API routes
│   ├── auth.py               # JWT auth + Entra ID + mock users for dev
│   ├── tenant_retriever.py   # Tenant-isolated Azure AI Search + embeddings
│   ├── memory.py             # Cosmos DB per-user memory with tenant isolation
│   ├── generator.py          # Memory-augmented GPT-4o response generation
│   ├── config.py             # Pydantic settings from environment variables
│   └── models.py             # Pydantic data models
├── indexer/
│   ├── sharepoint_connector.py   # SharePoint document connector (mock)
│   ├── confluence_connector.py   # Confluence page connector (mock)
│   └── index_documents.py        # Index pipeline: connectors → embeddings → Search
├── tests/
│   ├── __init__.py
│   └── test_memory.py        # Unit tests for memory management
├── infra/
│   ├── Dockerfile            # Container image definition
│   └── azure-deploy.sh       # Azure Container Apps deployment script
├── .env.example              # Environment variable template
├── requirements.txt          # Python dependencies
└── README.md
```

---

## Azure Services Required

| Service | Purpose |
|---|---|
| Azure OpenAI (GPT-4o) | Response generation |
| Azure OpenAI (text-embedding-3-large) | Document + query embeddings |
| Azure AI Search | Vector + semantic search with tenant filtering |
| Azure Cosmos DB | Per-user memory (partitioned by tenant_id) |
| Azure Entra ID | Production authentication (JWT fallback for dev) |
| Azure Container Apps | Hosting |

---

## Local Development Setup

### 1. Clone and install dependencies

```bash
cd enterprise-copilot
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your Azure credentials
```

### 3. Index documents (once)

```bash
python indexer/index_documents.py
```

### 4. Run the API server

```bash
uvicorn src.main:app --reload --port 8000
```

### 5. Run tests

```bash
pytest tests/ -v
```

---

## API Endpoints

### Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{"status": "healthy", "service": "enterprise-copilot", "version": "1.0.0"}
```

### Query Knowledge Base

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the IT security policy for remote access?"}'
```

With authentication (using a test token):

```python
from src.auth import create_test_token
token = create_test_token("user-t1-001")
print(token)
```

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"question": "What are the procurement approval limits?"}'
```

Response:
```json
{
  "answer": "Purchases over £1,000 require manager approval...",
  "sources": ["Procurement Guidelines", "Employee Handbook v5.2"],
  "confidence": "High",
  "personalised": true,
  "query_id": "3f4a5b6c-..."
}
```

### Get User Memory

```bash
curl http://localhost:8000/api/v1/memory/user-t1-001 \
  -H "Authorization: Bearer <token>"
```

Response:
```json
{
  "user_id": "user-t1-001",
  "tenant_id": "tenant-contoso",
  "memory": {
    "recent_queries": ["What is the IT security policy?", "..."],
    "topic_frequencies": {"security": 3, "policy": 2},
    "last_updated": "2026-02-28T10:00:00"
  }
}
```

### Interactive API Docs

Open `http://localhost:8000/docs` for the full Swagger UI.

---

## Multi-Tenant Data Isolation

The system enforces tenant isolation at every layer:

1. **Authentication**: JWT contains `tenant_id` (extracted from Entra ID `tid` claim in production).
2. **Retrieval**: Every Azure AI Search query includes `filter: "tenant_id eq '<tenant_id>'"` — impossible to retrieve another tenant's documents.
3. **Memory**: Cosmos DB uses `tenant_id` as the partition key — `read_item` always requires matching partition key.
4. **Memory key**: In-process cache uses `"<tenant_id>::<user_id>"` compound key.

```python
# From src/tenant_retriever.py — this filter is ALWAYS applied
tenant_filter = f"tenant_id eq '{user.tenant_id}'"
```

---

## Per-User Memory and Personalisation

Memory is stored in Cosmos DB per user, partitioned by tenant:

- **Recent queries**: Last 10 queries stored (rolling window)
- **Topic frequencies**: Word frequency map built from query history (stop words excluded)
- **Personalisation**: System prompt includes top 3 topics and user's department/role when memory exists

```python
# From src/generator.py — personalised system prompt
if memory and memory.topic_frequencies:
    top_topics = sorted(memory.topic_frequencies.items(), key=lambda x: x[1], reverse=True)[:3]
    prompt += f"\nThis user frequently asks about: {topics_str}."
```

---

## Indexing New Documents

To add documents from SharePoint and Confluence to the search index:

```bash
# Index for a specific tenant
python indexer/index_documents.py

# The script will:
# 1. Create/update the Azure AI Search index with vector fields
# 2. Fetch documents from SharePoint connector
# 3. Fetch pages from Confluence connector
# 4. Generate embeddings via Azure OpenAI
# 5. Upload all documents with tenant_id labels
```

To use real SharePoint data, update `indexer/sharepoint_connector.py` to call the Microsoft Graph API with the tenant's credentials. Similarly, update `indexer/confluence_connector.py` to call the Confluence REST API.

---

## Docker Deployment

```bash
# Build image
docker build -f infra/Dockerfile -t enterprise-copilot:latest .

# Run locally
docker run -p 8000:8000 --env-file .env enterprise-copilot:latest
```

---

## Azure Container Apps Deployment

```bash
# Set your Azure subscription
az login
az account set --subscription <your-subscription-id>

# Deploy
bash infra/azure-deploy.sh
```

For production, extend `infra/azure-deploy.sh` to:
- Build and push the Docker image to Azure Container Registry
- Set environment variables as Container App secrets
- Configure managed identity for keyless Azure service authentication

---

## Mock Users for Development

Three mock users are pre-configured in `src/auth.py`:

| User ID | Tenant | Name | Department | Role |
|---|---|---|---|---|
| user-t1-001 | tenant-contoso | Alice Johnson | Engineering | employee |
| user-t1-002 | tenant-contoso | Bob Smith | Finance | manager |
| user-t2-001 | tenant-fabrikam | Carol Lee | HR | employee |

Requests without an `Authorization` header default to `user-t1-001` (Alice) for easy local testing.

---

## Book Reference

This project is **Project 7** from **Chapter 20** of:

> **"Prompt to Production"** by Maneesh Kumar
>
> *Building production-grade agentic AI systems for the enterprise*

The chapter covers:
- Multi-tenant RAG architecture patterns
- Tenant isolation strategies for enterprise AI
- Per-user memory and personalisation in conversational AI
- Integrating enterprise knowledge sources (SharePoint, Confluence)
- Azure AI Search with hybrid vector + semantic search
- Production deployment on Azure Container Apps
