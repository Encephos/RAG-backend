
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
    
    print("--- Inspecting 'Herz OG' vs 'Herz OG Auto' ---")
    
    # Fetch Herz OG
    herz = kg.qdrant.client.scroll(
        collection_name=collection,
        scroll_filter=models.Filter(
            must=[models.FieldCondition(key="name", match=models.MatchValue(value="Herz OG"))]
        ),
        limit=1,
        with_payload=True
    )[0]
    
    # Fetch Herz OG Auto
    herz_auto = kg.qdrant.client.scroll(
        collection_name=collection,
        scroll_filter=models.Filter(
            must=[models.FieldCondition(key="name", match=models.MatchValue(value="Herz OG Auto"))]
        ),
        limit=1,
        with_payload=True
    )[0]
    
    if herz:
        h = herz[0]
        print(f"Herz OG: ID={h.id} | Relations={len(h.payload.get('relations', []))}")
    else:
        print("Herz OG: NOT FOUND")
        
    if herz_auto:
        ha = herz_auto[0]
        print(f"Herz OG Auto: ID={ha.id} | Relations={len(ha.payload.get('relations', []))}")
    else:
        print("Herz OG Auto: NOT FOUND")
        
    if herz and herz_auto:
        if herz[0].id != herz_auto[0].id:
            print(f"\n!! MISMATCH: They are separate entities! !!")
            print("This explains why the lineage breaks. 'Herz OG Auto' (child of ZZZ) has no parents, while 'Herz OG' has the full tree.")
        else:
            print("\nThey are the same entity.")

if __name__ == "__main__":
    asyncio.run(main())
