
import asyncio
import sys
from collections import defaultdict
from pathlib import Path
from qdrant_client import models

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.services.kg_service import KnowledgeGraphService
from src.core.config import settings

async def main():
    kg_service = KnowledgeGraphService()
    # We must access the client directly for scroll/delete operations
    client = kg_service.qdrant.client
    collection = "botanical_entities"
    
    print(f"Starting deduplication for collection: {collection}")
    
    # 1. Fetch ALL entities (Scroll)
    # Note: For huge datasets, we should process in batches or use scroll with cursor.
    # Assuming < 10k entities for now, or we iterate.
    
    all_points = []
    next_offset = None
    
    print("Fetching all entities...")
    while True:
        points, next_offset = client.scroll(
            collection_name=collection,
            limit=1000,
            offset=next_offset,
            with_payload=True,
            with_vectors=True # Needed if we want to preserve vector of master?
        )
        all_points.extend(points)
        if next_offset is None:
            break
            
    print(f"Total entities fetched: {len(all_points)}")
    
    # 2. Group by Name (Case Insensitive)
    grouped = defaultdict(list)
    for p in all_points:
        name = p.payload.get("name", "").strip()
        if name:
            grouped[name.lower()].append(p)
            
    # 3. Identify Duplicates
    duplicates = {k: v for k, v in grouped.items() if len(v) > 1}
    print(f"Found {len(duplicates)} duplicate groups.")
    
    merges_log = []
    ids_to_delete = []
    
    for name_key, group in duplicates.items():
        print(f"\nProcessing duplicates for: '{name_key}' ({len(group)} entities)")
        
        # Strategy: Prefer "Cannabis Strain" (SeedFinder) over "Strain" (New Ingest)
        # Sort group: 'Cannabis Strain' first, then by Relation Count descending
        def sort_key(point):
            p = point.payload
            type_score = 10 if p.get("type") == "Cannabis Strain" else 5
            rel_count = len(p.get("relations", []))
            return (type_score, rel_count)
            
        group.sort(key=sort_key, reverse=True)
        
        master = group[0]
        slaves = group[1:]
        
        master_id = master.id
        master_payload = master.payload
        master_relations = master_payload.get("relations", [])
        
        print(f"  Master: {master_id} ({master_payload.get('type')})")
        
        for slave in slaves:
            slave_id = slave.id
            slave_payload = slave.payload
            print(f"  Merging Slave: {slave_id} ({slave_payload.get('type')})")
            
            # A. Merge Payload Fields (Keep Master if exists, else take Slave)
            for k, v in slave_payload.items():
                if k not in master_payload or not master_payload[k]:
                    if k not in ["id", "relations"]:
                        master_payload[k] = v
                        # print(f"    + Added field {k}")

            # B. Merge Outgoing Relations (Master -> X)
            slave_relations = slave_payload.get("relations", [])
            for s_rel in slave_relations:
                # Check if this relation already exists in Master
                exists = False
                for m_rel in master_relations:
                    if m_rel.get("target_id") == s_rel.get("target_id") and m_rel.get("type") == s_rel.get("type"):
                        exists = True
                        break
                
                if not exists:
                    master_relations.append(s_rel)
                    print(f"    + Added relation: {s_rel.get('type')} -> {s_rel.get('target_id')}")

            # C. Track Incoming Relations (X -> Slave) to update them to (X -> Master)
            # We can't do this easily here without a full index or separate query.
            # We will handle this in a separate pass or immediate query.
            # Immediate Query to find anyone pointing to Slave
            
            # Find points where relations.target_id == slave_id
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
            
            if incoming_points:
                print(f"    Updating {len(incoming_points)} incoming references...")
                for inc in incoming_points:
                    inc_payload = inc.payload
                    inc_relations = inc_payload.get("relations", [])
                    updated = False
                    for r in inc_relations:
                        if r.get("target_id") == slave_id:
                            r["target_id"] = master_id
                            updated = True
                    
                    if updated:
                        client.set_payload(
                            collection_name=collection,
                            payload={"relations": inc_relations},
                            points=[inc.id]
                        )
            
            ids_to_delete.append(slave_id)

        # Update Master Payload
        master_payload["relations"] = master_relations
        client.set_payload(
            collection_name=collection,
            payload=master_payload,
            points=[master_id]
        )
        merges_log.append(f"Merged {len(slaves)} into {master_id} for '{name_key}'")

    # 4. Delete Slaves
    if ids_to_delete:
        print(f"\nDeleting {len(ids_to_delete)} duplicate entities...")
        client.delete(
            collection_name=collection,
            points_selector=models.PointIdsList(points=ids_to_delete)
        )
        print("Delete complete.")
    else:
        print("\nNo duplicates to delete.")
        
    print("\nDeduplication finished.")

if __name__ == "__main__":
    asyncio.run(main())
