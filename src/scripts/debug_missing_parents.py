
import asyncio
import sys
from pathlib import Path
from qdrant_client import models

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.services.kg_service import KnowledgeGraphService

async def main():
    kg = KnowledgeGraphService()
    client = kg.qdrant.client
    collection = "botanical_entities"
    
    strains_to_check = ["Z3", "Monster Mash"]
    
    for name in strains_to_check:
        print(f"\n--- Checking '{name}' ---")
        
        # 1. Fetch Entity
        results = client.scroll(
            collection_name=collection,
            scroll_filter=models.Filter(must=[models.FieldCondition(key="name", match=models.MatchValue(value=name))]),
            limit=1,
            with_payload=True
        )[0]
        
        if not results:
            print(f"  Entity '{name}' NOT FOUND!")
            continue
            
        entity = results[0]
        print(f"  ID: {entity.id}")
        
        # 2. Inspect Relations
        relations = entity.payload.get("relations", [])
        print(f"  Relation Count: {len(relations)}")
        
        found_parents = False
        
        for r in relations:
            rtype = r.get("type")
            target_id = r.get("target_id")
            target_label = r.get("target_label", "Unknown")
            
            # Check if target exists
            target_exists = False
            try:
                t_res = client.retrieve(collection_name=collection, ids=[target_id])
                if t_res:
                    target_exists = True
            except:
                pass
                
            status_str = "OK" if target_exists else "DANGLING (Target ID not found)"
            
            if rtype in ["bred_from", "has_parent", "cross_of"]:
                found_parents = True
                print(f"    - [PARENT] {rtype} -> {target_label} ({target_id}) [{status_str}]")
            else:
                print(f"    - {rtype} -> {target_label} ({target_id}) [{status_str}]")
                
        if not found_parents:
            print("  NO PARENT RELATIONS FOUND (bred_from, has_parent, etc.)")
            
            # 3. Check Incoming Parent_Of
            # Does anyone claim to be the parent of this entity?
            print("  Checking for incoming 'parent_of' relations...")
            incoming, _ = client.scroll(
                collection_name=collection,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(key="relations.target_id", match=models.MatchValue(value=entity.id)),
                        models.FieldCondition(key="relations.type", match=models.MatchValue(value="parent_of"))
                    ]
                ),
                limit=10,
                with_payload=True
            )
            
            if incoming:
                print(f"  Found {len(incoming)} entities claiming to be parent of {name}:")
                for p in incoming:
                    print(f"    - {p.payload.get('name')} ({p.id})")
            else:
                print("  No incoming parents found.")

if __name__ == "__main__":
    asyncio.run(main())
