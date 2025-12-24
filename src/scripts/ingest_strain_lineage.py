
import pandas as pd
import os
import glob
import uuid
import logging
import re
from typing import Dict, List, Any, Optional, Set, Tuple
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models
import sys
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

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

# Helper function needs to be top-level for pickling in multiprocessing
def normalize_name(name: Any) -> Optional[str]:
    if pd.isna(name) or not name:
        return None
    # Aggressive normalization:
    # 1. Lowercase
    n = str(name).lower().strip()
    # 2. Remove text in brackets [] or parens () ONLY IF they contain "clone", "cut", "pheno", "ibl"
    # Actually user wants to merge "Sour Diesel IBL(IBL)" -> "Sour Diesel IBL".
    # And "OG Kush[Larry Clone]" -> "OG Kush".
    # Let's remove ALL content in [] as that is usually pheno info in Seedfinder.
    n = re.sub(r'\[.*?\]', '', n)
    # Remove (IBL) specifically or other noise? (IBL) is a breeding term.
    # "Sour Diesel IBL" vs "Sour Diesel IBL(IBL)" -> remove (IBL) at end.
    n = re.sub(r'\s*\(ibl\)$', '', n)
    n = re.sub(r'\s*\(.*?\)$', '', n) # Remove ALL parens? Might match "Gelato (41)" -> Gelato. 
    # Maybe too aggressive? "Zkittlez (Grape Ape x Grapefruit)" -> Zkittlez. NO!
    # Parents are often in parens in descriptions, but not in NAME usually unless it's a cross name.
    # Safest: Remove [] definitely. Remove specific suffixes like (IBL), (Cut).
    
    # Revised: Remove all [] (Phenos)
    n = re.sub(r'\[.*?\]', '', n)
    
    # Remove specific noise pattern
    n = n.replace('(ibl)', '').replace(' ibl', '') # Merge IBL variants
    
    # Cleanup spaces
    n = re.sub(r'\s+', ' ', n).strip()
    
    return n if n else None

def generate_uuid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))

def parse_lineage_tree_static(parent_html: str, root_name: str) -> Tuple[Dict, Set]:
    """Static version of lineage parsing for multiprocessing"""
    if not parent_html or pd.isna(parent_html):
            return {}, set()

    if not parent_html.strip().lower().startswith("<li"):
            parent_html = f"<li>{parent_html}</li>"

    try:
        from bs4 import BeautifulSoup, Tag
    except ImportError:
        return {}, set()

    soup = BeautifulSoup(parent_html, "html.parser")
    root_li = soup.find('li')
    
    tree_relations = {}
    found_strains = {root_name} if root_name else set()
    
    def parse_node(element: Tag, current_name: str):
            if not current_name: return
            current_name_norm = normalize_name(current_name)
            if not current_name_norm: return

            found_strains.add(current_name_norm)
            
            ul = element.find('ul', recursive=False)
            if not ul: return 
            
            for child in ul.children:
                if child.name == 'ul':
                    for inner_li in child.find_all('li'):
                        if "»»»" in inner_li.get_text():
                            links = inner_li.find_all('a')
                            p_list = []
                            for link in links:
                                p_name = link.get_text(strip=True)
                                if p_name and p_name != "Unknown Ruderalis":
                                    p_norm = normalize_name(p_name)
                                    if p_norm: p_list.append(p_norm)
                            
                            if p_list:
                                existing = tree_relations.get(current_name_norm, [])
                                tree_relations[current_name_norm] = list(set(existing + p_list))
                                found_strains.update(p_list)
                                break 
                
                elif child.name == 'li':
                    li = child
                    text = li.get_text()
                    
                    if "»»»" in text and not li.find('ul'):
                        links = li.find_all('a')
                        p_list = []
                        for link in links:
                            p_name = link.get_text(strip=True)
                            if p_name and p_name != "Unknown Ruderalis":
                                p_norm = normalize_name(p_name)
                                if p_norm: p_list.append(p_norm)
                        
                        if p_list:
                            existing = tree_relations.get(current_name_norm, [])
                            tree_relations[current_name_norm] = list(set(existing + p_list))
                            found_strains.update(p_list)
                    
                    if li.find('ul'):
                        # Iterate children to build FULL name (e.g. "Gelato x Orange")
                        # Stop at the nested 'ul'
                        name_parts = []
                        for sub in li.children:
                            if sub.name == 'ul': break
                            if sub.name == 'a':
                                name_parts.append(sub.get_text(strip=True))
                            elif isinstance(sub, str) and sub.strip():
                                name_parts.append(sub.strip())
                            # Handle spans or other tags if any (rare in seedfinder simple lists)
                            elif sub.name and sub.name != 'ul':
                                name_parts.append(sub.get_text(strip=True))
                        
                        child_name = " ".join(name_parts).strip()

                        if child_name and child_name != current_name:
                            child_name_norm = normalize_name(child_name)
                            if child_name_norm:
                                existing = tree_relations.get(current_name_norm, [])
                                if child_name_norm not in existing:
                                    existing.append(child_name_norm)
                                    tree_relations[current_name_norm] = existing
                                
                                parse_node(li, child_name)

                    elif not li.find('ul') and "»»»" not in text:
                        link = li.find('a')
                        if link:
                            p_name = link.get_text(strip=True)
                            if p_name:
                                p_norm = normalize_name(p_name)
                                if p_norm:
                                    existing = tree_relations.get(current_name_norm, [])
                                    if p_norm not in existing:
                                        existing.append(p_norm)
                                        tree_relations[current_name_norm] = existing
                                    found_strains.add(p_norm)

    if root_li:
            parse_node(root_li, root_name)
            
    return tree_relations, found_strains

