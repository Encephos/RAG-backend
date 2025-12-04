from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "RAG Backend"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Qdrant Settings
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "rag_collection"
    
    # Embedding Settings
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
