from typing import List
from fastembed import TextEmbedding
from src.core.config import settings

class EmbeddingService:
    def __init__(self):
        self.model = TextEmbedding(model_name=settings.EMBEDDING_MODEL_NAME)

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        # fastembed returns a generator, convert to list
        return list(self.model.embed(texts))

    def embed_query(self, query: str) -> List[float]:
        """Generate embedding for a single query string."""
        return list(self.model.embed([query]))[0]
