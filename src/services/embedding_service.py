from typing import List
from fastembed import TextEmbedding
from src.core.config import settings
import numpy as np

class EmbeddingService:
    def __init__(self):
        self.model = TextEmbedding(model_name=settings.EMBEDDING_MODEL_NAME)

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        # fastembed returns a generator of numpy arrays, convert to list of lists
        embeddings = list(self.model.embed(texts))
        return [emb.tolist() if isinstance(emb, np.ndarray) else list(emb) for emb in embeddings]

    def embed_query(self, query: str) -> List[float]:
        """Generate embedding for a single query string."""
        embeddings = list(self.model.embed([query]))
        emb = embeddings[0]
        return emb.tolist() if isinstance(emb, np.ndarray) else list(emb)
