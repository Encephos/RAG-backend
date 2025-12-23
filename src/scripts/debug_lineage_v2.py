
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
    
    print("=== TEST 1: Herz OG Auto Lookup ===")
    query = "Herz OG Auto"
    
    # 1. Vector Search Raw Score
    embedding = await kg.embedder.embed_query_384(query)
    results = kg.qdrant.client.search(
        collection_name=collection,
        query_vector=embedding,
        limit=5,
        with_payload=True
    )
    
    print(f"Vector Search for '{query}':")
    for hit in results:
        print(f"  - {hit.payload.get('name')} (Score: {hit.score})")

    # 2. Heuristic Check (Strip 'Auto')
    stripped = query.replace("Auto", "").strip()
    print(f"Checking stripped name '{stripped}'...")
    results_stripped = kg.qdrant.client.scroll(
         collection_name=collection,
         scroll_filter=models.Filter(
             must=[models.FieldCondition(key="name", match=models.MatchValue(value=stripped))]
         ),
         limit=1
    )[0]
    if results_stripped:
        print(f"  FOUND by stripping Auto: {results_stripped[0].payload.get('name')}")
    else:
        print("  Not found by stripping Auto.")


    print("\n=== TEST 2: Herz OG Lineage Size ===")
    # Simulate get_lineage for "Herz OG"
    try:
        # We know Herz OG exists from prev debug
        lineage = await kg.get_lineage("Herz OG", depth=10, collection_name=collection)
        nodes = lineage.get("nodes", [])
        links = lineage.get("links", [])
        print(f"Lineage Result for 'Herz OG':")
        print(f"  - Node Count: {len(nodes)}")
        print(f"  - Link Count: {len(links)}")
        
        # Check for cycles or duplicates in output
        node_ids = set()
        for n in nodes:
            if n['id'] in node_ids:
                print(f"  !! DUPLICATE NODE IN OUTPUT: {n['id']} !!")
            node_ids.add(n['id'])
            
        print("  - Leaf nodes (Landraces?):")
        for n in nodes:
            # A leaf in this ancestry direction means no parents
            # Check if this node is a source in any link? 
            # In bred_from, Source is Child, Target is Parent.
            # So a node is a 'landrace' if it is never a SOURCE in a link (meaning it has no parents)?
            # Wait, no. If A bred_from B. A is source, B is target.
            # If B has no parents, B is never a source in any 'bred_from' link.
            
            is_child = False
            for l in links:
                if l['source'] == n['id']:
                     is_child = True
                     break
            if not is_child:
                print(f"    - {n['label']} (No recorded parents in graph)")

    except Exception as e:
        print(f"!! Error fetching lineage: {e}")


    print("\n=== TEST 3: Z3 (ZZZ...) Lineage Size ===")
    try:
        lineage = await kg.get_lineage("Z3", depth=20, collection_name=collection)
        nodes = lineage.get("nodes", [])
        print(f"Lineage Result for 'Z3':")
        print(f"  - Node Count: {len(nodes)}")
        if len(nodes) >= 60:
             print("  !! HIT SAFETY LIMIT (60) !!")

    except Exception as e:
        print(f"!! Error fetching lineage: {e}")

if __name__ == "__main__":
    asyncio.run(main())
