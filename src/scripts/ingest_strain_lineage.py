
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

    def parse_lineage_tree(self, parent_html: str, root_name: str) -> Tuple[Dict, Set]:
        """
        Parses the nested HTML structure from seedfinder parent_tree column.
        Copied and adapted from ingest_scraped.py
        """
        if not parent_html or pd.isna(parent_html):
             return {}, set()

        # Ensure we have a root LI.
        if not parent_html.strip().lower().startswith("<li"):
             parent_html = f"<li>{parent_html}</li>"

        try:
            from bs4 import BeautifulSoup, Tag
        except ImportError:
            logger.error("BeautifulSoup not found. Please install beautifulsoup4.")
            return {}, set()

        soup = BeautifulSoup(parent_html, "html.parser")
        root_li = soup.find('li')
        
        tree_relations = {}
        found_strains = {root_name} if root_name else set()
        
        def parse_node(element: Tag, current_name: str):
             if not current_name: return
             current_name_norm = self.normalize_name(current_name)
             if not current_name_norm: return # Skip if normalization fails

             found_strains.add(current_name_norm)
             
             # Find the UL containing children/lineage info
             ul = element.find('ul', recursive=False)
             if not ul: return 
             
             for child in ul.children:
                 if child.name == 'ul':
                      # Potential Formula Wrapper (e.g., A x B)
                      for inner_li in child.find_all('li'):
                          if "»»»" in inner_li.get_text():
                              links = inner_li.find_all('a')
                              p_list = []
                              for link in links:
                                  p_name = link.get_text(strip=True)
                                  if p_name and p_name != "Unknown Ruderalis":
                                       p_norm = self.normalize_name(p_name)
                                       if p_norm: p_list.append(p_norm)
                              
                              if p_list:
                                  existing = tree_relations.get(current_name_norm, [])
                                  tree_relations[current_name_norm] = list(set(existing + p_list))
                                  found_strains.update(p_list)
                                  break 
                 
                 elif child.name == 'li':
                     li = child
                     text = li.get_text()
                     
                     # Direct LI Formula?
                     if "»»»" in text and not li.find('ul'):
                          links = li.find_all('a')
                          p_list = []
                          for link in links:
                              p_name = link.get_text(strip=True)
                              if p_name and p_name != "Unknown Ruderalis":
                                   p_norm = self.normalize_name(p_name)
                                   if p_norm: p_list.append(p_norm)
                          
                          if p_list:
                               existing = tree_relations.get(current_name_norm, [])
                               tree_relations[current_name_norm] = list(set(existing + p_list))
                               found_strains.update(p_list)
                     
                     # Definition Node (Ancestors)
                     if li.find('ul'):
                         child_name = None
                         # Helper to find direct name
                         for sub in li.children:
                             if sub.name == 'ul': break
                             if sub.name == 'a':
                                 child_name = sub.get_text(strip=True)
                                 break
                             if isinstance(sub, str) and sub.strip():
                                 if not child_name: child_name = sub.strip()

                         if child_name and child_name != current_name:
                             # Re-normalize found child name
                             child_name_norm = self.normalize_name(child_name)
                             if child_name_norm:
                                 # Add to relations
                                 existing = tree_relations.get(current_name_norm, [])
                                 if child_name_norm not in existing:
                                      existing.append(child_name_norm)
                                      tree_relations[current_name_norm] = existing
                                 
                                 # Recurse
                                 parse_node(li, child_name)
                     
                     # Simple Parent Node (Leaf)?
                     # If it's not a formula and has no children UL, checking for direct link
                     elif not li.find('ul') and "»»»" not in text:
                          # It might be a simple list of parents: <li><a href="...">Parent</a></li>
                          link = li.find('a')
                          if link:
                               p_name = link.get_text(strip=True)
                               if p_name:
                                    p_norm = self.normalize_name(p_name)
                                    if p_norm:
                                         existing = tree_relations.get(current_name_norm, [])
                                         # Add if not present
                                         if p_norm not in existing:
                                              existing.append(p_norm)
                                              tree_relations[current_name_norm] = existing
                                         found_strains.add(p_norm)

        if root_li:
             parse_node(root_li, root_name)
             
        return tree_relations, found_strains

    def load_data(self):
        logger.info("Loading CSV files...")
        
        for file_path in CSV_FILES:
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                continue

            try:
                sep = ';' if 'seedfinder' in file_path else ','
                # Special handling for scrape.csv to ensure delimiter is correct if auto-detect fails
                if 'scrape.csv' in file_path: sep = ';' 
                
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
                "breeders": set(), 
                "type": "",
                "effects": [],
                "html_tree": None
            }

            # --- Extraction Logic per File ---
            if 'seedfinder' in filename:
                name = self.normalize_name(row.get('Name der Strain'))
                p1 = self.normalize_name(row.get('Eltern 1'))
                p2 = self.normalize_name(row.get('Eltern 2'))
                if p1: strain_data['parents'].append(p1)
                if p2: strain_data['parents'].append(p2)
                br = row.get('Breeder')
                if br and not pd.isna(br): strain_data['breeders'].add(str(br).strip())
                strain_data['type'] = row.get('Typ', '')

            elif 'scrape.csv' in filename:
                name = self.normalize_name(row.get('strain_name') or row.get('Name')) # 'Name' is in header
                parent_html = row.get('parent_tree')
                
                if parent_html:
                    strain_data['html_tree'] = parent_html
                    # Parse HTML to discover parents immediately
                    relations, found_strains = self.parse_lineage_tree(parent_html, name)
                    
                    # Direct parents of THIS strain
                    if name in relations:
                        strain_data['parents'] = relations[name]
                    
                    # Also register INFERRED strains from the tree?
                    # The user asked: "Wie werden die Eltern gefunden und gespeichert (vorallem beim html code)?"
                    # We should process found_strains properly.
                    # We can iterate found_strains and add them to our global list IF they have relations too
                    for found in found_strains:
                        if found == name: continue
                        
                        # Create a partial record for found ancestor
                        ancestor_data = {
                            "source_files": [filename + " (inferred)"],
                            "parents": relations.get(found, []),
                            "description": "Inferred from lineage tree",
                            "breeders": set(),
                            "type": "Inferred",
                            "effects": [],
                            "html_tree": None
                        }
                        self._merge_strain_data(found, ancestor_data)
                
                # Fallback to direct parents column if HTML didn't yield main parents
                if not strain_data['parents'] and 'parents' in row:
                     parents_str = str(row.get('parents', ''))
                     if parents_str and parents_str != 'nan':
                         strain_data['parents'] = [self.normalize_name(p) for p in parents_str.split(',')]
                         
                br = row.get('breeder') or row.get('Breeder')
                if br and not pd.isna(br): strain_data['breeders'].add(str(br).strip())

            elif 'kushy' in filename:
                name = self.normalize_name(row.get('name'))
                strain_data['description'] = row.get('description', '')
                br = row.get('breeder')
                if br and not pd.isna(br): strain_data['breeders'].add(str(br).strip())
                
            else:
                # Generic fallback
                name_col = next((c for c in cols if 'name' in c.lower() and 'filename' not in c.lower()), None)
                if not name_col and 'Strain' in cols: name_col = 'Strain'
                if name_col:
                    name = self.normalize_name(row[name_col])
                    desc_col = next((c for c in cols if 'desc' in c.lower()), None)
                    if desc_col: strain_data['description'] = row[desc_col]
                    br_col = next((c for c in cols if 'breeder' in c.lower()), None)
                    if br_col:
                        br = row[br_col]
                        if br and not pd.isna(br): strain_data['breeders'].add(str(br).strip())

            if name:
                self._merge_strain_data(name, strain_data)

    def _merge_strain_data(self, name: str, new_data: Dict[str, Any]):
        if name not in self.strains:
            self.strains[name] = {
                "name": name,
                "uuid": self.generate_uuid(name),
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
             # Union parents from authoritative sources
             existing['parents'] = list(set(existing['parents'] + new_data['parents']))
        
        if new_data['html_tree'] and not existing['html_tree']:
            existing['html_tree'] = new_data['html_tree']
            
        if new_data['breeders']:
            existing['breeders'].update(new_data['breeders'])

        if len(str(new_data['description'])) > len(str(existing['description'])):
             existing['description'] = new_data['description']

    def resolve_references(self):
        """
        Convert text parent names to UUID references.
        AUTO-CREATE missing parents as full nodes.
        """
        logger.info("Resolving lineage references and creating missing nodes...")
        
        new_nodes = {}
        
        for name, data in self.strains.items():
            for p_name in data['parents']:
                if not p_name: continue
                
                if p_name not in self.strains and p_name not in new_nodes:
                    # Create new node for missing parent
                    logger.debug(f"Creating missing node for parent: {p_name}")
                    new_nodes[p_name] = {
                        "name": p_name,
                        "uuid": self.generate_uuid(p_name),
                        "parents": [],
                        "breeders": set(["Unknown"]), 
                        "description": "Auto-created parent node",
                        "type": "Unknown",
                        "effects": [],
                        "sources": ["auto-generated"],
                        "html_tree": None
                    }
        
        if new_nodes:
            logger.info(f"Adding {len(new_nodes)} auto-created parent nodes.")
            self.strains.update(new_nodes)

        for name, data in self.strains.items():
            resolved_parents = []
            for p_name in data['parents']:
                if not p_name: continue
                # Prevent self-loops
                if p_name == name: continue
                
                if p_name in self.strains:
                    resolved_parents.append({
                        "name": p_name,
                        "id": self.strains[p_name]['uuid']
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
