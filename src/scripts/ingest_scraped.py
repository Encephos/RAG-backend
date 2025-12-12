
import os
import csv
import json
import asyncio
import logging
from typing import List, Dict, Any
import uuid

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock settings/service for standalone execution if needed, 
# or import from app if available.
try:
    from src.services.qdrant_service import QdrantService
    from src.core.config import settings
except ImportError:
    # Fallback for standalone testing typically not needed if run from root
    logger.error("Could not import QdrantService. Run this script from project root.")
    exit(1)

DATA_DIR = "data/sources/scrape"

class ScrapedDataIngestor:
    def __init__(self):
        self.qdrant = QdrantService()
        self.batch_size = 50 

    async def run(self):
        logger.info("Starting ingestion of scraped data...")
        
        files = [f for f in os.listdir(DATA_DIR) if os.path.isfile(os.path.join(DATA_DIR, f))]
        
        for filename in files:
            filepath = os.path.join(DATA_DIR, filename)
            logger.info(f"Processing {filename}...")
            
            try:
                data = self._parse_file(filepath, filename)
                if data:
                    await self._ingest_batch(data, filename)
            except Exception as e:
                logger.error(f"Failed to process {filename}: {e}")

        logger.info("Ingestion complete!")

    def _parse_file(self, filepath: str, filename: str) -> List[Dict[str, Any]]:
        """Parses file based on name and returns list of standardized strain dicts."""
        normalized_data = []

        if "cannabis-strains-final.csv" in filename:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    normalized_data.append({
                        "name": row.get("strain_name"),
                        "description": row.get("description"),
                        "type": f"{row.get('indica_sativa', '')} ({row.get('type_ratio', '')})",
                        "effects": row.get("effect"),
                        "flavor": f"{row.get('flavor')} / {row.get('smell_taste')}",
                        "thc": row.get("thc"),
                        "cbd": row.get("cbd"),
                        "yield_indoor": row.get("yield_indoor"),
                        "climate": row.get("climate"),
                        "source_file": filename
                    })

        elif "leafly_strain_data.csv" in filename:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Flatten heavy medical/effect columns to string desc
                    effects_list = []
                    for k, v in row.items():
                        if v and '%' in str(v) and k not in ['thc_level']:
                             effects_list.append(f"{k}: {v}")
                    
                    normalized_data.append({
                        "name": row.get("name"),
                        "description": row.get("description"),
                        "type": row.get("type"),
                        "thc": row.get("thc_level"),
                        "terpene": row.get("most_common_terpene"),
                        "effects_profile": ", ".join(effects_list),
                        "image": row.get("img_url"),
                        "source_file": filename
                    })

        elif "cannabis.csv" in filename:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    normalized_data.append({
                        "name": row.get("Strain"),
                        "type": row.get("Type"),
                        "rating": row.get("Rating"),
                        "effects": row.get("Effects"),
                        "flavor": row.get("Flavor"),
                        "description": row.get("Description"),
                        "source_file": filename
                    })

        elif "cannabis.json" in filename:
            with open(filepath, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
                # It's a list check
                if isinstance(raw_data, list):
                    for item in raw_data:
                         normalized_data.append({
                            "name": item.get("Strain"),
                            "type": item.get("Type"),
                            "effects": item.get("Effects"),
                            "flavor": item.get("Flavor"),
                            "description": item.get("Description"),
                            "source_file": filename
                        })

        elif "strains-kushy_api" in filename:
             with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    normalized_data.append({
                        "name": row.get("name"),
                        "description": row.get("description"), # Contains HTML, useful to process later or keep raw
                        "type": row.get("type"),
                        "breeder": row.get("breeder"),
                        "effects": row.get("effects"),
                        "ailment": row.get("ailment"),
                        "thc": row.get("thc"),
                        "cbd": row.get("cbd"),
                        "terpenes": row.get("terpenes"),
                        "source_file": filename
                    })
        
        elif "results.csv" in filename:
             with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Lab results are distinct, treat Sample Name as Strain Name
                    # Collect basic chemical profile
                    chem_profile = []
                    for k, v in row.items():
                         if v and k not in ['Sample Name', 'Database Identifier', 'Provider'] and len(str(v)) < 10:
                             chem_profile.append(f"{k}: {v}")
                    
                    normalized_data.append({
                        "name": row.get("Sample Name"),
                        "type": "Lab Result",
                        "chemicals": ", ".join(chem_profile),
                        "provider": row.get("Provider"),
                        "source_file": filename
                    })

        return normalized_data

    async def _ingest_batch(self, data: List[Dict[str, Any]], filename: str):
        """Ingests normalized data into Knowledge and Entity collections."""
        
        # We process in small chunks to avoid memory/rate issues
        chunk_size = 50
        for i in range(0, len(data), chunk_size):
             batch = data[i:i + chunk_size]
             
             # Prepare Entity Points (Graph)
             # Entities collection needs: id, vector (placeholder or named vector), payload
             for item in batch:
                 await self._upsert_item(item)
    
    async def _upsert_item(self, item: Dict[str, Any]):
        name = item.get("name")
        if not name or len(name) < 2: 
            return

        # 1. ENTITY (Graph Node) -> botanical_entities
        # ID is deterministic based on name
        entity_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, name))
        
        # Create a dummy vector for entity if no embedding model used here yet
        # Or ideally, we should use RagService to get embedding.
        # For this script simplicity, we skip embedding generation and just push payload 
        # BUT Qdrant needs a vector. 
        # Let's rely on QdrantService behavior or generate a zero vector/random for now if allowed, 
        # OR better: use the RagService to embed name.
        
        # Actually, let's use the description for Knowledge collection text.
        text_content = f"Strain: {name}\n"
        for k, v in item.items():
            if v and k not in ['name', 'source_file']:
                text_content += f"{k.capitalize()}: {v}\n"
        
        # We need embeddings. Let's use fastembed logic if possible, 
        # or just import the global RagService if initialized. 
        # Initializing RagService is heavier but correct.
        
        # For simplicity in this standalone script, let's assume we can use QdrantService to upsert
        # but we need vectors. 
        # Let's instantiate the embedding model locally.
        try:
             from fastembed import TextEmbedding
             if not hasattr(self, 'model'):
                 self.model = TextEmbedding(model_name=settings.EMBEDDING_MODEL_NAME)
        except ImportError:
             logger.error("Fastembed not found.")
             return

        # Generate Vector
        # We embed the entire text content for Knowledge
        embeddings = list(self.model.embed([text_content]))
        vector = [float(x) for x in embeddings[0]]

        # Upsert to Knowledge (Botanical)
        self.qdrant.upsert(
            text=text_content,
            vector=vector,
            metadata={"source": item.get('source_file'), "type": "scraped_data", "strain": name},
            collection_alias="botanical"
        )
        
        # Upsert to Knowledge (Master) - Requested by User
        self.qdrant.upsert(
            text=text_content,
            vector=vector,
            metadata={"source": item.get('source_file'), "type": "scraped_data", "strain": name},
            collection_alias="master"
        )
        
        # Upsert to Entities (Botanical)
        # We embed just the Name for the Entity Vector usually, or same content.
        # Let's use name embedding for entity lookup
        name_emb = list(self.model.embed([name]))[0]
        name_vector = [float(x) for x in name_emb]
        
        self.qdrant.upsert_entity(
            entity_id=entity_id,
            vector=name_vector,
            payload={**item, "entity_type": "strain", "label": name},
            collection_name="botanical_entities"
        )
        
        # Also upsert to Master Entities for global graph
        self.qdrant.upsert_entity(
            entity_id=entity_id,
            vector=name_vector,
            payload={**item, "entity_type": "strain", "label": name},
            collection_name=settings.QDRANT_ENTITY_COLLECTION_NAME # rag_entities
        )

if __name__ == "__main__":
    ingestor = ScrapedDataIngestor()
    asyncio.run(ingestor.run())
