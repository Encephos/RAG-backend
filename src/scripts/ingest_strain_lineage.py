
import pandas as pd
import os
import glob
import uuid
import logging
from typing import Dict, List, Any, Optional
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models
import sys

# Add parent directory to path to allow imports from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
CSV_FILES = [
    'scrape_data/scrape/cannabis-strains-final.csv',
    'scrape_data/scrape/cannabis.csv',
    'scrape_data/scrape/cepas.csv',
    'scrape_data/scrape/leafly_strain_data.csv',
    'scrape_data/scrape/OCPDB.csv',
    'scrape_data/scrape/results.csv', 
    'scrape_data/scrape/scrape.csv',
    'scrape_data/scrape/strainmaster.csv',
    'scrape_data/scrape/strains-kushy_api.2017-11-14.csv',
    'data/sources/all_strains_seedfinder.csv'
]

COLLECTION_NAME = "strain_lineage_data"
VECTOR_SIZE = 384

class StrainIngester:
    def __init__(self):
        self.strains: Dict[str, Dict[str, Any]] = {}
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

    def normalize_name(self, name: Any) -> Optional[str]:
        if not name or pd.isna(name):
            return None
        return str(name).strip().lower()

    def generate_uuid(self, name: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))

    def load_data(self):
        logger.info("Loading CSV files...")
        
        for file_path in CSV_FILES:
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                continue

            try:
                # Handle separator for Seedfinder
                sep = ';' if 'seedfinder' in file_path else ','
                df = pd.read_csv(file_path, on_bad_lines='skip', low_memory=False, sep=sep)
                
                logger.info(f"Processing {os.path.basename(file_path)}...")
                self._process_dataframe(df, file_path)
                
            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")

    def _process_dataframe(self, df: pd.DataFrame, source_file: str):
        # Identify column mappings based on file source
        cols = df.columns
        filename = os.path.basename(source_file)
        
        for _, row in df.iterrows():
            name = None
            strain_data = {
                "source_files": [filename],
                "parents": [],
                "description": "",
                "breeder": "",
                "type": "",
                "effects": [],
                "html_tree": None # Special field for scrape.csv lineage tree
            }

            # --- Extraction Logic per File ---
            if 'seedfinder' in filename:
                name = self.normalize_name(row.get('Name der Strain'))
                
                # Extract parents (Eltern 1, Eltern 2)
                p1 = self.normalize_name(row.get('Eltern 1'))
                p2 = self.normalize_name(row.get('Eltern 2'))
                if p1: strain_data['parents'].append(p1)
                if p2: strain_data['parents'].append(p2)
                
                strain_data['breeder'] = row.get('Breeder', '')
                strain_data['type'] = row.get('Typ', '')

            elif 'scrape.csv' in filename:
                # This file usually has the HTML parent_tree
                name = self.normalize_name(row.get('strain_name') or row.get('Strain')) # Check actual col name
                if 'parent_tree' in cols:
                    strain_data['html_tree'] = row.get('parent_tree')
                
                # Try to get parents from standard cols if html tree absent
                if not strain_data['html_tree'] and 'parents' in row:
                     parents_str = str(row.get('parents', ''))
                     if parents_str and parents_str != 'nan':
                         strain_data['parents'] = [self.normalize_name(p) for p in parents_str.split(',')]

            elif 'kushy' in filename:
                name = self.normalize_name(row.get('name'))
                # Kushy has 'crosses' column? Or we just take description
                strain_data['description'] = row.get('description', '')
                strain_data['breeder'] = row.get('breeder', '')
                
            else:
                # Generic fallback: look for 'name' or 'Strain'
                name_col = next((c for c in cols if 'name' in c.lower() and 'filename' not in c.lower()), None)
                if not name_col and 'Strain' in cols: name_col = 'Strain'
                
                if name_col:
                    name = self.normalize_name(row[name_col])
                    
                    # Try to find description
                    desc_col = next((c for c in cols if 'desc' in c.lower()), None)
                    if desc_col: strain_data['description'] = row[desc_col]

            if name:
                self._merge_strain_data(name, strain_data)

    def _merge_strain_data(self, name: str, new_data: Dict[str, Any]):
        if name not in self.strains:
            self.strains[name] = {
                "name": name,
                "uuid": self.generate_uuid(name),
                "parents": [],
                "breeder": "",
                "description": "",
                "type": "",
                "effects": [],
                "sources": [],
                 "html_tree": None
            }
        
        existing = self.strains[name]
        
        # Merge Sources
        existing['sources'] = list(set(existing['sources'] + new_data['source_files']))
        
        # Merge Parents (Prioritize Seedfinder/Scrape)
        # If existing has no parents or new data is from seedfinder, update/append
        if not existing['parents'] and new_data['parents']:
            existing['parents'] = new_data['parents']
        elif new_data['parents'] and 'seedfinder' in new_data['source_files'][0]:
             # Seedfinder is authoritative for direct parents usually
             # But let's union them to be safe, avoid dups
             existing['parents'] = list(set(existing['parents'] + new_data['parents']))
        
        # Merge HTML Tree (Prioritize if present)
        if new_data['html_tree'] and not existing['html_tree']:
            existing['html_tree'] = new_data['html_tree']
            
        # Merge Breeder (Longest string wins, primitive heuristic)
        if len(str(new_data['breeder'])) > len(str(existing['breeder'])):
             existing['breeder'] = new_data['breeder']

        # Merge Description (Concatenate if unique or Longest?)
        # Let's keep longest
        if len(str(new_data['description'])) > len(str(existing['description'])):
             existing['description'] = new_data['description']

    def resolve_references(self):
        """
        Convert text parent names to UUID references.
        Create stub entries for parents that don't exist yet? 
        For now, just link to UUIDs of known strains.
        """
        logger.info("Resolving lineage references...")
        
        for name, data in self.strains.items():
            resolved_parents = []
            for p_name in data['parents']:
                if not p_name: continue
                p_uuid = self.generate_uuid(p_name)
                
                # Check if parent exists in our DB, if so, add valid link
                if p_name in self.strains:
                    resolved_parents.append({
                        "name": p_name,
                        "id": p_uuid
                    })
                else:
                    # Parent doesn't exist as a main entry
                    # We create a stub? Or just keep it as text?
                    # Plan says "creating stubs if missing", but that might bloat DB 
                    # with empty strains.
                    # For now, let's just include name and the theoretical UUID
                    resolved_parents.append({
                        "name": p_name,
                        "id": p_uuid,
                        "missing": True
                    })
            
            data['resolved_parents'] = resolved_parents

    def ensure_collection(self):
        logger.info(f"Ensuring Qdrant collection {COLLECTION_NAME} exists...")
        collections = self.client.get_collections().collections
        existing = [c.name for c in collections]
        
        if COLLECTION_NAME not in existing:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=VECTOR_SIZE,
                    distance=models.Distance.COSINE
                )
            )

    def ingest(self):
        self.ensure_collection()
        
        logger.info(f"Encoding and upserting {len(self.strains)} strains...")
        
        batch_size = 100
        strain_list = list(self.strains.values())
        
        for i in tqdm(range(0, len(strain_list), batch_size)):
            batch = strain_list[i : i + batch_size]
            
            # Prepare vectors
            # Text to encode: Name + Breeder + Description
            texts = [
                f"{s['name']} breeder:{s['breeder']} {s['description']}"[:1000] 
                for s in batch
            ]
            
            vectors = self.encoder.encode(texts)
            
            points = []
            for idx, item in enumerate(batch):
                points.append(models.PointStruct(
                    id=item['uuid'],
                    vector=vectors[idx].tolist(),
                    payload=item
                ))
            
            self.client.upsert(
                collection_name=COLLECTION_NAME,
                points=points
            )

def main():
    ingester = StrainIngester()
    ingester.load_data()
    ingester.resolve_references()
    ingester.ingest()
    logger.info("Ingestion complete.")

if __name__ == "__main__":
    main()
