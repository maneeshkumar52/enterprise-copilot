"""Confluence page connector (mock implementation)."""
import structlog
from typing import List, Dict

logger = structlog.get_logger(__name__)

MOCK_CONFLUENCE_PAGES = [
    {"title": "Engineering Onboarding Guide", "content": "Setup steps for new engineers: 1. Request laptop via IT portal 2. Set up GitHub access 3. Clone the main repo 4. Run setup script 5. Join #engineering Slack channel", "source": "Confluence", "category": "Engineering"},
    {"title": "Incident Response Runbook", "content": "P1 incidents: page on-call engineer immediately. SLA: acknowledge in 15 min, resolve in 4 hours. Post-incident review mandatory within 48 hours.", "source": "Confluence", "category": "Operations"},
    {"title": "API Design Standards", "content": "Use REST for all external APIs. Version with /v1/, /v2/ prefixes. Return errors as JSON with code, message, details fields. Rate limit all public endpoints.", "source": "Confluence", "category": "Engineering"},
]


class ConfluenceConnector:
    """Syncs pages from Confluence to Azure AI Search."""

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id

    async def get_pages(self) -> List[Dict]:
        """Fetch pages from Confluence (mock returns static data)."""
        logger.info("confluence_sync", tenant=self.tenant_id, count=len(MOCK_CONFLUENCE_PAGES))
        return [dict(page, tenant_id=self.tenant_id) for page in MOCK_CONFLUENCE_PAGES]
