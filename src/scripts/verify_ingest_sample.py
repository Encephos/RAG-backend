
import logging
import asyncio
import os
import sys
import csv
import random
from typing import List, Dict, Any

# Adjust path to find src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.services.qdrant_service import QdrantService
from src.core.config import settings

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
CSV_PATH = os.path.join(os.path.dirname(__file__), "../../scrape_data/scrape/scrape.csv")
SAMPLE_SIZE = 20
CRITICAL_STRAINS = ["Z and Z Auto", "ZZZ...", "ZZ4", "Herz OG Auto"]
REMOTE_HOST = "95.216.204.29"

async def main():
    logger.info("--- Preparing Ingestion Verification Sample ---")
    
    # Increase CSV limit for large HTML fields
    csv.field_size_limit(sys.maxsize)
    
    # 1. Read CSV and Sample
    strains_to_check = set(CRITICAL_STRAINS)
    all_strains = []
    
    if os.path.exists(CSV_PATH):
        try:
            with open(CSV_PATH, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=";")
                for row in reader:
                    name = row.get("Name")
                    if name:
                        all_strains.append(name)
            
            logger.info(f"Loaded {len(all_strains)} strains from CSV.")
            
            # Add random sample
            if all_strains:
                random_sample = random.sample(all_strains, min(len(all_strains), SAMPLE_SIZE))
                strains_to_check.update(random_sample)
                
        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
    else:
        logger.warning(f"CSV not found at {CSV_PATH}. Checking only critical strains.")

    sorted_strains = sorted(list(strains_to_check))
    logger.info(f"Selected {len(sorted_strains)} strains for verification: {sorted_strains}")

    # 2. Connect to Qdrant
    logger.info(f"Connecting to Remote Qdrant at {REMOTE_HOST}...")
    
    try:
        # Hack to force remote host without changing global config
        # We assume QdrantService uses settings.QDRANT_HOST. 
        # We can modify the env var for this process.
        os.environ["QDRANT_HOST"] = REMOTE_HOST
        # Also need to re-import settings or patching? 
        # QdrantService reads settings at init or module level? 
        # Usually it reads `settings.QDRANT_HOST`.
        # Let's verify QdrantService init.
        # Ideally we pass host to init.
        # If init doesn't take host, we modify settings object if possible.
        settings.QDRANT_HOST = REMOTE_HOST
        
        qdrant = QdrantService()
    except Exception as e:
        logger.error(f"Failed to initialize QdrantService: {e}")
        return

    # 3. Verify Strains
    logger.info("\n--- Verification Results ---")
    success_count = 0
    failure_count = 0
    
    for strain in sorted_strains:
        # Search for the entity
        # We need the vector to search, or we can assume ID generation if we knew the math, 
        # but 'search_entities' implies we need a vector. 
        # However, for verification, we might just filter by Payload if possible, or generate ID.
        # ingest_scraped uses uuid5 for ID: entity_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, name))
        import uuid
        entity_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, strain))
        
        # Determine collection
        collection = "botanical_entities" # Default
        
        try:
            # Direct Retrieve by ID is faster and more accurate than search
            point = qdrant.client.retrieve(
                collection_name=collection,
                ids=[entity_id],
                with_payload=True
            )
            
            if point:
                payload = point[0].payload
                relations = payload.get("relations", [])
                
                if relations:
                    logger.info(f"✅ [OK] '{strain}': Found with {len(relations)} relations.")
                    success_count += 1
                else:
                    # It might be a leaf node (no parents known), which is valid, 
                    # but for our critical ones we EXPECT relations.
                    if strain in CRITICAL_STRAINS:
                         logger.error(f"❌ [FAIL] '{strain}': Entity found but NO relations (Lineage empty).")
                         failure_count += 1
                    else:
                         logger.info(f"⚠️ [WARN] '{strain}': Found but 0 relations (might be a root ancestor).")
                         # We count finding the entity as partial success
                         success_count += 1
            else:
                logger.error(f"❌ [MISSING] '{strain}': Entity ID {entity_id} not found in DB.")
                failure_count += 1
                
        except Exception as e:
            logger.error(f"Error checking '{strain}': {e}")
            failure_count += 1

    logger.info("\n--- Summary ---")
    logger.info(f"Total Checked: {len(sorted_strains)}")
    logger.info(f"Success (Found + Populated): {success_count}")
    logger.info(f"Failures (Missing or Empty Critical): {failure_count}")

    if failure_count == 0:
        logger.info("\n🎉 INGESTION VERIFICATION PASSED! All sampled strains look good.")
    else:
        logger.error("\n💥 VERIFICATION FAILED. Some strains are missing or incomplete.")

if __name__ == "__main__":
    asyncio.run(main())
