
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
    
    target = "Sour Diesel"
    print(f"--- Inspecting Relations for '{target}' ---")
    
    # Fetch Entity
    res = client.scroll(
        collection_name=collection,
        scroll_filter=models.Filter(must=[models.FieldCondition(key="name", match=models.MatchValue(value=target))]),
        limit=1,
        with_payload=True
    )[0]
    
    if not res:
        print(f"'{target}' NOT FOUND.")
        return
        
    entity = res[0]
    relations = entity.payload.get("relations", [])
    
    print(f"Total Relations: {len(relations)}")
    
    parent_rels = [r for r in relations if r.get("type") in ["bred_from", "has_parent", "cross_of"]]
    print(f"Parent Relations: {len(parent_rels)}")
    
    for r in parent_rels:
        t_id = r.get("target_id")
        t_label = r.get("target_label")
        print(f"  - ID: {t_id} | Label: '{t_label}'")
        
        # Check if ID exists
        try:
            chk = client.retrieve(collection_name=collection, ids=[t_id])
            if chk:
                print(f"    -> Exists. Name in DB: '{chk[0].payload.get('name')}'")
            else:
                print(f"    -> DOES NOT EXIST (Dangling)")
        except:
            print("    -> Error checking ID")

if __name__ == "__main__":
    asyncio.run(main())
