import asyncio
import sys
from pathlib import Path
from qdrant_client import models
import logging

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.services.kg_service import KnowledgeGraphService
from src.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    kg = KnowledgeGraphService()
    
    strain_name = "Zam's Poison"
    logger.info(f"Checking for strain: {strain_name} in 'strain_genetics'")
    
    # 1. Search by text (Hybrid) or exact match via get_strain_lineage
    # But get_strain_lineage uses deterministic ID.
    
    result = await kg.get_lineage(strain_name, collection_name="strain_genetics")
    
    if result and result.get("nodes"):
        logger.info(f"FOUND Strain in Graph: {strain_name}")
        nodes = result.get("nodes")
        logger.info(f"Nodes found: {len(nodes)}")
        for n in nodes:
             if n.get("id") == result.get("nodes")[0].get("id"): # Target node
                 logger.info(f"TARGET NODE: {n.get('label')}")
                 logger.info(f"Parents: {n.get('payload_stub', {}).get('resolved_parents')}")
             else:
                 logger.info(f" - {n.get('label')} ({n.get('group')})")
    else:
        logger.warning(f"Strain '{strain_name}' NOT FOUND.")

if __name__ == "__main__":
    asyncio.run(main())
