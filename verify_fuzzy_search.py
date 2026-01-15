import asyncio
import logging
from src.services.kg_service import KnowledgeGraphService
from src.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    kg = KnowledgeGraphService()
    
    # Test Case: Typo "Zams Poison" -> Should resolve to "Zam's Poison"
    strain_name = "Zams Poison"
    logger.info(f"Testing Fuzzy Search for: '{strain_name}' (Target: Zam's Poison)")
    
    # Debug: Perform raw search to see scores
    logger.info("--- DEBUG: Raw Vector Search ---")
    embedder = kg.embedder
    qdrant = kg.qdrant
    query_vector = await embedder.embed_query_384(strain_name)
    
    hits = qdrant.client.search(
        collection_name="strain_genetics",
        query_vector=query_vector,
        limit=5,
        with_payload=True
    )
    
    for hit in hits:
        logger.info(f"Candidate: {hit.payload.get('name')} | Score: {hit.score}")

    logger.info("--- End DEBUG ---")

    # Force use of strain_genetics collection
    result = await kg.get_lineage(strain_name, collection_name="strain_genetics")
    
    if result and result.get("nodes"):
        nodes = result.get("nodes")
        target_node = nodes[0]
        
        logger.info(f"Resolved Name: {target_node.get('label')}")
        if target_node.get('label') == "Zam's Poison":
             logger.info("SUCCESS: Fuzzy match worked!")
        else:
             logger.info(f"Result: {target_node.get('label')}")
    else:
        logger.warning(f"Strain '{strain_name}' NOT FOUND via get_lineage.")

if __name__ == "__main__":
    asyncio.run(main())
