from typing import List
from fastembed import TextEmbedding
from src.core.config import settings
import numpy as np
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Service for generating text embeddings using FastEmbed.
    Optimized for async execution using ThreadPoolExecutor.
    """
    def __init__(self):
        self.model = TextEmbedding(model_name=settings.EMBEDDING_MODEL_NAME)
        self.model = TextEmbedding(model_name=settings.EMBEDDING_MODEL_NAME)
        self._model_384 = None # Lazy load legacy model
        self._executor = ThreadPoolExecutor(max_workers=3) # Limit CPU threads

    def _get_model_384(self):
        """Lazy load the 384-dim model for legacy collections."""
        if not self._model_384:
             logger.info("Loading legacy 384-dim model (all-MiniLM-L6-v2)...")
             self._model_384 = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
        return self._model_384

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts asynchronously.
        
        Args:
            texts: List of strings to embed.
            
        Returns:
            List of embedding vectors (lists of floats).
        """
        loop = asyncio.get_running_loop()
        try:
            # Run CPU-bound embedding in thread pool
            embeddings = await loop.run_in_executor(self._executor, self._embed_sync, texts)
            return embeddings
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    def _embed_sync(self, texts: List[str]) -> List[List[float]]:
        """Synchronous embedding generation (internal)."""
        embeddings = list(self.model.embed(texts))
        return [emb.tolist() if isinstance(emb, np.ndarray) else list(emb) for emb in embeddings]

    async def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a single query string asynchronously.
        
        Args:
            query: The query string.
            
        Returns:
            Embedding vector as list of floats.
        """
        embeddings = await self.embed([query])
        return embeddings[0]

    async def embed_query_384(self, query: str) -> List[float]:
        """
        Generate 384-dim embedding for legacy collections.
        """
        loop = asyncio.get_running_loop()
        try:
             # Run in thread pool
            embedding = await loop.run_in_executor(self._executor, self._embed_sync_384, query)
            return embedding
        except Exception as e:
            logger.error(f"Error generating 384 embedding: {e}")
            raise

    def _embed_sync_384(self, query: str) -> List[float]:
        """Internal sync method for 384 model."""
        model = self._get_model_384()
        embedding = list(model.embed([query]))[0]
        return embedding.tolist() if isinstance(embedding, np.ndarray) else list(embedding)
