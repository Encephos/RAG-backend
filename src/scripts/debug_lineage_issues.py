
import asyncio
import sys
from pathlib import Path
from qdrant_client import models

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.services.kg_service import KnowledgeGraphService

async def main():
    kg = KnowledgeGraphService()
    collection = "botanical_entities"
    
    # 1. Inspect "Z3" for Cycles
    print("--- Inspecting 'Z3' for Cycles ---")
    z3_results = kg.qdrant.client.scroll(
        collection_name=collection,
        scroll_filter=models.Filter(
            must=[models.FieldCondition(key="name", match=models.MatchValue(value="Z3"))]
        ),
        limit=10,
        with_payload=True
    )[0]
    
    if not z3_results:
        print("Z3 not found found in Qdrant.")
    else:
        for point in z3_results:
            print(f"Found Z3 Entity: ID={point.id}, Type={point.payload.get('type')}")
            relations = point.payload.get("relations", [])
            print(f"  Direct Relations ({len(relations)}):")
            for r in relations:
                print(f"    - {r.get('type')} -> {r.get('target_id')}")
                
                # Check 1 level deep to see if it points back to self
                target = kg.qdrant.client.retrieve(
                    collection_name=collection,
                    ids=[r.get("target_id")]
                )
                if target:
                    t_payload = target[0].payload
                    t_name = t_payload.get("name")
                    print(f"      -> Target Name: {t_name}")
                    t_rels = t_payload.get("relations", [])
                    for tr in t_rels:
                        if tr.get("target_id") == point.id:
                            print(f"      !!! CYCLE DETECTED !!! {t_name} points back to Z3")

    # 2. Inspect "Herz OG Auto"
    print("\n--- Inspecting 'Herz OG Auto' ---")
    herz_results = kg.qdrant.client.scroll(
        collection_name=collection,
        scroll_filter=models.Filter(
            must=[models.FieldCondition(key="name", match=models.MatchValue(value="Herz OG Auto"))]
        ),
        limit=10,
        with_payload=True
    )[0]
    
    if not herz_results:
         # Try partial match or "Herz OG"
         print("'Herz OG Auto' not found. Trying 'Herz OG'...")
         herz_results = kg.qdrant.client.scroll(
            collection_name=collection,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="name", match=models.MatchValue(value="Herz OG"))]
            ),
            limit=10,
            with_payload=True
        )[0]
         
    if herz_results:
        for point in herz_results:
            print(f"Found Entity: {point.payload.get('name')} (ID={point.id})")
            print(f"  Payload keys: {list(point.payload.keys())}")
            print(f"  Relations: {point.payload.get('relations')}")
    else:
        print("No entity found for Herz OG / Herz OG Auto.")

if __name__ == "__main__":
    asyncio.run(main())
