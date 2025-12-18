
import asyncio
import os
import sys

# Setup path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)

# Try connecting to the user's server
HOST = "95.216.204.29"
PORT = 6333

async def main():
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models
    except ImportError:
        print("Please install qdrant-client")
        return

    print(f"Connecting to Qdrant at {HOST}:{PORT}...")
    
    try:
        client = QdrantClient(host=HOST, port=PORT, timeout=5)
        # Check connection
        cols = client.get_collections()
        print(f"Connected successfully. Collections: {[c.name for c in cols.collections]}")
    except Exception as e:
        print(f"Remote Connection failed: {e}")
        return
    
    strain_name = "Z and Z Auto"
    print(f"Searching for: {strain_name}")
    
    try:
        response = client.scroll(
            collection_name="botanical_entities",
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="name",
                        match=models.MatchValue(value=strain_name)
                    )
                ]
            ),
            limit=1
        )
        
        points = response[0]
        
        if not points:
            print("Strain 'Z and Z Auto' NOT FOUND in Qdrant")
        else:
            point = points[0]
            relations = point.payload.get("relations", [])
            print(f"FOUND 'Z and Z Auto'. Relations Count: {len(relations)}")
            print(f"Relations: {relations}")

        # Check for Parent "Z3"
        print("\nChecking for parent 'Z3'...")
        response_parent = client.scroll(
            collection_name="botanical_entities",
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="name",
                        match=models.MatchValue(value="Z3")
                    )
                ]
            ),
            limit=1
        )
        if response_parent[0]:
            p_point = response_parent[0][0]
            print(f"FOUND 'Z3'. Relations Count: {len(p_point.payload.get('relations', []))}")
            print(f"Z3 Relations: {p_point.payload.get('relations', [])}")
        else:
            print("Parent 'Z3' NOT FOUND. Inferred ingestion failed.")

    except Exception as e:
        print(f"Search failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
