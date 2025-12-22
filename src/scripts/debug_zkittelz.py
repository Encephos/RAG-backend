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
    
    # 1. Check if Collection Exists and has items
    try:
        count = kg.qdrant.client.count("botanical_entities_768").count
        logger.info(f"COUNT in 'botanical_entities_768': {count}")
    except Exception as e:
        logger.error(f"Collection 'botanical_entities_768' check failed: {e}")

    # 2. Search for Strain
    logger.info(f"Searching for '{STAIN_NAME}' in botanical_entities_768...")
    
    col = "botanical_entities_768"
    try:
         # Try variations
         for name in VARIATIONS:
            logger.info(f"Checking for '{name}'...")
            vec = await kg.embedder.embed_query(name)
            
            # Check matches with score
            points = kg.qdrant.search_entities(vec, limit=5, score_threshold=0.60, collection_name=col)
            
            if not points:
                logger.info(f"  No vector matches for {name} > 0.60")
                
                # FALLBACK: Check exact name via Scroll (maybe embedding is weird?)
                from qdrant_client import models
                scroll_filter = models.Filter(
                    must=[models.FieldCondition(key="name", match=models.MatchValue(value=name))]
                )
                res = kg.qdrant.client.scroll(collection_name=col, scroll_filter=scroll_filter, limit=1)
                if res[0]:
                     p_exact = res[0][0]
                     logger.info(f"  BUT found via EXACT NAME match! ID: {p_exact.id}")
                     logger.info(f"  Payload keys: {list(p_exact.payload.keys())}")
                     logger.info(f"  'text' field content: '{p_exact.payload.get('text', 'MISSING')}'")
                     logger.info(f"  'name' field: '{p_exact.payload.get('name', 'MISSING')}'")
                     logger.info(f"  'description' (start): '{str(p_exact.payload.get('description', 'MISSING'))[:50]}'")
                else:
                     logger.info(f"  And NO exact name match found.")
                     
            else:
                for p in points:
                    logger.info(f"  MATCH FOUND: {p.payload.get('name')} (Score: {p.score})")
                    logger.info(f"  ID: {p.id}")
                    logger.info(f"  Relations: {len(p.payload.get('relations', []))}")
                    if p.payload.get('relations'):
                         for r in p.payload.get('relations')[:3]:
                             logger.info(f"    - {r}")

    except Exception as e:
        logger.error(f"Error checking {col}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
