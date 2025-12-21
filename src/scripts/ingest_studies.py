import asyncio
import csv
import sys
import os
import logging
import uuid
from typing import List, Dict, Any

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.core.config import settings
from src.services.qdrant_service import QdrantService
from src.services.rag_service import RagService
from src.services.scraper_service import ScraperService
from src.services.document_service import DocumentService
from src.services.embedding_service import EmbeddingService

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CSV_PATH = "scrape_data/scrape/cannabis_studies_complete_2025_classified.csv"

class StudyIngestor:
    def __init__(self):
        self.qdrant = QdrantService()
        self.rag_service = RagService()
        self.scraper = ScraperService()
        self.doc_service = DocumentService()
        self.embedding_service = EmbeddingService()

    async def run(self):
        if not os.path.exists(CSV_PATH):
            logger.error(f"CSV file not found at {CSV_PATH}")
            return

        # Concurrency Limit
        try:
            concurrency = int(sys.argv[1]) if len(sys.argv) > 1 else 5
        except ValueError:
            concurrency = 5
            
        logger.info(f"Starting ingestion from {CSV_PATH} with concurrency={concurrency}...")
        
        semaphore = asyncio.Semaphore(concurrency)

        async def worker(row, idx, total_rows):
            async with semaphore:
                logger.info(f"Processing study {idx+1}/{total_rows}: {row.get('study_title')}")
                await self.process_study(row)

        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            total = len(rows)
            
            tasks = [worker(row, i, total) for i, row in enumerate(rows)]
            await asyncio.gather(*tasks)

    async def process_study(self, row: Dict[str, str]):
        title = row.get("study_title")
        if not title:
            return

        # 1. Ingest Metadata & Knowledge Graph Entity
        await self.ingest_metadata(row)

        # 2. Download and Ingest PDF
        pdf_url = row.get("pdf_final_url")
        if pdf_url and pdf_url.strip():
            await self.ingest_pdf(pdf_url, title, row)
        else:
            logger.warning(f"No PDF URL for study: {title}")

    async def ingest_metadata(self, row: Dict[str, str]):
        title = row.get("study_title")
        cannabinoids = row.get("cannabinoids", "")
        organs = row.get("organ_systems", "")
        link = row.get("study_link", "")
        year = row.get("study_year", "")
        conditions = row.get("study_conditions", "")
        study_type = row.get("study_type", "")

        # Create Text Representation
        text_content = f"Study: {title}\n"
        text_content += f"Year: {year}\n"
        text_content += f"Type: {study_type}\n"
        text_content += f"Cannabinoids: {cannabinoids}\n"
        text_content += f"Organ Systems: {organs}\n"
        text_content += f"Conditions: {conditions}\n"
        text_content += f"Link: {link}\n"

        # Generate Vector
        vector = await self.embedding_service.embed_query(text_content)
        
        # Metadata Payload
        payload = {
            "title": title,
            "cannabinoids": cannabinoids,
            "organ_systems": organs,
            "url": link,
            "type": "study",
            "year": year,
            "study_type": study_type,
            "conditions": conditions,
            "source": "csv_ingest"
        }

        # 1. Upsert to Knowledge Collection (studies_data_768)
        # Using alias "studies" which maps to "studies_data_768"
        self.qdrant.upsert(
            text=text_content,
            vector=vector,
            metadata=payload,
            collection_alias="studies"
        )
        
        # Also ingest to master? User said "studies und master".
        self.qdrant.upsert(
            text=text_content,
            vector=vector,
            metadata=payload,
            collection_alias="master"
        )

        # 2. Upsert to Knowledge Graph (Entity)
        # Entity ID
        entity_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, title))
        
        entity_payload = {
            "id": entity_id,
            "name": title,
            "type": "Study",
            "description": f"Study on {conditions} affecting {organs}. Cannabinoids: {cannabinoids}",
            "metadata": payload,
            "relations": [] # Potentially relationships to Cannabinoid Entities could be added here
        }

        # Ingest to studies_entities_768 (via alias 'studies')
        # Note: qdrant_service.upsert_entity takes collection_name, not alias usually.
        # But let's check qdrant_service.upsert_entity signature. 
        # It takes 'collection_name'.
        # We need to look up the real name from the alias 'studies' in 'entity_collections' map.
        
        target_entity_col = self.qdrant.entity_collections.get("studies")
        if target_entity_col:
            self.qdrant.upsert_entity(
                entity_id=entity_id,
                vector=vector,
                payload=entity_payload,
                collection_name=target_entity_col
            )
        
        # Also to master entity collection?
        target_master_entity = self.qdrant.entity_collections.get("master")
        if target_master_entity:
             self.qdrant.upsert_entity(
                entity_id=entity_id,
                vector=vector,
                payload=entity_payload,
                collection_name=target_master_entity
            )
            
        logger.info(f"Ingested metadata for: {title}")

    async def ingest_pdf(self, url: str, title: str, metadata: Dict[str, str]):
        import time
        t0 = time.time()
        logger.info(f"Downloading PDF for '{title}' from {url}...")
        
        try:
            # Download
            pdf_bytes = await asyncio.to_thread(self.scraper.download_file, url)
            t_download = time.time()
            
            if not pdf_bytes:
                logger.warning(f"Failed to download PDF from {url} ({(t_download-t0):.2f}s)")
                return

            # Process / Chunk
            # 'process_uploaded_file' expects bytes and filename
            pseudo_filename = f"{title[:50].replace(' ', '_')}.pdf"
            logger.info(f"Processing PDF (OCR/Parsing) for '{title}'...")
            chunks, pdf_meta = await self.doc_service.process_uploaded_file(pdf_bytes, pseudo_filename)
            t_process = time.time()
            
            if not chunks:
                logger.warning(f"No text extracted from PDF ({(t_process-t_download):.2f}s).")
                return

            full_text = "\n\n".join([c.text for c in chunks])
            logger.info(f"Extracted {len(full_text)} chars from PDF in {(t_process-t_download):.2f}s. Ingesting chunks...")

            # Merge PDF metadata with CSV metadata
            combined_metadata = {
                "source": url,
                "source_url": url,
                "title": title,
                "type": "study_pdf",
                "csv_metadata": metadata,
                "download_time_sec": round(t_download - t0, 3),
                "parse_time_sec": round(t_process - t_download, 3)
            }

            # Update chunks metadata
            for chunk in chunks:
                if hasattr(chunk, 'metadata'):
                    chunk.metadata.update(combined_metadata)
                elif isinstance(chunk, dict):
                    chunk['metadata'].update(combined_metadata)

            # Ingest using RagService generator
            # Target collections: studies, master
            target_cols = ["studies", "master"]
            
            async for event in self.rag_service.ingest_document_generator(
                full_text=full_text,
                chunks=chunks, 
                target_collections=target_cols,
                source_name=title,
                skip_kg_extraction=True
            ):
                # Log progress from generator
                if event.get("step") == "indexing":
                    logger.info(f"[{title[:30]}...] {event.get('message')}")
                elif event.get("step") == "indexing_complete":
                     logger.info(f"[{title[:30]}...] Vector indexing complete.")
                
            logger.info(f"Successfully ingested PDF for {title}")

        except Exception as e:
            logger.error(f"Error ingesting PDF for {title}: {e}")

if __name__ == "__main__":
    ingestor = StudyIngestor()
    asyncio.run(ingestor.run())
