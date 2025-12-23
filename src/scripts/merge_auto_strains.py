
import asyncio
import sys
from pathlib import Path
from qdrant_client import models

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.services.kg_service import KnowledgeGraphService

async def main():
    kg_service = KnowledgeGraphService()
    client = kg_service.qdrant.client
    collection = "botanical_entities"
    
    print(f"Starting Auto-Strain Merge for collection: {collection}")
    
    # 1. Fetch ALL entities (Scroll)
    all_points = []
    next_offset = None
    
    print("Fetching all entities...")
    while True:
        points, next_offset = client.scroll(
            collection_name=collection,
            limit=1000,
            offset=next_offset,
            with_payload=True
        )
        all_points.extend(points)
        if next_offset is None:
            break
            
    print(f"Total entities fetched: {len(all_points)}")
    
    # 2. Index by Name for fast lookup
    name_map = {}
    for p in all_points:
        name = p.payload.get("name", "").strip()
        if name:
            name_map[name.lower()] = p

    # 3. Identify and Merge "Auto" variants
    suffixes = [" Auto", " Automatic", " Feminized", " Fem"]
    
    merges = 0
    ids_to_delete = []
    
    for auto_name_lower, auto_point in name_map.items():
        # Check if this is an "Auto" strain
        matched_suffix = None
        base_name_candidate = None
        
        for suffix in suffixes:
            if auto_name_lower.endswith(suffix.lower()):
                matched_suffix = suffix
                base_name_candidate = auto_name_lower[:-len(suffix)].strip()
                break
        
        if matched_suffix and base_name_candidate:
            # Check if Base exists
            if base_name_candidate in name_map:
                base_point = name_map[base_name_candidate]
                
                # We found a pair: "Herz OG Auto" (Slave) -> "Herz OG" (Master)
                print(f"Merging '{auto_point.payload.get('name')}' -> '{base_point.payload.get('name')}'")
                
                slave_id = auto_point.id
                master_id = base_point.id
                
                if slave_id == master_id:
                    continue

                # A. Update pointers (Graph Rewiring)
                # Find anyone pointing to Slave, re-point to Master
                # Since we have all points, we can iterate in memory!
                
                # (Optimized: In-memory relational update would be hard without iterating all Relations of all points.
                #  Since we have 1000s, let's just do a Qdrant Filter search for robustness)
                
                # Incoming relations (X -> Slave)
                incoming_points, _ = client.scroll(
                    collection_name=collection,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="relations.target_id",
                                match=models.MatchValue(value=slave_id)
                            )
                        ]
                    ),
                    limit=100
                )
                
                for inc in incoming_points:
                    inc_payload = inc.payload
                    inc_relations = inc_payload.get("relations", [])
                    updated = False
                    for r in inc_relations:
                        if r.get("target_id") == slave_id:
                            print(f"  - Rewiring {inc.payload.get('name')} to point to Master")
                            r["target_id"] = master_id
                            r["target_label"] = base_point.payload.get("name") # Update label too
                            updated = True
                    
                    if updated:
                        client.set_payload(
                            collection_name=collection,
                            payload={"relations": inc_relations},
                            points=[inc.id]
                        )

                # B. Merge Outgoing Relations (Slave -> Y) to Master
                master_payload = base_point.payload
                master_relations = master_payload.get("relations", [])
                slave_relations = auto_point.payload.get("relations", [])
                
                for s_rel in slave_relations:
                    # Check if exists in master
                    exists = False
                    for m_rel in master_relations:
                        if m_rel.get("target_id") == s_rel.get("target_id") and m_rel.get("type") == s_rel.get("type"):
                            exists = True
                            break
                    if not exists:
                        print(f"  - Moving relation {s_rel.get('type')}->{s_rel.get('target_label')} to Master")
                        master_relations.append(s_rel)
                
                # C. Merge Metadata
                # Prefer Master, fill gaps from Slave
                for k, v in auto_point.payload.items():
                    if k not in master_payload or not master_payload[k]:
                        if k not in ["id", "relations", "name"]:
                            master_payload[k] = v
                
                master_payload["relations"] = master_relations
                
                # Update Master
                client.set_payload(
                    collection_name=collection,
                    payload=master_payload,
                    points=[master_id]
                )
                
                ids_to_delete.append(slave_id)
                merges += 1
                
    # 4. Delete Slaves
    if ids_to_delete:
        print(f"\nDeleting {len(ids_to_delete)} merged 'Auto' entities...")
        # Delete in batches of 100
        batch_size = 100
        for i in range(0, len(ids_to_delete), batch_size):
            batch = ids_to_delete[i:i+batch_size]
            client.delete(
                collection_name=collection,
                points_selector=models.PointIdsList(points=batch)
            )
        print("Delete complete.")
    
    print(f"\nMerge pipeline finished. Merged {merges} entities.")

if __name__ == "__main__":
    asyncio.run(main())
