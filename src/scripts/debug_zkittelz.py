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
                        
    # Check Non-Suffixed / 384 Collections
    collections_check = ["botanical_entities", "rag_entities", "botanical_knowledge", "botanical_entities_384"]
    
    from qdrant_client import models
    
    for col in collections_384:
        logger.info(f"--- Checking 384 Collection: {col} ---")
        try:
            # We cannot do vector search because our current model is likely 768.
            # So we perform a Scroll with a Filter for the name.
            
            for name in VARIATIONS:
                 scroll_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="name",
                            match=models.MatchValue(value=name)
                        )
                    ]
                )
                 res = kg.qdrant.client.scroll(
                     collection_name=col,
                     scroll_filter=scroll_filter,
                     limit=5
                 )
                 points = res[0]
                 
                 if points:
                     for p in points:
                         logger.info(f"  MATCH FOUND in {col}: {p.payload.get('name')}")
                 else:
                     logger.info(f"  No exact match for {name}")
                     
        except Exception as e:
            logger.warning(f"  Collection {col} likely does not exist or error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
