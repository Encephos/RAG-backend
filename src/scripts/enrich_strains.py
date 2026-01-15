import asyncio
import sys
import uuid
import pandas as pd
import numpy as np
from pathlib import Path
from qdrant_client import models
import logging
import csv

# Increase CSV field size limit
csv.field_size_limit(sys.maxsize)

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.services.qdrant_service import QdrantService
from src.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCRAPE_DIR = PROJECT_ROOT / "scrape_data" / "scrape"
COLLECTION_NAME = "strain_genetics"

def generate_deterministic_id(name: str) -> str:
    """Generate a deterministic UUID based on the strain name."""
    name_normalized = name.strip().lower()
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name_normalized))

async def enrich_from_strainmaster(qdrant: QdrantService):
    file_path = SCRAPE_DIR / "strainmaster.csv"
    if not file_path.exists():
        logger.warning(f"{file_path} not found.")
        return

    logger.info(f"Enriching from {file_path.name}...")
    
    # Read CSV
    df = pd.read_csv(file_path, on_bad_lines='skip', engine='python')
    
    updates = 0
    batch_size = 200
    current_batch = []
    
    for _, row in df.iterrows():
        try:
            name = str(row.get('Name', '')).strip()
            if not name or name.lower() == 'nan':
                continue
                
            doc_id = generate_deterministic_id(name)
            
            # Extract metadata lists
            # Columns like 'effects_1', 'effects_2', ...
            effects = [str(row.get(f'effects_{i}', '')) for i in range(1, 10)]
            effects = [x for x in effects if x and x.lower() != 'nan']
            
            flavors = [str(row.get(f'flavors_{i}', '')) for i in range(1, 11)]
            flavors = [x for x in flavors if x and x.lower() != 'nan']
            
            aromas = [str(row.get(f'aromas_{i}', '')) for i in range(1, 11)]
            aromas = [x for x in aromas if x and x.lower() != 'nan']
            
            terpenes = [str(row.get(f'terpene_{i}', '')) for i in range(1, 9)]
            terpenes = [x for x in terpenes if x and x.lower() != 'nan']
            
            medical = [str(row.get(f'medical_application_{i}', '')) for i in range(1, 6)]
            medical = [x for x in medical if x and x.lower() != 'nan']
            
            cannabinoids = [str(row.get(f'cannabinoids_{i}', '')) for i in range(1, 7)]
            cannabinoids = [x for x in cannabinoids if x and x.lower() != 'nan']

            payload_update = {}
            if effects: payload_update["effects"] = effects
            if flavors: payload_update["flavors"] = flavors
            if aromas: payload_update["aromas"] = aromas
            if terpenes: payload_update["terpenes"] = terpenes
            if medical: payload_update["medical"] = medical
            if cannabinoids: payload_update["cannabinoids"] = cannabinoids
            
            if payload_update:
                current_batch.append((doc_id, payload_update))
                
            if len(current_batch) >= batch_size:
                await process_batch(qdrant, current_batch)
                updates += len(current_batch)
                current_batch = []
                logger.info(f"Processed {updates} updates from strainmaster...")
                
        except Exception as e:
            continue
            
    if current_batch:
        await process_batch(qdrant, current_batch)
        updates += len(current_batch)
        
    logger.info(f"Finished {file_path.name}. Total potential updates: {updates}")


async def enrich_from_kushy(qdrant: QdrantService):
    file_path = SCRAPE_DIR / "strains-kushy_api.2017-11-14.csv"
    if not file_path.exists():
        logger.warning(f"{file_path} not found.")
        return

    logger.info(f"Enriching from {file_path.name}...")
    
    # Kushy CSV has quoted fields, standard comma sep
    df = pd.read_csv(file_path, on_bad_lines='skip', engine='python')
    
    updates = 0
    batch_size = 200
    current_batch = []
    
    for _, row in df.iterrows():
        try:
            name = str(row.get('name', '')).strip()
            if not name or name.lower() == 'nan':
                continue
                
            doc_id = generate_deterministic_id(name)
            
            payload_update = {}
            
            # Numeric fields
            if row.get('thc'): payload_update['thc_percent'] = row.get('thc')
            if row.get('cbd'): payload_update['cbd_percent'] = row.get('cbd')
            
            # CSV string fields (need generic splitting if needed, but looks like single value or array string?)
            # Assuming simple string for now, or use safe eval if it looks like ['a','b']
            # Based on header "flavor", "terpenes", "effects", "ailment"
            
            if row.get('flavor') and str(row.get('flavor')) != 'nan':
                # Might be comma separated
                payload_update['flavors'] = [x.strip() for x in str(row.get('flavor')).split(',')]
            
            if row.get('effects') and str(row.get('effects')) != 'nan':
                 payload_update['effects'] = [x.strip() for x in str(row.get('effects')).split(',')]
                 
            if row.get('ailment') and str(row.get('ailment')) != 'nan':
                 payload_update['medical'] = [x.strip() for x in str(row.get('ailment')).split(',')]

            if payload_update:
                current_batch.append((doc_id, payload_update))
                
            if len(current_batch) >= batch_size:
                await process_batch(qdrant, current_batch)
                updates += len(current_batch)
                current_batch = []
                logger.info(f"Processed {updates} updates from kushy...")
                
        except Exception as e:
            continue

    if current_batch:
        await process_batch(qdrant, current_batch)
        
    logger.info(f"Finished {file_path.name}.")


async def process_batch(qdrant: QdrantService, batch: list):
    """
    Checks existence of IDs in batch and updates payload if exists.
    """
    ids = [x[0] for x in batch]
    
    try:
        # Retrieve existing
        existing_points = qdrant.client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=ids,
            with_payload=True
        )
        
        existing_map = {point.id: point.payload for point in existing_points}
        
        for doc_id, new_data in batch:
            if doc_id in existing_map:
                # Merge logic: Append to list if list, or overwrite?
                # For safety, let's just MERGE lists if both exist, taking unique set
                
                current_payload = existing_map[doc_id]
                merged_payload = {}
                
                for key, val in new_data.items():
                    if isinstance(val, list):
                        existing_val = current_payload.get(key, [])
                        if isinstance(existing_val, list):
                            # Merge and uniq
                            merged_list = list(set(existing_val + val))
                            merged_payload[key] = merged_list
                        else:
                            merged_payload[key] = val
                    else:
                        # Scalar overwrite (e.g. thc pct)
                        merged_payload[key] = val
                
                if merged_payload:
                    # Perform set_payload
                    qdrant.client.set_payload(
                        collection_name=COLLECTION_NAME,
                        payload=merged_payload,
                        points=[doc_id]
                    )
                    
    except Exception as e:
        logger.error(f"Batch processing error: {e}")


async def main():
    qdrant = QdrantService()
    
    await enrich_from_strainmaster(qdrant)
    await enrich_from_kushy(qdrant)
    
    logger.info("Enrichment complete.")

if __name__ == "__main__":
    asyncio.run(main())