def process_chunk(chunk_data: List[Dict[str, Any]], filename: str) -> Dict[str, Dict]:
    """Process a list of rows in a separate process"""
    results = {}
    
    for row in chunk_data:
        name = None
        strain_data = {
            "source_files": [filename],
            "parents": [],
            "description": "",
            "breeders": set(),
            "type": "",
            "effects": [],
            "html_tree": None,
            "inferred_ancestors": [] # Store inferred nodes here
        }

        # --- Extraction Logic ---
        if 'seedfinder' in filename:
            name = normalize_name(row.get('Name der Strain'))
            p1 = normalize_name(row.get('Eltern 1'))
            p2 = normalize_name(row.get('Eltern 2'))
            if p1: strain_data['parents'].append(p1)
            if p2: strain_data['parents'].append(p2)
            br = row.get('Breeder')
            if br and not pd.isna(br): strain_data['breeders'].add(str(br).strip())
            strain_data['type'] = row.get('Typ', '')

        elif 'scrape.csv' in filename:
            name = normalize_name(row.get('strain_name') or row.get('Name'))
            parent_html = row.get('parent_tree')
            
            if parent_html:
                strain_data['html_tree'] = parent_html
                # Use static parsing function
                relations, found_strains = parse_lineage_tree_static(parent_html, name)
                
                if name in relations:
                    strain_data['parents'] = relations[name]
                
                for found in found_strains:
                    if found == name: continue
                    # Collect inferred ancestor data
                    strain_data["inferred_ancestors"].append({
                        "name": found,
                        "parents": relations.get(found, [])
                    })
            
            if not strain_data['parents'] and 'parents' in row:
                    parents_str = str(row.get('parents', ''))
                    if parents_str and parents_str != 'nan':
                        strain_data['parents'] = [normalize_name(p) for p in parents_str.split(',')]
                        
            br = row.get('breeder') or row.get('Breeder')
            if br and not pd.isna(br): strain_data['breeders'].add(str(br).strip())

        elif 'kushy' in filename:
            name = normalize_name(row.get('name'))
            strain_data['description'] = row.get('description', '')
            br = row.get('breeder')
            if br and not pd.isna(br): strain_data['breeders'].add(str(br).strip())
            
        else:
            cols = row.keys()
            # Generic fallback (keys are present in the row dict)
            name_col = next((c for c in cols if 'name' in c.lower() and 'filename' not in c.lower()), None)
            if not name_col and 'Strain' in cols: name_col = 'Strain'
            
            if name_col:
                name = normalize_name(row[name_col])
                desc_col = next((c for c in cols if 'desc' in c.lower()), None)
                if desc_col: strain_data['description'] = row[desc_col]
                br_col = next((c for c in cols if 'breeder' in c.lower()), None)
                if br_col:
                    br = row[br_col]
                    if br and not pd.isna(br): strain_data['breeders'].add(str(br).strip())

        if name:
            results[name] = strain_data
            
    return results

