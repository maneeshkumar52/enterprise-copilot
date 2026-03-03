from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    azure_openai_endpoint: str = Field(default="https://your-openai.openai.azure.com/", env="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_key: str = Field(default="your-key", env="AZURE_OPENAI_API_KEY")
    azure_openai_api_version: str = Field(default="2024-02-01", env="AZURE_OPENAI_API_VERSION")
    azure_openai_deployment: str = Field(default="gpt-4o", env="AZURE_OPENAI_DEPLOYMENT")
    azure_openai_embedding_deployment: str = Field(default="text-embedding-3-large", env="AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    azure_search_endpoint: str = Field(default="https://your-search.search.windows.net", env="AZURE_SEARCH_ENDPOINT")
    azure_search_api_key: str = Field(default="your-search-key", env="AZURE_SEARCH_API_KEY")
    azure_search_index_name: str = Field(default="enterprise-knowledge", env="AZURE_SEARCH_INDEX_NAME")
    cosmos_endpoint: str = Field(default="https://your-cosmos.documents.azure.com:443/", env="COSMOS_ENDPOINT")
    cosmos_key: str = Field(default="your-cosmos-key", env="COSMOS_KEY")
    cosmos_database: str = Field(default="enterprise-copilot", env="COSMOS_DATABASE")
    cosmos_memory_container: str = Field(default="user-memory", env="COSMOS_MEMORY_CONTAINER")
    entra_tenant_id: str = Field(default="your-tenant-id", env="ENTRA_TENANT_ID")
    jwt_secret: str = Field(default="dev-secret-change-in-production", env="JWT_SECRET")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    return Settings()
