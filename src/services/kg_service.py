
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
        
        target_collection = collection_name
        if not target_collection:
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

        # Batch fetch missing nodes
        all_node_ids = set(nodes.keys())
        target_ids = {l["target"] for l in links}
        missing_ids = list(target_ids - all_node_ids)
        
        if missing_ids:
             # Just loop for now
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

    async def get_lineage(self, strain_name: str, depth: int = 10, collection_name: str = "strain_genetics") -> Dict[str, Any]:
        """
        Retrieves the genealogy/lineage of a strain using Batched BFS on `strain_genetics`.
        Supports complex nested trees via `resolved_parents` and `html_tree` data.
        """
        import time
        cache_key = (strain_name, depth, collection_name)
        if cache_key in self._lineage_cache:
            ts, data = self._lineage_cache[cache_key]
            if time.time() - ts < self._cache_ttl:
                return data
            else:
                del self._lineage_cache[cache_key]

        target_collection = collection_name
        
        # 1. Resolve Start Node by Name (Exact Match via QdrantService which normalizes)
        start_payload = self.qdrant.get_strain_lineage(strain_name)
        
        if not start_payload:
            # Fallback 1: Try "Auto" suffix variants purely on name logic
            suffixes = [" Auto", " Automatic", " Feminized", " Fem"]
            for s in suffixes:
                if strain_name.lower().endswith(s.lower()):
                    variant = strain_name[0:-len(s)].strip()
                    start_payload = self.qdrant.get_strain_lineage(variant)
                    if start_payload: 
                        logger.info(f"Resolved '{strain_name}' to variant '{variant}'")
                        break
        
        if not start_payload:
            # Fallback 2: Vector Search (Fuzzy Match / Typo Tolerance)
            # This handles "Zams Poison" -> "Zam's Poison"
            logger.info(f"Direct match failed for '{strain_name}'. Attempting vector search in {target_collection}...")
            try:
                # Use the 384-dim embedder consistent with this collection
                query_vector = await self.embedder.embed_query_384(strain_name)
                
                # Search specifically in the strain collection
                results = self.qdrant.search_entities(
                    query_vector, 
                    limit=1, 
                    score_threshold=0.85, 
                    collection_name=target_collection
                )
                
                if results:
                    start_payload = results[0].payload
                    resolved_name = start_payload.get("name")
                    logger.info(f"Fuzzy match resolved: '{strain_name}' -> '{resolved_name}' (Score: {results[0].score:.4f})")
            except Exception as e:
                logger.error(f"Fuzzy search failed: {e}")

        if not start_payload:
            logger.warning(f"Lineage: Strain '{strain_name}' not found in {target_collection}.")
            return {"nodes": [], "links": []}

        start_node_id = start_payload.get("uuid")

        # 2. Batched BFS Traversal
        nodes = {}
        links = []
        visited = set([start_node_id])
        
        # Init Start Node
        nodes[start_node_id] = self._format_node(start_node_id, start_payload, "Target", 20)
        
        current_layer_ids = [start_node_id]
        
        # Pre-load start payload
        layer_payloads = {start_node_id: start_payload}

        for d in range(depth):
            if not current_layer_ids:
                break
            
            if len(nodes) > 200:
                logger.warning(f"Lineage limit 200 reached. Stopping traversal.")
                break

            # Need to fetch payloads for IDs that we only have stubs for
            ids_to_fetch = [nid for nid in current_layer_ids if nid not in layer_payloads]
            
            if ids_to_fetch:
                try:
                    results = self.qdrant.client.retrieve(
                        collection_name=target_collection,
                        ids=ids_to_fetch,
                        with_payload=True
                    )
                    for point in results:
                        layer_payloads[point.id] = point.payload
                except Exception as e:
                    logger.error(f"Batch retrieve failed: {e}")

            next_layer_ids = []
            
            for pid in current_layer_ids:
                payload = layer_payloads.get(pid)
                if not payload: continue

                # Update Node Details (Full Enrichment)
                if pid in nodes:
                    if not nodes[pid].get("breeder") and payload.get("breeders"):
                         bs = payload.get("breeders")
                         nodes[pid]["breeder"] = ", ".join(bs) if isinstance(bs, list) else str(bs)
                    if not nodes[pid].get("description"):
                         nodes[pid]["description"] = payload.get("description", "")
                    if payload.get("html_tree"):
                         nodes[pid]["html_tree"] = payload.get("html_tree")
                    
                    # Store resolved parents for frontend inspection if needed
                    # nodes[pid]["parents_data"] = payload.get("parents", [])

                # Get Parents (Upstream)
                parents = payload.get("resolved_parents", [])
                
                for p in parents:
                    p_id = p.get("id")
                    p_name = p.get("name")
                    
                    # Loop Check
                    if p_id == pid: continue 

                    if p_id and p_id not in visited:
                        visited.add(p_id)
                        next_layer_ids.append(p_id)
                        
                        nodes[p_id] = {
                            "id": p_id,
                            "label": p_name,
                            "group": "Ancestor",
                            "val": 10,
                            "type": "Strain",
                        }
                        
                        links.append({
                            "source": pid,
                            "target": p_id,
                            "label": "bred_from"
                        })
                        
                        if len(nodes) > 200:
                             break
                    elif p_id and p_id in nodes:
                         # Link to existing node
                         # Check dup link (inefficient linear check but graph is small)
                         exists = any(l for l in links if l["source"] == pid and l["target"] == p_id)
                         if not exists:
                             links.append({
                                "source": pid,
                                "target": p_id,
                                "label": "bred_from"
                            })

            current_layer_ids = next_layer_ids
            layer_payloads = {} # Clear for next iter
        
        result = {"nodes": list(nodes.values()), "links": links}
        self._lineage_cache[cache_key] = (time.time(), result)
        return result

    def _format_node(self, nid, payload, group, val):
        return {
            "id": nid,
            "label": payload.get("name", "Unknown"),
            "group": group,
            "val": val,
            "breeder": ", ".join(payload.get("breeders", [])) if isinstance(payload.get("breeders"), list) else payload.get("breeder"),
            "type": payload.get("type"),
            "image": payload.get("image"),
            "payload_stub": payload 
        }

    def clear(self) -> None:
        """Clear is not easily supported in persistent vector store without dropping collection."""
        pass
