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
        self.entity_collection_name = settings.QDRANT_ENTITY_COLLECTION_NAME
        self._ensure_collections()

    def _ensure_collections(self):
        """Create collections if they don't exist."""
        collections = self.client.get_collections().collections
        existing_names = [c.name for c in collections]
        
        # Document Collection
        if self.collection_name not in existing_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=384,
                    distance=models.Distance.COSINE
                )
            )
            
        # Entity Collection (for Knowledge Graph)
        if self.entity_collection_name not in existing_names:
            self.client.create_collection(
                collection_name=self.entity_collection_name,
                vectors_config=models.VectorParams(
                    size=384,
                    distance=models.Distance.COSINE
                )
            )

    def upsert(self, text: str, vector: List[float], metadata: Dict[str, Any] = None):
        """Upsert a single document chunk."""
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
        """Search for similar document chunks."""
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

    # --- Entity / Graph Methods ---

    def upsert_entity(self, entity_id: str, vector: List[float], payload: Dict[str, Any]):
        """Upsert a graph entity."""
        self.client.upsert(
            collection_name=self.entity_collection_name,
            points=[
                models.PointStruct(
                    id=entity_id,
                    vector=vector,
                    payload=payload
                )
            ]
        )

    def search_entities(self, vector: List[float], limit: int = 1, score_threshold: float = 0.0) -> List[Any]:
        """Search for similar entities (for resolution or retrieval)."""
        return self.client.search(
            collection_name=self.entity_collection_name,
            query_vector=vector,
            limit=limit,
            score_threshold=score_threshold
        )

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve entity payload by ID."""
        points = self.client.retrieve(
            collection_name=self.entity_collection_name,
            ids=[entity_id]
        )
        if points:
            return points[0].payload
        return None

    def update_entity_payload(self, entity_id: str, payload: Dict[str, Any]):
        """Update payload of an existing entity."""
        self.client.set_payload(
            collection_name=self.entity_collection_name,
            payload=payload,
            points=[entity_id]
        )
