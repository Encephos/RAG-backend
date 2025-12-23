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
        Retrieves the genealogy/lineage of a strain using Batched BFS for performance.
        Builds a strict spanning tree to prevent cycles.
        """
        import time
        cache_key = (strain_name, depth, collection_name)
        if cache_key in self._lineage_cache:
            ts, data = self._lineage_cache[cache_key]
            if time.time() - ts < self._cache_ttl:
                return data
            else:
                del self._lineage_cache[cache_key]

        target_collection = collection_name or "botanical_entities"
        
        # 1. Resolve Start Node
        # Try finding by exact name first (Fastest/Safest for known entities)
        start_node_id = None
        start_payload = None
        
        try:
             # Smart Exact Match (Handle "Auto" suffix automatically)
             name_variants = [strain_name]
             suffixes = [" Auto", " Automatic", " Feminized", " Fem"]
             for s in suffixes:
                 if strain_name.lower().endswith(s.lower()):
                     name_variants.append(strain_name[0:-len(s)].strip())
             
             for name in name_variants:
                 scroll_res = self.qdrant.client.scroll(
                     collection_name=target_collection,
                     scroll_filter=models.Filter(must=[models.FieldCondition(key="name", match=models.MatchValue(value=name))]),
                     limit=1,
                     with_payload=True
                 )
                 if scroll_res[0]:
                     start_node_id = scroll_res[0][0].id
                     start_payload = scroll_res[0][0].payload
                     logger.info(f"Lineage: Resolved '{strain_name}' to '{name}' ({start_node_id})")
                     break
        except Exception as e:
            logger.warning(f"Lineage lookup failed: {e}")

        # Fallback to Vector Search if exact match failed
        if not start_node_id:
             if target_collection == "botanical_entities":
                 vec = await self.embedder.embed_query_384(strain_name)
             else:
                 vec = await self.embedder.embed_query(strain_name)
             
             search_res = self.qdrant.search_entities(vec, limit=1, score_threshold=0.70, collection_name=target_collection)
             if search_res:
                 start_node_id = search_res[0].id
                 start_payload = search_res[0].payload

        if not start_node_id:
            logger.warning(f"Lineage: Strain '{strain_name}' not found.")
            return {"nodes": [], "links": []}

        # 2. Batched BFS Traversal
        nodes = {}
        links = []
        visited = set([start_node_id])
        
        # Init Start Node
        nodes[start_node_id] = self._format_node(start_node_id, start_payload, "Target", 20)
        
        current_layer_ids = [start_node_id]
        
        for d in range(depth):
            if not current_layer_ids:
                break
            
            # Stop expansion if too large
            if len(nodes) > 200:
                logger.warning(f"Lineage limit 200 reached.")
                break

            # A. Fetch all entities in current layer to get their relations
            # (We already have payload for start node, but for subsequent layers we need to fetch)
            # Optimization: We already have payloads from the *previous* batch fetch? 
            # No, in previous step we found IDs. Now we need their payloads to find *their* parents.
            
            # Filter IDs that we don't have payloads for yet (should be all except start on first run)
            ids_to_fetch = [nid for nid in current_layer_ids if "relations" not in nodes[nid].get("payload_stub", {})]
            
            # If start node, we might already have payload, but let's ensure we parse relations
            # Actually, let's just use the `nodes` dict to store payload for processing?
            # We stored formatted node. Let's fetch payloads for the layer's IDs.
            
            layer_payloads = {}
            if current_layer_ids:
                # Batch Retrieve
                try:
                    # Qdrant retrieve takes list of IDs
                    results = self.qdrant.client.retrieve(
                        collection_name=target_collection,
                        ids=current_layer_ids,
                        with_payload=True
                    )
                    for point in results:
                        layer_payloads[point.id] = point.payload
                except Exception as e:
                    logger.error(f"Batch retrieve failed: {e}")
            
            next_layer_ids = []
            
            # Process this layer
            for pid in current_layer_ids:
                payload = layer_payloads.get(pid, {})
                relations = payload.get("relations", [])
                
                # UPDATE LABEL from actual payload (Fixes "Unknown")
                if payload.get("name"):
                    nodes[pid]["label"] = payload.get("name")
                    nodes[pid]["breeder"] = payload.get("breeder")
                    nodes[pid]["image"] = payload.get("image")
                    nodes[pid]["type"] = payload.get("type")

                # Check parents (upstream)
                for r in relations:
                    rtype = r.get("type", "").lower()
                    target_id = r.get("target_id")
                    
                    if rtype in ["bred_from", "has_parent", "hybrid_of", "child_of", "cross_of"]:
                         if target_id and target_id not in visited:
                             visited.add(target_id)
                             next_layer_ids.append(target_id)
                             
                             # Create Node Placeholder (will be filled in next fetch, or now?)
                             # We need to add to `nodes` so we can link to it.
                             # We don't have its payload yet, but we have label from relation.
                             nodes[target_id] = {
                                 "id": target_id,
                                 "label": r.get("target_label", "Unknown"),
                                 "group": "Ancestor",
                                 "val": 10,
                                 "payload_stub": {} # Marker to fetch next
                             }
                             
                             # Add Link (Strict Tree)
                             links.append({
                                 "source": pid,
                                 "target": target_id,
                                 "label": rtype
                             })

            current_layer_ids = next_layer_ids

        # 3. Add 1st Level Descendants (Children)
        # Separate fetch
        try:
             children_res = self.qdrant.client.scroll(
                 collection_name=target_collection,
                 scroll_filter=models.Filter(
                     must=[models.FieldCondition(key="relations.target_id", match=models.MatchValue(value=start_node_id))]
                 ),
                 limit=20,
                 with_payload=True
             )[0]
             
             for child in children_res:
                 if child.id not in nodes:
                     nodes[child.id] = self._format_node(child.id, child.payload, "Descendant", 10)
                     
                     # Add Link
                     links.append({
                         "source": child.id,
                         "target": start_node_id,
                         "label": "descendant"
                     })
        except Exception as e:
            logger.warning(f"Error fetching descendants: {e}")

        return {"nodes": list(nodes.values()), "links": links}

    def _format_node(self, nid, payload, group, val):
        return {
            "id": nid,
            "label": payload.get("name", "Unknown"),
            "group": group,
            "val": val,
            "breeder": payload.get("breeder"),
            "type": payload.get("type"),
            "image": payload.get("image"),
            # internal marker
            "payload_stub": payload 
        }
        
        # Cache Result
        self._lineage_cache[cache_key] = (time.time(), result)
        
        return result

    def clear(self) -> None:
        """Clear is not easily supported in persistent vector store without dropping collection."""
        pass
