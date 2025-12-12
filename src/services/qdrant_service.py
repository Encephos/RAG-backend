from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from src.core.config import settings
import uuid
import logging

logger = logging.getLogger(__name__)

class QdrantService:
    def __init__(self):
        self.client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )
        
        # Define Collections Map (ID -> Name)
        # Using simple names for Qdrant, mapped from frontend IDs
        self.collections = {
            "master": "master_collection",
            "botanical": "botanical_knowledge",
            "pharmacological": "pharmacological_knowledge",
            "studies": "studies_data",
            "production": "production_knowledge"
        }

        # Define Entity Collections Map
        self.entity_collections = {
            "master": settings.QDRANT_ENTITY_COLLECTION_NAME, # rag_entities
            "botanical": "botanical_entities",
            "pharmacological": "pharmacological_entities",
            "studies": "studies_entities",
            "production": "production_entities"
        }
        
        self._ensure_collections()

    def _ensure_collections(self):
        """Create collections if they don't exist."""
        try:
            collections = self.client.get_collections().collections
            existing_names = [c.name for c in collections]
            logger.info(f"Existing Qdrant collections: {existing_names}")
            
            # Ensure all data collections exist (Vectors)
            for key, col_name in self.collections.items():
                if col_name not in existing_names:
                    logger.info(f"Creating vector collection: {col_name}")
                    self.client.create_collection(
                        collection_name=col_name,
                        vectors_config=models.VectorParams(
                            size=384,
                            distance=models.Distance.COSINE
                        )
                    )
                else:
                    logger.info(f"Vector Collection {col_name} already exists.")
                
            # Ensure all entity collections exist (Graphs)
            for key, col_name in self.entity_collections.items():
                if col_name not in existing_names:
                    logger.info(f"Creating entity collection: {col_name}")
                    self.client.create_collection(
                        collection_name=col_name,
                        vectors_config=models.VectorParams(
                            size=384,
                            distance=models.Distance.COSINE
                        )
                    )
                else:
                    logger.info(f"Entity Collection {col_name} already exists.")
                
        except Exception as e:
            logger.error(f"Error ensuring collections: {e}")

    def upsert(self, text: str, vector: List[float], metadata: Dict[str, Any] = None, collection_alias: str = "master"):
        """
        Upsert a single document chunk.
        collection_alias: One of 'master', 'botanical', 'pharmacological', etc.
        """
        if metadata is None:
            metadata = {}
        
        metadata["text"] = text
        
        # Resolve actual collection name
        collection_name = self.collections.get(collection_alias, self.collections["master"])
        
        # Generate deterministic ID based on text content to prevent duplicates
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, text))
        
        try:
            self.client.upsert(
                collection_name=collection_name,
                points=[
                    models.PointStruct(
                        id=doc_id,
                        vector=vector,
                        payload=metadata
                    )
                ]
            )
        except Exception as e:
            # Simple retry logic only for master as it is critical, or just log error
            logger.error(f"Error upserting to {collection_name}: {e}")
            raise e

    def search(self, vector: List[float], limit: int = 5, collection_alias: str = "master") -> List[Dict[str, Any]]:
        """Search for similar document chunks in a specific collection."""
        
        collection_name = self.collections.get(collection_alias, self.collections["master"])
        
        results = self.client.query_points(
            collection_name=collection_name,
            query=vector,
            limit=limit
        ).points
        
        return [
            {
                "text": hit.payload.get("text", ""),
                "score": hit.score,
                "metadata": hit.payload
            }
            for hit in results
        ]

    # --- Entity / Graph Methods ---

    def upsert_entity(self, entity_id: str, vector: List[float], payload: Dict[str, Any], collection_name: str = None):
        """Upsert a graph entity."""
        target_collection = collection_name or settings.QDRANT_ENTITY_COLLECTION_NAME
        
        self.client.upsert(
            collection_name=target_collection,
            points=[
                models.PointStruct(
                    id=entity_id,
                    vector=vector,
                    payload=payload
                )
            ]
        )

    def search_entities(self, vector: List[float], limit: int = 1, score_threshold: float = 0.0, collection_name: str = None) -> List[Any]:
        """Search for similar entities (for resolution or retrieval)."""
        target_collection = collection_name or settings.QDRANT_ENTITY_COLLECTION_NAME
        
        return self.client.query_points(
            collection_name=target_collection,
            query=vector,
            limit=limit,
            score_threshold=score_threshold
        ).points

    def get_entity(self, entity_id: str, collection_name: str = None) -> Optional[Dict[str, Any]]:
        """Retrieve entity payload by ID."""
        target_collection = collection_name or settings.QDRANT_ENTITY_COLLECTION_NAME
        
        points = self.client.retrieve(
            collection_name=target_collection,
            ids=[entity_id]
        )
        if points:
            return points[0].payload
        return None

    def update_entity_payload(self, entity_id: str, payload: Dict[str, Any], collection_name: str = None):
        """Update payload of an existing entity."""
        target_collection = collection_name or settings.QDRANT_ENTITY_COLLECTION_NAME
        
        self.client.set_payload(
            collection_name=target_collection,
            payload=payload,
            points=[entity_id]
        )

    async def get_total_points(self) -> dict:
        """
        Count total points.
        Returns count of 'master_collection' as the primary metric.
        """
        try:
             # We use the 'master' vector collection as the reference for "Total Knowledge Items"
             master_count = self.client.count(collection_name=self.collections["master"]).count
        except Exception as e:
             logger.warning(f"Failed to count master collection: {e}")
             master_count = 0
             
        return {
            "total_points": master_count,
            "details": {"master": master_count}
        }
