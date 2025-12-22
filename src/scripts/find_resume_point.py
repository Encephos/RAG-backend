import asyncio
import csv
import sys
import os
import uuid
import logging

# Add project root to path
sys.path.append(os.getcwd())

from src.services.qdrant_service import QdrantService
from src.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CSV_PATH = "scrape_data/scrape/cannabis_studies_complete_2025_classified.csv"

async def main():
    if not os.path.exists(CSV_PATH):
        logger.error(f"CSV not found: {CSV_PATH}")
        return

    qdrant = QdrantService()
    
    # Read all rows first to have indices
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        total_rows = len(rows)
        logger.info(f"Loaded {total_rows} rows from CSV.")

    # We want to find the first index that is NOT in the DB.
    # Since ingestion is roughly sequential, we can check in steps.
    
    async def check_index(idx):
        if idx >= total_rows: return False
        row = rows[idx]
        title = row.get("study_title")
        if not title: return True # Skip empty
        
        # Calculate Deterministic ID (Same logic as ingest_studies.py)
        # Note: ingest_studies uses: entity_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, title))
        # AND it upserts points with the same ID logic for the Entity.
        # But for the vector point in 'studies_data_768', it uses: doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, text_content))
        # This is harder to replicate exactly without reconstructing the text content perfectly.
        
        # HOWEVER, the script ALSO ingests an Entity into `studies_entities_768` (mapped from 'studies').
        # The entity ID is purely based on title: 
        # entity_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, title))
        
        # Let's check the Entity Collection!
        entity_col = "studies_entities_768" # Default map locally, assuming server matches
        # Verify collection name from service
        entity_col = qdrant.entity_collections.get("studies", "studies_entities_768")
        
        entity_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, title))
        
        try:
            # We use retrieve (efficient by ID)
            res = qdrant.client.retrieve(collection_name=entity_col, ids=[entity_id])
            return len(res) > 0
        except Exception as e:
            logger.warning(f"Error validating index {idx}: {e}")
            return False

    # Heuristic Search
    # Check every 100th item to find roughly where chunks match
    logger.info("Scanning for last ingested item...")
    
    start_search = 0
    end_search = total_rows
    
    # Coarse check
    found_missing_block = False
    for i in range(0, total_rows, 100):
        exists = await asyncio.to_thread(lambda: asyncio.run(check_index(i))) if False else await check_index(i) 
        # (asyncio run trickery not needed here, check_index isn't really async but calls client logic. 
        # client logic is sync in qdrant_client unless using AsyncQdrantClient. 
        # Service uses sync Client. So we can just call it.)
        
        if not exists:
            logger.info(f"Index {i} is missing. Ingestion likely stopped before this.")
            start_search = max(0, i - 100)
            end_search = i
            found_missing_block = True
            break
        else:
            if i % 1000 == 0:
                print(f"Checked up to {i}... (Exists)")

    if not found_missing_block:
        logger.info("All scanned check-points exist. Checking last item...")
        if await check_index(total_rows - 1):
             logger.info("Last item exists. Full ingestion might be complete.")
             return
        else:
             start_search = total_rows - 100

    # Fine search in the identified range
    logger.info(f"Fine searching matching range {start_search} to {end_search}...")
    for i in range(start_search, end_search + 1):
        exists = await check_index(i)
        if not exists:
            logger.info(f"Found first missing item at Index: {i}")
            print(f"\nRECOMMENDED COMMAND:\npython src/scripts/ingest_studies.py 5 {i}\n")
            return

    logger.info("Could not determine exact break point.")

if __name__ == "__main__":
    asyncio.run(main())
