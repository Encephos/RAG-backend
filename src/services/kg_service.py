from typing import List, Dict, Any, Optional
import uuid
from src.services.qdrant_service import QdrantService
from src.services.embedding_service import EmbeddingService
import logging

logger = logging.getLogger(__name__)

class KnowledgeGraphService:
    """
    Service for managing the Vector-Native Knowledge Graph.
    Handles entity resolution, relation storage, and graph retrieval.
    """
    def __init__(self):
        self.qdrant = QdrantService()
        self.embedder = EmbeddingService()

    async def add_entity_with_resolution(self, name: str, type: str, description: str) -> str:
        """
        Add an entity to the graph with resolution (deduplication).
        
        Args:
            name: Entity name.
            type: Entity type.
            description: Entity description.
            
        Returns:
            The Entity ID (either new or existing).
        """
        # Create semantic embedding for the entity
        text_to_embed = f"{name}: {description}"
        vector = await self.embedder.embed_query(text_to_embed)
        
        # 1. Entity Resolution: Check for existing similar entities
        existing = self.qdrant.search_entities(vector, limit=1, score_threshold=0.92)
        
        if existing:
            logger.info(f"Resolved entity '{name}' to existing ID: {existing[0].id}")
            return existing[0].metadata.get("id") or str(existing[0].id)
        else:
            # No match -> Create new entity
            new_id = str(uuid.uuid4())
            payload = {
                "id": new_id,
                "name": name,
                "type": type,
                "description": description,
                "relations": []
            }
            self.qdrant.upsert_entity(new_id, vector, payload)
            logger.info(f"Created new entity '{name}' with ID: {new_id}")
            return new_id

    def add_relation(self, source_id: str, target_id: str, relation_type: str):
        """
        Add a relation between two entities by ID.
        
        Args:
            source_id: ID of the source entity.
            target_id: ID of the target entity.
            relation_type: Type of the relation.
        """
        if source_id == target_id:
            return

        # 1. Get source entity payload
        source_payload = self.qdrant.get_entity(source_id)
        if not source_payload:
            logger.warning(f"Source entity {source_id} not found for relation.")
            return

        # 2. Check if relation already exists
        relations = source_payload.get("relations", [])
        for rel in relations:
            if rel["target_id"] == target_id and rel["type"] == relation_type:
                return # Relation exists

        # 3. Add new relation
        relations.append({
            "target_id": target_id,
            "type": relation_type
        })
        
        # 4. Update payload in Qdrant
        source_payload["relations"] = relations
        self.qdrant.update_entity_payload(source_id, source_payload)
        logger.debug(f"Added relation: {source_id} --{relation_type}--> {target_id}")

    async def get_graph_context(self, query: str, depth: int = 1) -> str:
        """
        Retrieve graph context for a query using semantic entry points.
        
        Args:
            query: The search query.
            depth: Traversal depth (currently 1-hop).
            
        Returns:
            A string representation of the graph context.
        """
        # 1. Vector Entry Point: Find entities relevant to the query
        query_vector = await self.embedder.embed_query(query)
        
        entry_points = self.qdrant.search_entities(query_vector, limit=3, score_threshold=0.75)
        
        if not entry_points:
            return ""

        context_lines = []
        visited_ids = set()

        # 2. Traverse Graph (1-Hop Neighborhood)
        for point in entry_points:
            entity = point.metadata
            e_id = entity.get("id")
            e_name = entity.get("name")
            
            if e_id in visited_ids:
                continue
            visited_ids.add(e_id)
            
            # Add entity description to context
            context_lines.append(f"Entity: {e_name} ({entity.get('type')}) - {entity.get('description')}")
            
            # Traverse relations
            relations = entity.get("relations", [])
            for rel in relations:
                target_id = rel["target_id"]
                rel_type = rel["type"]
                
                # Fetch target entity details
                target_payload = self.qdrant.get_entity(target_id)
                if target_payload:
                    target_name = target_payload.get("name")
                    context_lines.append(f"  - {rel_type} -> {target_name}")
        
        return "\n".join(context_lines)

    def clear(self) -> None:
        """Clear is not easily supported in persistent vector store without dropping collection."""
        pass
