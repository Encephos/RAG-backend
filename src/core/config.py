from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "RAG Backend"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Qdrant Settings
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "rag_collection"
    QDRANT_ENTITY_COLLECTION_NAME: str = "rag_entities"
    
    # Embedding Settings
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_VECTOR_SIZE: int = 384
    
    # OpenRouter LLM Settings
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_MODEL: str = "google/gemini-2.5-flash-lite-preview" # Updated to Gemini 2.5 Flash Lite

    # Security Settings
    BACKEND_API_KEY: str = "secret-api-key" # Default for dev, override in .env
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
