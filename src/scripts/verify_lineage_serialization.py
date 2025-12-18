
import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.services.kg_service import KnowledgeGraphService

async def main():
    service = KnowledgeGraphService()
    
    # Mock Qdrant and Embedder to avoid needing a running DB for this unit-like verification
    service.embedder.embed_query = AsyncMock(return_value=[0.1] * 384)
    
    mock_start_node = MagicMock()
    mock_start_node.id = "id_1"
    mock_start_node.payload = {
        "name": "White Widow",
        "breeder": "Green House Seeds",
        "thc": "20%",
        "type": "Hybrid",
        "relations": [{"target_id": "id_2", "type": "bred_from"}]
    }
    
    mock_parent_node = {
        "name": "Brazilian Sativa",
        "breeder": "Nature",
        "type": "Sativa",
        "relations": []
    }

    # Mock search result for start node
    service.qdrant.search_entities = MagicMock(return_value=[mock_start_node])
    
    # Mock get_entity for parent
    service.qdrant.get_entity = MagicMock(side_effect=lambda id, **kwargs: mock_parent_node if id == "id_2" else {})

    print("Fetching lineage for White Widow...")
    result = await service.get_lineage("White Widow")
    
    nodes = result["nodes"]
    print(f"Found {len(nodes)} nodes.")
    
    white_widow = next((n for n in nodes if n["label"] == "White Widow"), None)
    parent = next((n for n in nodes if n["label"] == "Brazilian Sativa"), None)
    
    if white_widow:
        print(f"White Widow Breeder: {white_widow.get('breeder')}")
        print(f"White Widow THC: {white_widow.get('thc')}")
        if white_widow.get('breeder') == "Green House Seeds" and white_widow.get('thc') == "20%":
             print("SUCCESS: White Widow data incorrect.")
        else:
             print("FAILURE: White Widow data missing/incorrect.")
             
    if parent:
        print(f"Parent Breeder: {parent.get('breeder')}")
        if parent.get('breeder') == "Nature":
            print("SUCCESS: Parent data correct.")
        else:
            print("FAILURE: Parent data missing.")

if __name__ == "__main__":
    asyncio.run(main())
