# Enterprise Copilot

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

Enterprise AI copilot platform with tenant-isolated retrieval, conversation memory, multi-source document indexing (Confluence, SharePoint), and JWT authentication — powered by Azure OpenAI, Azure AI Search, and Cosmos DB.

## Architecture

```
Enterprise Knowledge Sources
├── Confluence ──► confluence_connector.py
├── SharePoint ──► sharepoint_connector.py
└── Documents  ──► index_documents.py
        │
        ▼
Azure AI Search (tenant-isolated vector index)
        │
        ▼
┌───────────────────────────────────────┐
│  FastAPI Service (:8000)              │
│                                       │
│  Auth ──► JWT + Entra tenant ID      │
│       │                               │
│  TenantIsolatedRetriever ──► Search  │──► Tenant-scoped hybrid search
│       │                               │
│  UserMemoryManager ──► Cosmos DB     │──► Conversation history per user
│       │                               │
│  MemoryAugmentedGenerator ──► GPT-4o │──► Context-aware answers
└───────────────────────────────────────┘
```

## Key Features

- **Tenant Isolation** — `TenantIsolatedRetriever` enforces strict data boundaries per Entra tenant ID
- **Conversation Memory** — `UserMemoryManager` stores per-user conversation history in Cosmos DB for context continuity
- **Memory-Augmented Generation** — `MemoryAugmentedGenerator` combines retrieved documents + conversation history for contextual answers
- **Multi-Source Indexing** — Connectors for Confluence, SharePoint, and direct document upload
- **JWT + Entra Auth** — Token-based authentication with Azure Entra tenant validation
- **Hybrid Search** — Vector similarity + keyword matching via Azure AI Search

## Step-by-Step Flow

### Step 1: Knowledge Ingestion
Run connectors (`confluence_connector.py`, `sharepoint_connector.py`) or `index_documents.py` to ingest and index enterprise documents, tagged with tenant_id.

### Step 2: User Authentication
User authenticates with JWT. `get_current_user()` validates the token and extracts `TenantUserContext` (tenant_id, user_id, roles).

### Step 3: Query Submission
User sends a question via the API.

### Step 4: Tenant-Scoped Retrieval
`TenantIsolatedRetriever` searches Azure AI Search with a tenant_id filter, ensuring users only access their organization's knowledge.

### Step 5: Memory Lookup
`UserMemoryManager` fetches the user's recent conversation history from Cosmos DB.

### Step 6: Augmented Generation
`MemoryAugmentedGenerator` combines retrieved documents + conversation memory + current query, sending the full context to GPT-4o.

## Repository Structure

```
enterprise-copilot/
├── src/
│   ├── main.py              # FastAPI entry point
│   ├── tenant_retriever.py   # TenantIsolatedRetriever
│   ├── memory.py             # UserMemoryManager (Cosmos DB)
│   ├── generator.py          # MemoryAugmentedGenerator
│   ├── auth.py               # JWT + Entra authentication
│   ├── models.py             # QueryRequest, CopilotResponse, TenantUserContext
│   └── config.py             # Environment settings
├── indexer/
│   ├── index_documents.py
│   ├── confluence_connector.py
│   └── sharepoint_connector.py
├── tests/
│   └── test_memory.py
├── infra/
│   ├── Dockerfile
│   └── azure-deploy.sh
├── demo_e2e.py
├── requirements.txt
└── .env.example
```

## Quick Start

```bash
git clone https://github.com/maneeshkumar52/enterprise-copilot.git
cd enterprise-copilot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Configure Azure credentials
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

## Configuration

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment (gpt-4o) |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search endpoint |
| `AZURE_SEARCH_INDEX_NAME` | Index (enterprise-knowledge) |
| `COSMOS_ENDPOINT` | Cosmos DB for conversation memory |
| `COSMOS_MEMORY_CONTAINER` | Memory container (user-memory) |
| `ENTRA_TENANT_ID` | Azure Entra tenant ID |
| `JWT_SECRET` | JWT signing secret |

## Testing

```bash
pytest -q
python demo_e2e.py
```

## License

MIT
