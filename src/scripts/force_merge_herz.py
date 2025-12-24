
import asyncio
import sys
from pathlib import Path
from qdrant_client import models

sys.path.append(str(Path(__file__).parent.parent.parent))
from src.services.kg_service import KnowledgeGraphService

async def main():
    kg = KnowledgeGraphService()
    client = kg.qdrant.client
    collection = "botanical_entities"
    
    print("--- DIAGNOSTIC: Herz OG Auto Merge ---")
    
    # 1. Find the Master (Herz OG)
    master_res = client.scroll(
        collection_name=collection,
        scroll_filter=models.Filter(must=[models.FieldCondition(key="name", match=models.MatchValue(value="Herz OG"))]),
        limit=1,
        with_payload=True
    )[0]
    
    if not master_res:
        print("CRITICAL: 'Herz OG' (Master) NOT FOUND!")
        return
    master = master_res[0]
    master_id = master.id
    print(f"Master found: {master.payload.get('name')} ({master_id})")

    # 2. Find the Slave (Herz OG Auto)
    slave_res = client.scroll(
        collection_name=collection,
        scroll_filter=models.Filter(must=[models.FieldCondition(key="name", match=models.MatchValue(value="Herz OG Auto"))]),
        limit=1,
        with_payload=True
    )[0]
    
    slave_id = None
    if slave_res:
        slave = slave_res[0]
        slave_id = slave.id
        print(f"Slave found: {slave.payload.get('name')} ({slave_id})")
    else:
        print("Slave 'Herz OG Auto' NOT FOUND (Already merged?)")
        
        # If not found, we check if ZZZ... still points to the OLD slave ID or the NEW Master ID
        # We need to find ZZZ...
        pass

    # 3. Find 'ZZZ...' (The strain pointing to it)
    # Search for anything starting with ZZZ
    zzz_res = client.scroll(
        collection_name=collection,
        scroll_filter=models.Filter(must=[models.FieldCondition(key="name", match=models.MatchText(text="ZZZ"))]),
        limit=10,
        with_payload=True
    )[0]
    
    print(f"\nScanning {len(zzz_res)} candidates for links...")
    
    for point in zzz_res:
        name = point.payload.get("name")
        relations = point.payload.get("relations", [])
        
        updated = False
        new_relations = []
        
        for r in relations:
            target_label = r.get("target_label", "")
            target_id = r.get("target_id")
            
            # Check if it points to "Herz OG Auto" (by name or ID)
            if "Herz OG Auto" in target_label or (slave_id and target_id == slave_id):
                print(f"  [FIX] Found broken link in '{name}': {r}")
                
                # Re-point to Master
                r["target_id"] = master_id
                r["target_label"] = "Herz OG"
                print(f"        -> Rewired to: {r}")
                updated = True
                
            new_relations.append(r)
            
        if updated:
            print(f"  Saving updates to '{name}'...")
            client.set_payload(
                collection_name=collection,
                payload={"relations": new_relations},
                points=[point.id]
            )
            print("  Success!")
        else:
            print(f"  No broken links found in '{name}'.")

    # 4. Cleanup Slave if it exists
    if slave_id:
        print(f"\nDeleting Slave entity: {slave_id}")
        client.delete(collection_name=collection, points_selector=models.PointIdsList(points=[slave_id]))
        print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
