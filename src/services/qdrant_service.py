from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from src.core.config import settings
import uuid

class QdrantService:
    def __init__(self):
        self.client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if not exists:
            # Assuming 384 dim for all-MiniLM-L6-v2
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=384,
                    distance=models.Distance.COSINE
                )
            )

    def upsert(self, text: str, vector: List[float], metadata: Dict[str, Any] = None):
        """Upsert a single document."""
        if metadata is None:
            metadata = {}
        
        metadata["text"] = text
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload=metadata
                )
            ]
        )

    def search(self, vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar vectors."""
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            limit=limit
        )
        
        return [
            {
                "text": hit.payload.get("text", ""),
                "score": hit.score,
                "metadata": hit.payload
            }
            for hit in results
        ]
