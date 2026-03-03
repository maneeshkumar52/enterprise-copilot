"""SharePoint document connector (mock implementation for local dev)."""
import structlog
from typing import List, Dict

logger = structlog.get_logger(__name__)

MOCK_SHAREPOINT_DOCS = [
    {"title": "IT Security Policy 2024", "content": "All employees must use MFA for all corporate systems. VPN is required for remote access. Password requirements: 12+ characters, complexity enabled, 90-day rotation.", "source": "SharePoint", "category": "IT Policy"},
    {"title": "Employee Handbook v5.2", "content": "Welcome to Contoso. This handbook covers company culture, benefits, code of conduct, performance management, and career development frameworks.", "source": "SharePoint", "category": "HR"},
    {"title": "Procurement Guidelines", "content": "Purchases over £1,000 require manager approval. Over £10,000 require Director approval. All contracts over £50,000 must go through Legal review.", "source": "SharePoint", "category": "Finance"},
    {"title": "Azure Cloud Architecture Standards", "content": "All new services must deploy to Azure. Use Azure Container Apps for microservices. Enable Azure Monitor and Application Insights on all production workloads.", "source": "SharePoint", "category": "Engineering"},
]


class SharePointConnector:
    """Syncs documents from SharePoint to Azure AI Search."""

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id

    async def get_documents(self) -> List[Dict]:
        """Fetch documents from SharePoint (mock returns static data)."""
        logger.info("sharepoint_sync", tenant=self.tenant_id, count=len(MOCK_SHAREPOINT_DOCS))
        return [dict(doc, tenant_id=self.tenant_id) for doc in MOCK_SHAREPOINT_DOCS]
