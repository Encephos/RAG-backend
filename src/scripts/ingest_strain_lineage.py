
import os
import pandas as pd
import glob
from typing import List, Dict, Any, Optional, Set
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
import uuid
import logging
from bs4 import BeautifulSoup
import re
from tqdm import tqdm
from dotenv import load_dotenv

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# --- Config & Normalization ---

COLLECTION_NAME = "strain_lineage_data"
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

def normalize_name(name: Any) -> Optional[str]:
    if pd.isna(name) or not name:
        return None
    # Aggressive normalization:
    n = str(name).lower().strip()
    # Remove text in brackets [] (phenos)
    n = re.sub(r'\[.*?\]', '', n)
    # Remove specific noise pattern
    n = n.replace('(ibl)', '').replace(' ibl', '') 
    # Cleanup spaces
    n = re.sub(r'\s+', ' ', n).strip()
    
    # Remove surrounding parentheses if present (common in intermediate nodes)
    # e.g. "(Grape Ape x Grapefruit)" -> "Grape Ape x Grapefruit"
    if n.startswith('(') and n.endswith(')'):
        n = n[1:-1].strip()
        
    return n if n else None

def generate_uuid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))

class StrainIngester:
    def __init__(self):
        self.qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        
        # In-memory storage: normalized_name -> strain_data_dict
        self.strains: Dict[str, Dict[str, Any]] = {}
        
        # Statistics
        self.stats = {"primary": 0, "secondary": 0, "new_from_secondary": 0, "merged": 0}

    def _init_strain_entry(self, name: str, normalized_name: str, source_type: str) -> Dict[str, Any]:
        """Creates a fresh strain entry skeleton."""
        return {
            "name": name, # Keep original casing of first finding? Or Title Case?
            "normalized_name": normalized_name,
            "uuid": generate_uuid(normalized_name),
            "description": "",
            "breeders": set(),
            "lineage": {}, # Store parent structure
            "html_tree": None, # Raw seedfinder tree
            "type": None, # Indica/Sativa
            
            # Aggregate Fields (Lists for multiple values from different sources)
            "thc": [],
            "cbd": [],
            "terpenes": set(),
            "effects": set(),
            "flavors": set(),
            
            # Management
            "primary_source_loaded": (source_type == "primary"),
            "sources": set()
        }

    def process_primary_source(self, filepath: str):
        """Loads scrape.csv as the Source of Truth."""
        logger.info(f"Loading Primary Source: {filepath}")
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return

        df = pd.read_csv(filepath)
        # Expected columns: Strain, Breeder, Description, parent_tree, Type (maybe)
        # Check actual columns from task mapping or inspection
        # scrape.csv: Strain, Breeder, Description, parent_tree, (others?)
        
        for _, row in tqdm(df.iterrows(), total=len(df), desc="Primary Ingest"):
            raw_name = row.get("Strain")
            norm_name = normalize_name(raw_name)
            if not norm_name: continue
            
            if norm_name not in self.strains:
                self.strains[norm_name] = self._init_strain_entry(raw_name, norm_name, "primary")
                self.stats["primary"] += 1
            
            entry = self.strains[norm_name]
            
            # Update Truth Data
            entry["primary_source_loaded"] = True
            entry["sources"].add("scrape.csv")
            
            if pd.notna(row.get("Breeder")):
                entry["breeders"].add(str(row.get("Breeder")).strip())
            
            if pd.notna(row.get("Description")) and not entry["description"]:
                 entry["description"] = str(row.get("Description")).strip()
            
            # HTML Tree logic
            html = row.get("parent_tree")
            if pd.notna(html) and html:
                 entry["html_tree"] = html 
                 # We parse this later or on-the-fly? 
                 # Let's verify lineage extraction logic if needed, but for now store it.
            
            if pd.notna(row.get("Type")):
                entry["type"] = str(row.get("Type")).strip()

    def process_secondary_source(self, filepath: str, file_type: str):
        """Generic handler for secondary files."""
        logger.info(f"Loading Secondary Source: {filepath} ({file_type})")
        if not os.path.exists(filepath):
             logger.warning(f"File skipped (not found): {filepath}")
             return

        try:
            df = pd.read_csv(filepath, low_memory=False) # low_memory=False for mixed types
        except Exception as e:
            logger.error(f"Failed to read {filepath}: {e}")
            return

        for _, row in tqdm(df.iterrows(), total=len(df), desc=f"Enrich: {file_type}"):
            # 1. Determine Name Column based on file_type
            raw_name = self._extract_name(row, file_type)
            norm_name = normalize_name(raw_name)
            if not norm_name: continue

            # 2. Link or Create
            if norm_name not in self.strains:
                self.strains[norm_name] = self._init_strain_entry(raw_name, norm_name, "secondary")
                self.stats["new_from_secondary"] += 1
            else:
                self.stats["merged"] += 1
            
            entry = self.strains[norm_name]
            entry["sources"].add(os.path.basename(filepath))
            
            # 3. Enrich Data
            self._enrich_entry(entry, row, file_type)

    def _extract_name(self, row: pd.Series, file_type: str) -> Optional[str]:
        if file_type == "cannabis-strains-final": return row.get("strain_name")
        elif file_type == "cannabis": return row.get("Strain")
        elif file_type == "cepas": return row.get("Cepa")
        elif file_type == "leafly": return row.get("name")
        elif file_type == "ocpdb": return row.get("Strain")
        elif file_type == "results": return row.get("Sample Name")
        elif file_type == "strainmaster": return row.get("Name")
        elif file_type == "kushy": return row.get("name")
        return None

    def _enrich_entry(self, entry: Dict, row: pd.Series, file_type: str):
        # Helper to safely add valid floats/strings
        def add_val(target_list, val):
            try:
                if pd.notna(val):
                    # Clean % signs or text
                    v_str = str(val).replace('%', '').strip()
                    v_float = float(v_str)
                    if v_float > 0: target_list.append(v_float)
            except: pass

        def add_set(target_set, val):
            if pd.notna(val):
                target_set.add(str(val).strip())

        # Mapping Logic
        if file_type == "cannabis-strains-final":
            add_val(entry["thc"], row.get("thc"))
            add_val(entry["cbd"], row.get("cbd"))
            add_set(entry["effects"], row.get("effect")) # Check if comma list?
            if pd.notna(row.get("effect")):
                for e in str(row.get("effect")).split(','): entry["effects"].add(e.strip())

        elif file_type == "cannabis":
             if pd.notna(row.get("Effects")):
                 for e in str(row.get("Effects")).split(','): entry["effects"].add(e.strip())
             if pd.notna(row.get("Flavor")):
                 for f in str(row.get("Flavor")).split(','): entry["flavors"].add(f.strip())

        elif file_type == "cepas":
             add_val(entry["thc"], row.get("THC"))
             add_val(entry["cbd"], row.get("CBD"))

        elif file_type == "leafly":
             add_val(entry["thc"], row.get("thc_level"))
             add_set(entry["terpenes"], row.get("most_common_terpene"))
             # Leafly has bool columns for effects (happy, relaxed, etc)
             possible_effects = ["relaxed", "happy", "euphoric", "uplifted", "sleepy", "creative", "energetic", "focused"]
             for eff in possible_effects:
                 if row.get(eff) == 1 or str(row.get(eff)).lower() == 'true':
                     entry["effects"].add(eff.capitalize())

        elif file_type == "ocpdb":
             add_val(entry["thc"], row.get("TotalTHC"))
             add_val(entry["cbd"], row.get("TotalCBD"))
             
             # OCPDB Terpene Columns based on header
             terp_cols = [
                 "α-Pinene", "Camphene", "Myrcene", "β-Pinene", "3-Carene", "α-Terpinene", 
                 "D-Limonene", "p-Cymene", "Ocimene", "Eucalyptol", "γ-Terpinene", "Terpinolene", 
                 "Linalool", "Isopulegol", "Geraniol", "β-Caryophyllene", "α-Humelene", 
                 "Nerolidol-1", "Nerolidol-2", "Guaiol", "CaryophylleneOxide", "α-Bisabolol"
             ]
             for col in terp_cols:
                 try:
                     val = row.get(col)
                     if pd.notna(val) and float(val) > 0:
                         # Normalize name (remove greek letters for searchability?)
                         # Or keep scientific name. Let's keep name as is but strip potential junk.
                         t_name = col.replace('α-', 'Alpha-').replace('β-', 'Beta-').replace('γ-', 'Gamma-')
                         entry["terpenes"].add(t_name)
                 except: pass

        elif file_type == "results":
             add_val(entry["thc"], row.get("delta-9 THC"))
             try:
                 if "Total THC" in row: add_val(entry["thc"], row.get("Total THC"))
             except: pass
             add_val(entry["cbd"], row.get("CBD"))
             
             # Results CSV Terpenes
             res_terps = [
                 "cis-Nerolidol", "trans-Nerolidol", "trans-Ocimene", "3-Carene", "Camphene", 
                 "Caryophyllene Oxide", "Eucalyptol", "Geraniol", "Guaiol", "Isopulegol", 
                 "Linalool", "Ocimene", "Terpinolene", "alpha-Bisabolol", "alpha-Humulene", 
                 "alpha-Pinene", "alpha-Terpinene", "beta-Caryophyllene", "beta-Myrcene", 
                 "beta-Ocimene", "beta-Pinene", "delta-Limonene", "gamma-Terpinene", "p-Cymene"
             ]
             for col in res_terps:
                 try:
                     val = row.get(col)
                     if pd.notna(val) and float(val) > 0:
                         entry["terpenes"].add(col)
                 except: pass

        elif file_type == "kushy":
             add_val(entry["thc"], row.get("thc"))
             add_val(entry["cbd"], row.get("cbd"))
             if pd.notna(row.get("terpenes")): entry["terpenes"].add(row.get("terpenes"))

    # --- HTML Parsing & Lineage Resolution ---

    def parse_lineage_tree_static(self, parent_html: str, root_name: str) -> tuple[dict, set]:
        """
        Parses the nested HTML structure from seedfinder parent_tree column.
        (Ported from src/scripts/ingest_scraped.py as per user request)
        Returns (relations_dict, all_found_strains_set)
        """
        if not parent_html:
             return {}, set()

        # Ensure we have a root LI.
        if not parent_html.strip().lower().startswith("<li"):
             parent_html = f"<li>{parent_html}</li>"

        try:
            from bs4 import BeautifulSoup, Tag
        except ImportError:
            logger.error("BeautifulSoup not found.")
            return {}, set()

        soup = BeautifulSoup(parent_html, "html.parser")
        root_li = soup.find('li')
        
        tree_relations = {}
        found_strains = {normalize_name(root_name)} if root_name else set()
        
        def parse_node(element: Tag, current_name_raw: str):
             current_name = normalize_name(current_name_raw)
             if not current_name: return
             found_strains.add(current_name)
             
             # Find the UL containing children/lineage info
             ul = element.find('ul', recursive=False)
             if not ul: return 
             
             for child in ul.children:
                 if child.name == 'ul':
                      # Potential Formula Wrapper (Seedfinder specific)
                      for inner_li in child.find_all('li'):
                          if "»»»" in inner_li.get_text():
                               links = inner_li.find_all('a')
                               p_list = []
                               for link in links:
                                   p_name = normalize_name(link.get_text(strip=True))
                                   if p_name and "unknown" not in p_name:
                                        p_list.append(p_name)
                               
                                   if p_list:
                                       existing = tree_relations.get(current_name, [])
                                       # Direction: Current -> [Parents]
                                       tree_relations[current_name] = list(set(existing + p_list))
                                       found_strains.update(p_list)
                                   # We don't recurse into formula nodes usually as they are leaves
                                   break 
                 
                 elif child.name == 'li':
                     li = child
                     text = li.get_text()
                     
                     # Check for Direct Formula in LI
                     if "»»»" in text and not li.find('ul'):
                          links = li.find_all('a')
                          p_list = []
                          for link in links:
                              p_name = normalize_name(link.get_text(strip=True))
                              if p_name and "unknown" not in p_name:
                                   p_list.append(p_name)
                          
                          if p_list:
                               existing = tree_relations.get(current_name, [])
                               tree_relations[current_name] = list(set(existing + p_list))
                               found_strains.update(p_list)
                     
                     # Definition Node (Standard Ancestors)
                     if li.find('ul'):
                         child_name = None
                         # Helper to find direct name of this node (The Intermediate "A x B")
                         for sub in li.children:
                             if sub.name == 'ul': break
                             if sub.name == 'a':
                                 child_name = sub.get_text(strip=True)
                                 break
                             if isinstance(sub, str) and sub.strip():
                                 if not child_name: child_name = sub.strip()

                         # If text node contains "x" and looks like a cross name, use it
                         # Logic from previous fix: Capture full text including links!
                         # Re-applying the "Full Text" fix within this structure:
                         full_text = ""
                         li_clone = li.__copy__()
                         if li_clone.find('ul'): li_clone.find('ul').decompose()
                         full_text = li_clone.get_text(" ", strip=True).replace('»', '').strip()
                         
                         if full_text and len(full_text) > 2:
                             child_name = full_text

                         child_norm = normalize_name(child_name)

                         if child_norm and child_norm != current_name:
                             # Add to relations
                             existing = tree_relations.get(current_name, [])
                             if child_norm not in existing:
                                  existing.append(child_norm)
                                  tree_relations[current_name] = existing
                             
                             # Recurse
                             parse_node(li, child_name)
                     
                     else:
                         # Simple Leaf Node (e.g. <li><a href>Strain A</a></li>)
                         p_name = None
                         link = li.find('a')
                         if link:
                             p_name = link.get_text(strip=True)
                         else:
                             p_name = li.get_text(strip=True)
                         
                         p_norm = normalize_name(p_name)
                         if p_norm and p_norm != current_name:
                             existing = tree_relations.get(current_name, [])
                             if p_norm not in existing:
                                  existing.append(p_norm)
                                  tree_relations[current_name] = existing
                                  found_strains.add(p_norm)
                             
        if root_li:
             parse_node(root_li, root_name)
             
        return tree_relations, found_strains

    def _resolve_lineage(self):
        """
        Iterates all strains. If they have HTML tree, parses it.
        1. Updates entry['lineage'] with immediate parents.
        2. Creates 'Ghost Nodes' for ancestors found in tree but missing in DB.
        """
        logger.info("Resolving Lineage...")
        
        # Snapshot of keys to avoid runtime change error during iteration
        current_keys = list(self.strains.keys())
        
        for name in tqdm(current_keys, desc="Parsing Trees"):
            entry = self.strains[name]
            html = entry.get("html_tree")
            
            if html:
                rels, found_strains = self.parse_lineage_tree_static(html, entry['name'])
                
                # rels contains: {MainStrain: [ParentA, ParentB], ParentA: [GrandParentC]}
                
                # 1. Register inferred strains first
                for s_norm in found_strains:
                    if s_norm not in self.strains:
                         # Infer name casing from norm (not ideal, but better than nothing)
                         self.strains[s_norm] = self._init_strain_entry(s_norm.title(), s_norm, "inferred")
                         self.stats["new_from_secondary"] += 1

                # 2. Link Resolved Parents
                for child_norm, parents_norm in rels.items():
                    # Ensure child exists (it might be an intermediate node discovered)
                    if child_norm not in self.strains:
                        self.strains[child_norm] = self._init_strain_entry(child_norm.title(), child_norm, "inferred")
                        self.stats["new_from_secondary"] += 1 # Count as inferred
                    
                    # Ensure parents exist
                    resolved_parents = []
                    for p_norm in parents_norm:
                         if p_norm not in self.strains:
                             self.strains[p_norm] = self._init_strain_entry(p_norm.title(), p_norm, "inferred")
                             self.stats["new_from_secondary"] += 1
                         
                         p_entry = self.strains[p_norm]
                         resolved_parents.append({
                             "name": p_entry["name"],
                             "id": p_entry["uuid"]
                         })
                    
                    # Update Child's resolved parents logic
                    # We store them in a way Qdrant payload expects: "resolved_parents" list
                    self.strains[child_norm]["resolved_parents"] = resolved_parents

    # --- Upload ---
    def _upload_batches(self):
        BATCH_SIZE = 100
        batch_points = []
        
        logger.info(f"Starting Upload... Total: {len(self.strains)}")
        
        # Prepare Queue
        items = list(self.strains.values())
        
        for i, entry in enumerate(tqdm(items, desc="Uploading")):
            # Vectorize
            # Use Name + Description for rich semantic search
            text = f"{entry['name']}"
            if entry['description']:
                text += f": {entry['description'][:500]}"
            
            vector = self.model.encode(text).tolist()
            
            # Prepare Payload
            # Convert sets to lists
            payload = {
                "uuid": entry["uuid"],
                "name": entry["name"],
                "normalized_name": entry["normalized_name"],
                "description": entry["description"],
                "type": entry["type"],
                "breeders": list(entry["breeders"]),
                "thc": entry["thc"], # Keep as list of measurements? Or Avg?
                # User asked to "append info". Storing all vals is safer for stats.
                "cbd": entry["cbd"],
                "terpenes": list(entry["terpenes"]),
                "effects": list(entry["effects"]),
                "flavors": list(entry["flavors"]),
                "html_tree": entry["html_tree"],
                "resolved_parents": entry.get("resolved_parents", []),
                "source_files": list(entry["sources"])
            }
            
            point = models.PointStruct(
                id=entry["uuid"],
                vector=vector,
                payload=payload
            )
            batch_points.append(point)
            
            if len(batch_points) >= BATCH_SIZE:
                self._upsert_batch(batch_points)
                batch_points = []
        
        if batch_points:
            self._upsert_batch(batch_points)

    def _upsert_batch(self, points):
        try:
            self.qdrant.upsert(
                collection_name=COLLECTION_NAME,
                points=points,
                wait=False
            )
        except Exception as e:
            logger.error(f"Batch upsert failed: {e}")

    def ingest(self):
        # 1. Primary
        self.process_primary_source("scrape_data/scrape/scrape.csv")
        
        # 2. Secondary
        sources = [
            ("scrape_data/scrape/cannabis-strains-final.csv", "cannabis-strains-final"),
            ("scrape_data/scrape/cannabis.csv", "cannabis"),
            ("scrape_data/scrape/cepas.csv", "cepas"),
            ("scrape_data/scrape/leafly_strain_data.csv", "leafly"),
            ("scrape_data/scrape/OCPDB.csv", "ocpdb"),
            ("scrape_data/scrape/results.csv", "results"),
            ("scrape_data/scrape/strainmaster.csv", "strainmaster"),
            ("scrape_data/scrape/strains-kushy_api.2017-11-14.csv", "kushy")
        ]
        
        for fp, ft in sources:
            self.process_secondary_source(fp, ft)

        logger.info(f"Final Stats: {self.stats}")
        logger.info(f"Total Strains to Upsert: {len(self.strains)}")

        # 3. Resolve Parents & Lineage
        self._resolve_lineage()
        
        # 4. Upsert
        # Re-create Collection first to ensure clean state
        try:
             self.qdrant.recreate_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
             )
        except Exception as e:
             logger.warning(f"Collection recreate skipped/failed: {e}")

        self._upload_batches()

if __name__ == "__main__":
    ingester = StrainIngester()
    ingester.ingest()
