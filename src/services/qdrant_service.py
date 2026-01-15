from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from src.core.config import settings
import uuid
import logging
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

logger = logging.getLogger(__name__)

class QdrantService:
    def __init__(self):
        self.client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            timeout=60.0 # Increase timeout to 60s
        )
        
        # Define Collections Map (ID -> Name)
        # Using simple names for Qdrant, mapped from frontend IDs
        self.collections = {
            "master": "master_collection_768",
            "botanical": "botanical_knowledge_768",
            "pharmacological": "pharmacological_knowledge_768",
            "studies": "studies_data_768",
            "production": "production_knowledge_768",
            # Legacy Fallback Collections (384-dim)
            "master_legacy": "master_collection",
            "botanical_legacy": "botanical_knowledge",
            "pharmacological_legacy": "pharmacological_knowledge",
            "studies_legacy": "studies_data",
            "strain": "strain_lineage_data"
        }

        # Define Entity Collections Map
        self.entity_collections = {
            "master": settings.QDRANT_ENTITY_COLLECTION_NAME, # rag_entities_768
            "botanical": "botanical_entities_768",
            "pharmacological": "pharmacological_entities_768",
            "studies": "studies_entities_768",
            "production": "production_entities_768"
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
                            size=settings.EMBEDDING_VECTOR_SIZE,
                            distance=models.Distance.COSINE
                        )
                    )
                else:
                    logger.info(f"Vector Collection {col_name} already exists.")
            
                
            # Ensure Strain Collection (384 dim)
            # Legacy "strain_lineage_data" and new "strain_genetics"
            for col in ["strain_lineage_data", "strain_genetics"]:
                if col not in existing_names:
                    logger.info(f"Creating strain lineage collection (384 dim): {col}")
                    self.client.create_collection(
                        collection_name=col,
                        vectors_config=models.VectorParams(
                            size=384,
                            distance=models.Distance.COSINE
                        )
                    )
                
            # Ensure all entity collections exist (Graphs)
            for key, col_name in self.entity_collections.items():
                if col_name not in existing_names:
                    logger.info(f"Creating entity collection: {col_name}")
                    self.client.create_collection(
                        collection_name=col_name,
                        vectors_config=models.VectorParams(
                            size=settings.EMBEDDING_VECTOR_SIZE,
                            distance=models.Distance.COSINE
                        )
                    )
                else:
                    logger.info(f"Entity Collection {col_name} already exists.")
                
        except Exception as e:
            logger.error(f"Error ensuring collections: {e}")

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type((ResponseHandlingException, UnexpectedResponse, ConnectionError)))
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
            logger.warning(f"Error upserting to {collection_name} (attempting retry): {e}")
            raise e

    def search(self, vector: List[float], limit: int = 5, collection_alias: str = "master", query_text: str = None) -> List[Dict[str, Any]]:
        """
        Hyper-Hybrid Search: Combines Dense Vector Search with Keyword Matching.
        Ensures finding specific terms (e.g. 'Zkittelz') even if vector similarity is low.
        """
        
        collection_name = self.collections.get(collection_alias, self.collections["master"])
        
        # 1. Vector Search (Semantic)
        vector_results = self.client.query_points(
            collection_name=collection_name,
            query=vector,
            limit=limit
        ).points
        
        # 2. Keyword Search (Exact/Lexical) - If query provided
        keyword_results = []
        if query_text and len(query_text) > 2:
            try:
                # Use MatchText for full-text-like behavior (token based)
                # Or MatchValue for strict exact match of fields like 'name'
                # We try both: Text content AND specific payload fields
                kw_filter = models.Filter(
                    should=[
                        models.FieldCondition(key="text", match=models.MatchText(text=query_text)),
                        models.FieldCondition(key="name", match=models.MatchValue(value=query_text)), # Strict name match
                        models.FieldCondition(key="title", match=models.MatchText(text=query_text))
                    ]
                )
                
                # Fetch more candidates for keywords to ensure good recall
                keyword_points = self.client.scroll(
                    collection_name=collection_name,
                    scroll_filter=kw_filter,
                    limit=limit,
                    with_payload=True
                )[0]
                
                keyword_results = keyword_points
                if keyword_results:
                    logger.info(f"Hybrid Search: Found {len(keyword_results)} keyword matches for '{query_text}'")
                    
            except Exception as e:
                logger.warning(f"Keyword search failed (hybrid fallback): {e}")

        # 3. Merge & Deduplicate
        # Map ID -> Point, boosting score for keyword matches
        merged = {}
        
        # Add Vector Results first
        for hit in vector_results:
            merged[hit.id] = {
                "point": hit,
                "score": hit.score,
                "reason": "vector"
            }
            
        # Add/Boost Keyword Results
        for hit in keyword_results:
            if hit.id in merged:
                # Boost existing vector hit
                merged[hit.id]["score"] += 0.3 # Boost factor
                merged[hit.id]["reason"] = "hybrid"
            else:
                # Add new keyword-only hit with high base score
                # Assign score 1.0 to ensure it rivals/beats average vector scores (0.7-0.8)
                merged[hit.id] = {
                    "point": hit,
                    "score": 0.95, 
                    "reason": "keyword"
                }
        
        # 4. Sort and Slice
        sorted_hits = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:limit]
        
        return [
            {
                "text": item["point"].payload.get("text", ""),
                "score": item["score"],
                "metadata": item["point"].payload,
                "search_method": item["reason"]
            }
            for item in sorted_hits
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

    async def recover_snapshot_from_file(self, file_content: bytes, filename: str):
        """
        Recover a collection from a snapshot file.
        Attempts to guess the collection name from the filename.
        """
        # 1. Use Filename as Collection Name (User Request)
        # e.g., "botanical_entities.snapshot" -> "botanical_entities"
        target_collection = filename
        for ext in ['.snapshot', '.tar', '.zip']:
             if target_collection.endswith(ext):
                 target_collection = target_collection[:-len(ext)]
                 
        logger.info(f"Recovering snapshot '{filename}' into collection '{target_collection}'")
        
        # 2. Use requests (sync) or httpx (async) to upload
        # Qdrant client doesn't expose a stream upload for snapshots easily, 
        # so we use the raw HTTP API.
        import httpx
        
        url = f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}/collections/{target_collection}/snapshots/upload"
        
        # We need to send it as multipart/form-data
        files = {'snapshot': (filename, file_content)}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, files=files, timeout=300.0) # 5 min timeout for big files
            
            if response.status_code != 200:
                raise Exception(f"Qdrant Snapshot Upload Failed: {response.text}")
                
        return target_collection

    def get_strain_lineage(self, strain_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve strain lineage data by exact name match (normalized).
        Uses the 384-dim strain_lineage_data collection.
        """
        try:
            # We generate the UUID deterministically as per ingestion strategy
            name_normalized = strain_name.strip().lower()
            doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, name_normalized))
            
            points = self.client.retrieve(
                collection_name="strain_genetics",
                ids=[doc_id]
            )
            
            if points:
                return points[0].payload
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving strain lineage for {strain_name}: {e}")
            return None
