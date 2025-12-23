from typing import List, Dict, Any, Optional
import uuid
from src.services.qdrant_service import QdrantService
from src.services.embedding_service import EmbeddingService
from qdrant_client import models
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
        self._lineage_cache = {} # (strain_name, depth) -> (timestamp, result)
        self._cache_ttl = 300 # 5 minutes

    async def add_entity_with_resolution(self, name: str, type: str, description: str, collection_name: str = None, use_384_dim: bool = False) -> str:
        """
        Add an entity to the graph with resolution (deduplication).
        If use_384_dim is True, uses the smaller embedding model (all-MiniLM-L6-v2) suitable for botanical_entities.
        """
        # Create semantic embedding for the entity
        text_to_embed = f"{name}: {description}"
        
        if use_384_dim:
             vector = await self.embedder.embed_query_384(text_to_embed)
        else:
             vector = await self.embedder.embed_query(text_to_embed)
        
        # 1. Entity Resolution: Check for existing similar entities within the specific collection
        existing = self.qdrant.search_entities(vector, limit=1, score_threshold=0.92, collection_name=collection_name)
        
        if existing:
            logger.info(f"Resolved entity '{name}' to existing ID: {existing[0].id} in {collection_name}")
            return existing[0].payload.get("id") or str(existing[0].id)
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
            self.qdrant.upsert_entity(new_id, vector, payload, collection_name=collection_name)
            logger.info(f"Created new entity '{name}' with ID: {new_id} in {collection_name}")
            return new_id

    def add_relation(self, source_id: str, target_id: str, relation_type: str, collection_name: str = None):
        """
        Add a relation between two entities by ID within a specific collection.
        """
        if source_id == target_id:
            return

        # 1. Get source entity payload
        source_payload = self.qdrant.get_entity(source_id, collection_name=collection_name)
        if not source_payload:
            logger.warning(f"Source entity {source_id} not found for relation in {collection_name}.")
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
        self.qdrant.update_entity_payload(source_id, source_payload, collection_name=collection_name)
        logger.debug(f"Added relation: {source_id} --{relation_type}--> {target_id} in {collection_name}")

    async def get_graph_context(self, query: str, depth: int = 1, collection_name: str = None) -> str:
        """
        Retrieve graph context for a query using semantic entry points from a specific collection.
        """
        # 1. Vector Entry Point: Find entities relevant to the query
        query_vector = await self.embedder.embed_query(query)
        
        entry_points = self.qdrant.search_entities(query_vector, limit=3, score_threshold=0.50, collection_name=collection_name)
        
        if not entry_points:
            logger.debug(f"No graph entry points found above threshold 0.50 for query: {query} in {collection_name}")
            return ""

        context_lines = []
        visited_ids = set()

        # 2. Traverse Graph (1-Hop Neighborhood)
        for point in entry_points:
            entity = point.payload
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
                target_payload = self.qdrant.get_entity(target_id, collection_name=collection_name)
                if target_payload:
                    target_name = target_payload.get("name")
                    target_type = target_payload.get("type", "Unknown")
                    target_desc = target_payload.get("description", "")
                    context_lines.append(f"  - {rel_type} -> {target_name} ({target_type}): {target_desc}")
        
        return "\n".join(context_lines)

    async def get_visualization_data(self, query: str, collection_name: str = None) -> Dict[str, Any]:
        """
        Flatten the graph context into a node-link structure for visualization.
        """
        # Embed query
        query_vector = await self.embedder.embed_query(query)
        
        # Search for central nodes
        # We assume 'entities' collection if not specified or derived from name
        # If collection_name is passed (e.g. 'botanical_knowledge'), map it to entities
        target_collection = collection_name
        if not target_collection:
             # Default to a generic search or all known entity collections?
             # For now, let's assume we search in the default entity collection associated with settings
             from src.core.config import settings
             target_collection = settings.QDRANT_ENTITY_COLLECTION_NAME
        
        # Search
        results = self.qdrant.search_entities(query_vector, limit=20, score_threshold=0.35, collection_name=target_collection)
        
        nodes = {}
        links = []
        
        for point in results:
            payload = point.payload
            p_id = payload.get("id")
            
            if p_id not in nodes:
                nodes[p_id] = {
                    "id": p_id,
                    "label": payload.get("name"),
                    "group": payload.get("type", "concept"),
                    "val": point.score * 10 # Size based on relevance
                }
            
            # Process relations for links
            relations = payload.get("relations", [])
            for rel in relations:
                target_id = rel.get("target_id")
                # We add the link
                links.append({
                    "source": p_id,
                    "target": target_id,
                    "label": rel.get("type", "related_to")
                })
                
                # We might want to fetch the target node details if not already in nodes?
                # For visualization to be complete, we need the target node label.
                # But Qdrant 'get' is 1-by-1. For performance, we might just create a placeholder node
                # if we don't have it, or rely on it being found in the search if relevant?
                # Better: Add a "stub" node if missing, maybe the UI can fetch details or just show ID/Unknown.
                # However, our relation storage usually stores just ID.
                # Optimization: In `add_relation`, we could store target_name too. 
                # Without target_name, the graph looks ugly (just IDs).
                # Let's check `add_relation` logic... it stores target_id.
                
                # WORKAROUND: For now, if we don't have the target node in our search results,
                # we just show the ID or skip it? 
                # Ideally, we should do a batch fetch for missing IDs. Qdrant supports retrieve by list of IDs.
                
        # Batch fetch missing nodes
        all_node_ids = set(nodes.keys())
        target_ids = {l["target"] for l in links}
        missing_ids = list(target_ids - all_node_ids)
        
        if missing_ids:
            # Batch retrieve
             # Note: QdrantService might need a batch get method. 
             # Let's try to access Qdrant client directly or add a method.
             # Checking QdrantService... it has `get_entity`.
             # We can do parallel gets or add a batch get.
             # Implementation choice: Add `get_entities(ids)` to QdrantService in next step if needed,
             # OR just loop `get_entity` here (slower but safer for now).
            pass
            # For this iteration, let's just loop (limit is small, 15 nodes * avg 2 relations = 30 max)
            for m_id in missing_ids:
                 entity = self.qdrant.get_entity(m_id, collection_name=target_collection)
                 if entity:
                     nodes[m_id] = {
                         "id": m_id,
                         "label": entity.get("name"),
                         "group": entity.get("type", "target"),
                         "val": 1 # Default size
                     }
        
        return {
            "nodes": list(nodes.values()),
            "links": links
        }

    async def get_lineage(self, strain_name: str, depth: int = 10, collection_name: str = None) -> Dict[str, Any]:
        """
        Retrieves the genealogy/lineage of a strain.
        Traverses 'bred_from', 'parent_of', 'hybrid_of' relations.
        """
        import time
        cache_key = (strain_name, depth, collection_name)
        if cache_key in self._lineage_cache:
            ts, data = self._lineage_cache[cache_key]
            if time.time() - ts < self._cache_ttl:
                return data
            else:
                del self._lineage_cache[cache_key]

        target_collection = collection_name or "botanical_entities" # Reverted to 384 collection
        
        # 1. Find Start Node
        # We search by name vector essentially to find the exact node ID
        if target_collection == "botanical_entities":
            query_vector = await self.embedder.embed_query_384(strain_name)
        else:
            query_vector = await self.embedder.embed_query(strain_name)
            
        start_points = self.qdrant.search_entities(query_vector, limit=1, score_threshold=0.80, collection_name=target_collection)
        
        start_node_id = None
        start_payload = None
        
        if start_points:
             start_node_id = start_points[0].id
             start_payload = start_points[0].payload
        else:
             # Fallback: Exact name match via Scroll
             # This handles cases where vector/embedding quality is low but name is known
             try:
                 scroll_result = self.qdrant.client.scroll(
                     collection_name=target_collection,
                     scroll_filter=models.Filter(
                         must=[
                             models.FieldCondition(
                                 key="name",
                                 match=models.MatchValue(value=strain_name)
                             )
                         ]
                     ),
                     limit=1,
                     with_payload=True
                 )
                 if scroll_result[0]:
                     start_node_id = scroll_result[0][0].id
                     start_payload = scroll_result[0][0].payload
                     logger.info(f"Lineage: Found '{strain_name}' via exact name fallback.")
             except Exception as e:
                 logger.warning(f"Lineage fallback search failed: {e}")

        if not start_node_id:
            logger.warning(f"Lineage: Strain '{strain_name}' not found in {target_collection}")
            return {"nodes": [], "links": []}
        
        nodes = {}
        links = []
        visited = set()
        queue = [(start_node_id, 0)] # (id, current_depth)
        
        nodes[start_node_id] = {
            "id": start_node_id,
            "label": start_payload.get("name"),
            "group": "Target",
            "val": 20,
            "breeder": start_payload.get("breeder"),
            "thc": start_payload.get("thc"),
            "cbd": start_payload.get("cbd"),
            "type": start_payload.get("type"),
            "description": start_payload.get("description"),
            "effects": start_payload.get("effects"),
            "flavor": start_payload.get("flavor"),
            "image": start_payload.get("image")
        }
        visited.add(start_node_id)
        
        # 2. BFS Traversal
        while queue:
            current_id, current_depth = queue.pop(0)
            
            if current_depth >= depth:
                continue
                
            # Fetch current node details if not already (for start node we have it, for others might need fetch)
            # Actually we need payload to see relations
            if current_id == start_node_id:
                current_payload = start_payload
            else:
                current_payload = self.qdrant.get_entity(current_id, collection_name=target_collection) or {}
                
            relations = current_payload.get("relations", [])
            
            for rel in relations:
                target_id = rel.get("target_id")
                rel_type = rel.get("type", "").lower()
                
                # Filter for lineage-relevant relations (Ancestors only)
                # We exclude 'parent_of' to prevent recursive descent into all children (Use Step 3 for immediate children)
                if rel_type in ["bred_from", "has_parent", "hybrid_of", "child_of", "cross_of"]:
                     
                     # Add Logic: If bred_from -> target is Parent.
                     # We want to show the tree.
                     
                     if target_id not in visited:
                         visited.add(target_id)
                         queue.append((target_id, current_depth + 1))
                         
                         # Fetch node info for visualisation
                         target_node_payload = self.qdrant.get_entity(target_id, collection_name=target_collection)
                         
                         if target_node_payload:
                            nodes[target_id] = {
                                "id": target_id,
                                "label": target_node_payload.get("name"),
                                "group": "Ancestor" if rel_type == "bred_from" else "Relative",
                                "val": 10,
                                "breeder": target_node_payload.get("breeder"),
                                "thc": target_node_payload.get("thc"),
                                "cbd": target_node_payload.get("cbd"),
                                "type": target_node_payload.get("type"),
                                "description": target_node_payload.get("description"),
                                "effects": target_node_payload.get("effects"),
                                "flavor": target_node_payload.get("flavor"),
                                "image": target_node_payload.get("image")
                            }
                         else:
                             # Fallback: Create Stub Node from Relation Data
                             # This ensures the tree is shown even if the parent entity isn't fully ingested yet
                             nodes[target_id] = {
                                 "id": target_id,
                                 "label": rel.get("target_label") or "Unknown Parent",
                                 "group": "Ancestor",
                                 "val": 8,
                                 "type": "Inferred"
                             }
                     
                     # Add Link
                     links.append({
                         "source": current_id,
                         "target": target_id,
                         "label": rel_type
                     })

        # 3. Fetch Descendants (1st Level Children)
        # Search for entities where relations.target_id == start_node_id
        try:
            scroll_result = self.qdrant.client.scroll(
                collection_name=target_collection,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="relations.target_id",
                            match=models.MatchValue(value=start_node_id)
                        )
                    ]
                ),
                limit=15, 
                with_payload=True
            )
            
            descendants = scroll_result[0]

            for point in descendants:
                if point.id == start_node_id: continue
                
                child_id = point.id
                child_payload = point.payload or {}
                
                # Check relation type
                rels = child_payload.get("relations", [])
                relevant_rel = next((r for r in rels if r.get("target_id") == start_node_id), None)
                
                if relevant_rel:
                    if child_id not in nodes:
                        nodes[child_id] = {
                            "id": child_id,
                            "label": child_payload.get("name"),
                            "group": "Descendant",
                            "val": 10
                        }
                    
                    # Store Link
                    links.append({
                        "source": child_id,
                        "target": start_node_id,
                        "label": relevant_rel.get("type", "descendant")
                    })
        except Exception as e:
            logger.warning(f"Error fetching descendants: {e}")

        result = {
            "nodes": list(nodes.values()),
            "links": links
        }
        
        # Cache Result
        self._lineage_cache[cache_key] = (time.time(), result)
        
        return result

    def clear(self) -> None:
        """Clear is not easily supported in persistent vector store without dropping collection."""
        pass
