import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.services.kg_service import KnowledgeGraphService
from src.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STAIN_NAME = "Zkittelz" # Or try Zkittlez as commonly spelled?

async def main():
    kg = KnowledgeGraphService()
    
    # 1. Search for Strain
    logger.info(f"Searching for '{STAIN_NAME}' in botanical entities...")
    
    # Try multiple collections just in case
    for col in ["botanical_entities_768", settings.QDRANT_ENTITY_COLLECTION_NAME]:
        logger.info(f"--- Collection: {col} ---")
        try:
            # We use the embedding service from KG service
            vec = await kg.embedder.embed_query(STAIN_NAME)
            points = kg.qdrant.search_entities(vec, limit=3, score_threshold=0.80, collection_name=col)
            
            if not points:
                logger.info("  No matches found.")
            else:
                for p in points:
                    logger.info(f"  Match: {p.payload.get('name')} (Score: {p.score})")
                    logger.info(f"  ID: {p.id}")
                    logger.info(f"  Relations: {len(p.payload.get('relations', []))}")
                    for r in p.payload.get('relations', []):
                        logger.info(f"    - {r.get('type')} -> {r.get('target_label') or r.get('target_id')}")
        except Exception as e:
            logger.error(f"Error checking {col}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