class StrainIngester:
    def __init__(self):
        self.strains: Dict[str, Dict[str, Any]] = {}
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

    # ... normalize_name, generate_uuid, parse_lineage_tree moved to top level/static ...
    
    # Wrapper for instance to use static method if needed, but we use top level in multiprocessing
    def normalize_name(self, name): return normalize_name(name)
    def generate_uuid(self, name): return generate_uuid(name)
    def parse_lineage_tree(self, h, r): return parse_lineage_tree_static(h, r)

    def load_data(self):
        logger.info("Loading CSV files with Multiprocessing...")
        
        # Adjust pool size
        num_workers = min(multiprocessing.cpu_count(), 8)
        pool = ProcessPoolExecutor(max_workers=num_workers)
        futures = []

        for file_path in CSV_FILES:
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                continue

            try:
                sep = ';' if 'seedfinder' in file_path else ','
                if 'scrape.csv' in file_path: sep = ';' 
                
                df = pd.read_csv(file_path, on_bad_lines='skip', low_memory=False, sep=sep)
                filename = os.path.basename(file_path)
                logger.info(f"Loaded {filename}, processing {len(df)} rows...")
                
                # Convert DF to list of dicts for chunking
                rows = df.to_dict('records')
                chunk_size = 2000
                
                # Submit chunks
                for i in range(0, len(rows), chunk_size):
                    chunk = rows[i:i + chunk_size]
                    futures.append(pool.submit(process_chunk, chunk, filename))
                
            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")

        # Gather results
        logger.info(f"Waiting for {len(futures)} tasks to complete...")
        for future in tqdm(as_completed(futures), total=len(futures)):
            try:
                chunk_results = future.result()
                self._merge_chunk_results(chunk_results)
            except Exception as e:
                logger.error(f"Chunk processing failed: {e}")
        
        pool.shutdown()

    def _merge_chunk_results(self, chunk_results: Dict[str, Dict]):
        for name, data in chunk_results.items():
            self._merge_strain_data(name, data)
            
            # Handle inferred ancestors carried in data
            if "inferred_ancestors" in data:
                for inf in data["inferred_ancestors"]:
                    inf_data = {
                        "source_files": [data['source_files'][0] + " (inferred)"],
                        "parents": inf['parents'],
                        "description": "Inferred from lineage tree",
                        "breeders": set(),
                        "type": "Inferred",
                        "effects": [],
                        "html_tree": None
                    }
                    self._merge_strain_data(inf['name'], inf_data)

    def _merge_strain_data(self, name: str, new_data: Dict[str, Any]):
        if name not in self.strains:
            self.strains[name] = {
                "name": name,
                "uuid": generate_uuid(name),
                "parents": [],
                "breeders": set(),
                "description": "",
                "type": "",
                "effects": [],
                "sources": [],
                 "html_tree": None
            }
        
        existing = self.strains[name]
        existing['sources'] = list(set(existing['sources'] + new_data['source_files']))
        
        if not existing['parents'] and new_data['parents']:
            existing['parents'] = new_data['parents']
        elif new_data['parents'] and ('seedfinder' in new_data['source_files'][0] or 'scrape.csv' in new_data['source_files'][0]):
             existing['parents'] = list(set(existing['parents'] + new_data['parents']))
        
        if new_data['html_tree'] and not existing['html_tree']:
            existing['html_tree'] = new_data['html_tree']
            
        if new_data.get('breeders'):
            existing['breeders'].update(new_data['breeders'])

        if len(str(new_data['description'])) > len(str(existing['description'])):
             existing['description'] = new_data['description']

    def resolve_references(self):
        logger.info("Resolving lineage references...")
        new_nodes = {}
        for name, data in self.strains.items():
            for p_name in data['parents']:
                if not p_name: continue
                if p_name not in self.strains and p_name not in new_nodes:
                    new_nodes[p_name] = {
                        "name": p_name,
                        "uuid": generate_uuid(p_name),
                        "parents": [],
                        "breeders": set(["Unknown"]), 
                        "description": "Auto-created parent node",
                        "type": "Unknown",
                        "effects": [],
                        "sources": ["auto-generated"],
                        "html_tree": None
                    }
        if new_nodes:
            self.strains.update(new_nodes)

        for name, data in self.strains.items():
            resolved_parents = []
            for p_name in data['parents']:
                if not p_name: continue
                if p_name == name: continue
                if p_name in self.strains:
                    resolved_parents.append({
                        "name": p_name,
                        "id": self.strains[p_name]['uuid']
                    })
            data['resolved_parents'] = resolved_parents

    def ensure_collection(self):
        logger.info(f"Ensuring Qdrant collection {COLLECTION_NAME} exists...")
        try:
             collections = self.client.get_collections().collections
             existing = [c.name for c in collections]
             if COLLECTION_NAME not in existing:
                self.client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE)
                )
        except Exception:
             # Retry once
             pass

    def ingest(self):
        self.ensure_collection()
        logger.info(f"Encoding and upserting {len(self.strains)} strains...")
        
        strain_list = list(self.strains.values())
        batch_size = 100 # Qdrant batch size
        
        # Parallel Encoding option? SentenceTransformer is CPU/GPU intensive.
        # But usually batched encoding is faster on one process unless we have multiple GPUs.
        # So we keep this part simple but use larger batches if needed.
        
        for i in tqdm(range(0, len(strain_list), batch_size)):
            batch = strain_list[i : i + batch_size]
            texts = [s['name'] for s in batch]
            vectors = self.encoder.encode(texts)
            points = []
            for idx, item in enumerate(batch):
                payload = item.copy()
                if isinstance(payload.get('breeders'), set):
                    payload['breeders'] = list(payload['breeders'])
                points.append(models.PointStruct(
                    id=item['uuid'],
                    vector=vectors[idx].tolist(),
                    payload=payload
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
