
import asyncio
import sys
from pathlib import Path
from qdrant_client import models

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.services.kg_service import KnowledgeGraphService
from src.core.config import settings

async def main():
    kg_service = KnowledgeGraphService()
    collection = "botanical_entities"
    
    query = "Z3"
    print(f"Searching for '{query}' in {collection}...")
    
    # 1. Vector Search
    embedding = await kg_service.embedder.embed_query_384(query)
    search_results = kg_service.qdrant.client.search(
        collection_name=collection,
        query_vector=embedding,
        limit=5,
        with_payload=True
    )
    
    print("\n--- Vector Search Results ---")
    for hit in search_results:
        p = hit.payload
        print(f"ID: {hit.id} | Score: {hit.score:.4f} | Name: {p.get('name')} | Type: {p.get('type')}")
        relations = p.get('relations', [])
        print(f"  Relations ({len(relations)}):")
        for r in relations:
            print(f"    - {r.get('type')} -> {r.get('target_id')}")

    # 2. Exact Scroll Match
    print("\n--- Exact Name Match (Scroll) ---")
    scroll_results = kg_service.qdrant.client.scroll(
        collection_name=collection,
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="name",
                    match=models.MatchValue(value="Z3")
                )
            ]
        ),
        limit=5,
        with_payload=True
    )[0]
    
    for point in scroll_results:
        p = point.payload
        print(f"ID: {point.id} | Name: {p.get('name')} | Type: {p.get('type')}")
        relations = p.get('relations', [])
        print(f"  Relations ({len(relations)}):")
        for r in relations:
            print(f"    - {r.get('type')} -> {r.get('target_id')}")

if __name__ == "__main__":
    asyncio.run(main())
