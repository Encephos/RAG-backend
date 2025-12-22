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

STAIN_NAME = "Zkittelz" 
VARIATIONS = ["Zkittlez", "Zkittles", "Zkittelz"] # Common spellings

async def main():
    kg = KnowledgeGraphService()
    
    # 1. Search for Strain
    logger.info(f"Searching for '{STAIN_NAME}' in botanical entities...")
    
    # Try multiple collections just in case
    for col in ["botanical_entities_768", settings.QDRANT_ENTITY_COLLECTION_NAME]:
        logger.info(f"--- Collection: {col} ---")
        try:
             # Try variations
             for name in VARIATIONS:
                logger.info(f"Checking for '{name}'...")
                vec = await kg.embedder.embed_query(name)
                # Lower threshold significantly to catch ANYTHING related
                points = kg.qdrant.search_entities(vec, limit=5, score_threshold=0.50, collection_name=col)
                
                if not points:
                    logger.info(f"  No matches found for {name} > 0.50")
                else:
                    for p in points:
                        logger.info(f"  MATCH FOUND: {p.payload.get('name')} (Score: {p.score})")
                        logger.info(f"  ID: {p.id}")
                        logger.info(f"  Type: {p.payload.get('type')}")
                        logger.info(f"  Payload keys: {list(p.payload.keys())}")
                        logger.info(f"  Relations: {len(p.payload.get('relations', []))}")
                        
        except Exception as e:
            logger.error(f"Error checking {col}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
