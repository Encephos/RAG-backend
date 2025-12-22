import asyncio
import csv
import sys
import os
import logging
from qdrant_client.http import models

# Add project root to path
sys.path.append(os.getcwd())

from src.services.qdrant_service import QdrantService
from src.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CSV_PATH = "scrape_data/scrape/cannabis-strains-final.csv"
FILENAME = "cannabis-strains-final.csv"

async def main():
    if not os.path.exists(CSV_PATH):
        logger.error(f"CSV not found: {CSV_PATH}")
        return

    # 1. Count CSV Rows
    csv_count = 0
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        csv_count = sum(1 for row in reader)
    
    logger.info(f"CSV '{FILENAME}' contains {csv_count} rows.")

    # 2. Check Qdrant
    qdrant = QdrantService()
    collection_name = qdrant.collections["botanical"] # botanical_knowledge_768
    
    logger.info(f"Checking collection '{collection_name}' for items with source='{FILENAME}'...")
    
    try:
        # Create filter
        scroll_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="source",
                    match=models.MatchValue(value=FILENAME)
                )
            ]
        )
        
        # Count points matching filter
        # Note: qdrant-client python `count` method supports filtering
        count_result = qdrant.client.count(
            collection_name=collection_name,
            count_filter=scroll_filter
        )
        
        db_count = count_result.count
        logger.info(f"Found {db_count} items in Qdrant with source='{FILENAME}'.")
        
        if db_count == 0:
            logger.info("RESULT: NOT ingested.")
        elif db_count < csv_count:
            logger.info(f"RESULT: PARTIALLY ingested ({db_count}/{csv_count}).")
        else:
            logger.info(f"RESULT: FULLY ingested ({db_count}/{csv_count}).") # Could be more if duplicates or re-runs
            
    except Exception as e:
        logger.error(f"Error checking Qdrant: {e}")
        logger.info("Ensure SSH tunnel is active or use 'docker exec' to run this script.")

if __name__ == "__main__":
    asyncio.run(main())
