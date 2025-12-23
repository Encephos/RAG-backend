import sys
import os
import asyncio
from typing import List

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.qdrant_service import QdrantService
from src.services.embedding_service import EmbeddingService

async def main():
    qdrant = QdrantService()
    embedder = EmbeddingService()
    
    query = "Entourage Effect"
    print(f"--- Debugging RAG Retrieval for: '{query}' ---")
    
    # 1. Embed with 768 model
    print("Generating 768-dim embedding...")
    vec_768 = await embedder.embed_query(query)
    
    # 2. Embed with 384 model (Legacy fallback check)
    print("Generating 384-dim embedding...")
    vec_384 = await embedder.embed_query_384(query)

    collections_to_check = [
        ("master_collection_768", vec_768),
        ("studies_data_768", vec_768),
        ("botanical_knowledge_768", vec_768),
        # Check Legacy too just in case
        ("master_collection", vec_384),
        ("studies_data", vec_384)
    ]

    for col_name, vec in collections_to_check:
        print(f"\nChecking Collection: {col_name}...")
        try:
            # Check count first
            count_res = qdrant.client.count(collection_name=col_name)
            print(f"  Total Points: {count_res.count}")
            
            if count_res.count == 0:
                print("  -> EMPTY")
                continue

            results = qdrant.client.query_points(
                collection_name=col_name,
                query=vec,
                limit=3,
                with_payload=True
            ).points
            
            if not results:
                print("  -> NO MATCHES found.")
            else:
                for hit in results:
                    text = hit.payload.get("text", "")[:100].replace("\n", " ") + "..."
                    print(f"  - Score: {hit.score:.4f} | Text: {text}")
                    
        except Exception as e:
            print(f"  -> Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
