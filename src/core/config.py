from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "RAG Backend"
    VERSION: str = "0.4.2"
    API_V1_STR: str = "/api/v1"
    
    # Qdrant Settings
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "master_collection_768"
    QDRANT_ENTITY_COLLECTION_NAME: str = "rag_entities_768"
    
    # Embedding Settings
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-base-en-v1.5"
    EMBEDDING_VECTOR_SIZE: int = 768
    
    # Reranker Settings
    RERANKER_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    INITIAL_RETRIEVAL_LIMIT: int = 50
    FINAL_K: int = 15
    
    # OpenRouter LLM Settings
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_MODEL: str = "google/gemini-2.5-flash-lite-preview"
    
    # OpenAI Settings (for Embeddings if needed)
    OPENAI_API_KEY: str = ""

    # Security Settings
    BACKEND_API_KEY: str = "secret-api-key" # Default for dev, override in .env
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
