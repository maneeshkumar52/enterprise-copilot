"""Index documents from SharePoint and Confluence into Azure AI Search."""
import asyncio, uuid, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import get_settings
from indexer.sharepoint_connector import SharePointConnector
from indexer.confluence_connector import ConfluenceConnector


async def index_tenant(tenant_id: str) -> None:
    settings = get_settings()
    from openai import AzureOpenAI
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchIndex, SimpleField, SearchableField, SearchField,
        SearchFieldDataType, VectorSearch, HnswAlgorithmConfiguration,
        VectorSearchProfile, SemanticConfiguration, SemanticSearch,
        SemanticPrioritizedFields, SemanticField,
    )
    from azure.core.credentials import AzureKeyCredential

    cred = AzureKeyCredential(settings.azure_search_api_key)
    idx_client = SearchIndexClient(endpoint=settings.azure_search_endpoint, credential=cred)
    search_client = SearchClient(endpoint=settings.azure_search_endpoint, index_name=settings.azure_search_index_name, credential=cred)
    oai = AzureOpenAI(azure_endpoint=settings.azure_openai_endpoint, api_key=settings.azure_openai_api_key, api_version=settings.azure_openai_api_version)

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="tenant_id", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="category", type=SearchFieldDataType.String, filterable=True),
        SearchField(name="content_vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), searchable=True, vector_search_dimensions=3072, vector_search_profile_name="myHnsw"),
    ]
    vs = VectorSearch(algorithms=[HnswAlgorithmConfiguration(name="myHnsw")], profiles=[VectorSearchProfile(name="myHnsw", algorithm_configuration_name="myHnsw")])
    sc = SemanticConfiguration(name="default", prioritized_fields=SemanticPrioritizedFields(title_field=SemanticField(field_name="title"), content_fields=[SemanticField(field_name="content")]))
    idx_client.create_or_update_index(SearchIndex(name=settings.azure_search_index_name, fields=fields, vector_search=vs, semantic_search=SemanticSearch(configurations=[sc])))

    sp = SharePointConnector(tenant_id)
    cf = ConfluenceConnector(tenant_id)
    sp_docs = await sp.get_documents()
    cf_docs = await cf.get_pages()
    all_docs = sp_docs + cf_docs

    docs_to_index = []
    for doc in all_docs:
        emb = oai.embeddings.create(input=doc["content"][:500], model=settings.azure_openai_embedding_deployment).data[0].embedding
        docs_to_index.append({
            "id": str(uuid.uuid4()),
            "title": doc["title"],
            "content": doc["content"],
            "source": doc["source"],
            "tenant_id": doc["tenant_id"],
            "category": doc.get("category", "general"),
            "content_vector": emb,
        })

    if docs_to_index:
        search_client.upload_documents(docs_to_index)
        print(f"Indexed {len(docs_to_index)} documents for tenant {tenant_id}")


if __name__ == "__main__":
    asyncio.run(index_tenant("tenant-contoso"))
