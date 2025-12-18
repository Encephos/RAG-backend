
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
            print("Strain NOT FOUND in Qdrant 'botanical_entities' collection.")
            return

        point = points[0]
        print(f"Found Entity ID: {point.id}")
        print("Payload Keys:", point.payload.keys())
        
        relations = point.payload.get("relations", [])
        print(f"Relations Count: {len(relations)}")
        print("Relations Data:", relations)
        
        if not relations:
            print("WARNING: No relations found in payload!")
            
    except Exception as e:
        print(f"Search failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
