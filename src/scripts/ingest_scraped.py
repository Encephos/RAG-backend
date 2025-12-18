
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

# Add project root to sys.path
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)

# Mock settings/service for standalone execution if needed, 
# or import from app if available.
try:
    from src.services.qdrant_service import QdrantService
    from src.core.config import settings
except ImportError:
    # Fallback for standalone testing typically not needed if run from root
    logger.error("Could not import QdrantService. Run this script from project root.")
    exit(1)

DATA_DIR = "scrape_data/scrape"

class ScrapedDataIngestor:
    def __init__(self):
        self.qdrant = QdrantService()
        self.batch_size = 50 

    async def run(self):
        logger.info("Starting ingestion of scraped data...")
        
        files = [f for f in os.listdir(DATA_DIR) if os.path.isfile(os.path.join(DATA_DIR, f))]
        
        if len(sys.argv) > 1:
            filter_name = sys.argv[1]
            logger.info(f"Filtering files with keyword: '{filter_name}'")
            files = [f for f in files if filter_name in f]
        
        if not files:
            logger.warning("No files found to process.")
            return

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

        elif "strainmaster.csv" in filename:
             with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Helper to aggregate numbered columns
                    def collect_columns(prefix, max_count=10):
                        values = []
                        for i in range(1, max_count + 1):
                            val = row.get(f"{prefix}_{i}")
                            if val and val.strip():
                                values.append(val.strip())
                        return ", ".join(values)

                    normalized_data.append({
                        "name": row.get("Name"),
                        "description": row.get("Description"),
                        "type": row.get("strain_type"),
                        "cannabinoids": collect_columns("cannabinoids", 6),
                        "aromas": collect_columns("aromas", 10),
                        "flavors": collect_columns("flavors", 10),
                        "terpenes": collect_columns("terpene", 8),
                        "effects": collect_columns("effects", 7),
                        "negative_effects": collect_columns("negative_effects", 10),
                        "medical": collect_columns("medical_application", 5),
                        "growing": row.get("Growing"),
                        "source_file": filename
                    })

        elif "scrape.csv" in filename:
             csv.field_size_limit(sys.maxsize)
             try:
                 from bs4 import BeautifulSoup, Tag
                 import re
             except ImportError:
                 logger.error("BeautifulSoup not found. Please install beautifulsoup4.")
                 return []
             
             with open(filepath, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f, delimiter=";")
                count = 0
                for row in reader:
                    count += 1
                    if count % 1000 == 0:
                        logger.info(f"Parsing scrape.csv row {count}...")
                        
                    main_name = row.get("Name")
                    parent_html = row.get("parent_tree")
                    
                    # Map of Child -> [Parents] for this entire tree
                    tree_relations = {}
                    
                    if parent_html:
                        soup = BeautifulSoup(parent_html, "html.parser")
                        root_li = soup.find('li')
                        
                        def parse_node(element: Tag, current_name: str):
                             if not current_name: return
                             
                             # Find the UL containing children/lineage info
                             # Usually a direct child of the LI
                             ul = element.find('ul', recursive=False)
                             if not ul: return 
                             
                             # 1. Iterate direct children to find Formula (wrapped in UL?) vs Definitions (LI)
                             # Validated logic from verify_lineage_extraction.py
                             
                             for child in ul.children:
                                 if child.name == 'ul':
                                      # Potential Formula Wrapper
                                      for inner_li in child.find_all('li'):
                                          if "»»»" in inner_li.get_text():
                                              # Found Formula
                                              links = inner_li.find_all('a')
                                              p_list = []
                                              for link in links:
                                                  # Filter noise
                                                  p_name = link.get_text(strip=True)
                                                  if p_name and p_name != "Unknown Ruderalis":
                                                       p_list.append(p_name)
                                              
                                              if p_list:
                                                  tree_relations[current_name] = list(set(tree_relations.get(current_name, []) + p_list))
                                              break # Found formula in this wrapper
                                 
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
                                                   p_list.append(p_name)
                                          
                                          if p_list:
                                               tree_relations[current_name] = list(set(tree_relations.get(current_name, []) + p_list))
                                     
                                     # Definition Node (Ancestors)
                                     if li.find('ul'):
                                         child_name = None
                                         # Robust name extraction: split before UL
                                         pre_ul_html = str(li).split('<ul')[0]
                                         pre_soup = BeautifulSoup(pre_ul_html, "html.parser")
                                         child_a = pre_soup.find('a')

                                         if child_a:
                                             child_name = child_a.get_text(strip=True)
                                         else:
                                             # Text-only node?
                                             raw_text = pre_soup.get_text(strip=True)
                                             if raw_text and len(raw_text) > 1:
                                                 child_name = raw_text.strip()

                                         if child_name and child_name != current_name:
                                             # It is a parent/ancestor!
                                             # Add it to the relations for current_name
                                             tree_relations[current_name] = list(set(tree_relations.get(current_name, []) + [child_name]))
                                             
                                             parse_node(li, child_name)

                        if root_li:
                            parse_node(root_li, main_name)

                    # 1. Main Item
                    normalized_data.append({
                        "name": main_name,
                        "description": row.get("Description"), 
                        "breeder": row.get("Breeder"),
                        "type": "Strain",
                        "lineage": ", ".join(tree_relations.get(main_name, [])), # Main parents
                        "source_file": filename
                    })
                    
                    # 2. Inferred Ancestor Items
                    # For every other entry in tree_relations, create a lightweight item
                    for child, parents in tree_relations.items():
                        if child == main_name: continue
                        
                        normalized_data.append({
                            "name": child,
                            "type": "Strain (Inferred)",
                            "lineage": ", ".join(parents),
                            "source_file": filename, # track source
                            "is_inferred": True # Helper flag
                        })

        return normalized_data

    async def _ingest_batch(self, data: List[Dict[str, Any]], filename: str):
        """Ingests normalized data into Knowledge and Entity collections."""
        
        # We process in small chunks to avoid memory/rate issues
        chunk_size = 50
        total_batches = (len(data) // chunk_size) + 1
        
        for i in range(0, len(data), chunk_size):
             batch = data[i:i + chunk_size]
             current_batch = (i // chunk_size) + 1
             
             if current_batch % 10 == 0:
                 logger.info(f"[{filename}] Processing batch {current_batch}/{total_batches} ({i}/{len(data)} items)...")
             
             # Prepare Entity Points (Graph)
             # Entities collection needs: id, vector (placeholder or named vector), payload
             for item in batch:
                 await self._upsert_item(item)
    
    def _extract_parents(self, text: str) -> List[str]:
        """Simple heuristic to extract parents from text."""
        if not text: return []
        import re
        parents = []
        
        # Pattern: "cross between X and Y"
        match = re.search(r"cross between\s+([A-Z0-9][a-zA-Z0-9\s\-\#]+?)\s+and\s+([A-Z0-9][a-zA-Z0-9\s\-\#]+)", text, re.IGNORECASE)
        if match:
            parents.extend([m.strip() for m in match.groups()])
            
        # Pattern: "bred from X"
        match_bred = re.search(r"bred from\s+([A-Z0-9][a-zA-Z0-9\s\-\#]+)", text, re.IGNORECASE)
        if match_bred:
             parents.append(match_bred.group(1).strip())

        return [p for p in parents if len(p) > 2 and len(p) < 40]

    async def _upsert_item(self, item: Dict[str, Any]):
        name = item.get("name")
        if not name or not name.strip(): 
            return

        # 1. ENTITY (Graph Node)
        entity_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, name))
        
        text_content = f"Strain: {name}\n"
        for k, v in item.items():
            if v and k not in ['name', 'source_file']:
                text_content += f"{k.capitalize()}: {v}\n"
        
        # Embeddings
        try:
             from fastembed import TextEmbedding
             if not hasattr(self, 'model'):
                 self.model = TextEmbedding(model_name=settings.EMBEDDING_MODEL_NAME)
        except ImportError:
             logger.error("Fastembed not found.")
             return

        embeddings = list(self.model.embed([text_content]))
        vector = [float(x) for x in embeddings[0]]

        # Upsert Knowledge
        self.qdrant.upsert(
            text=text_content,
            vector=vector,
            metadata={"source": item.get('source_file'), "type": "scraped_data", "strain": name},
            collection_alias="botanical"
        )
        self.qdrant.upsert(
            text=text_content,
            vector=vector,
            metadata={"source": item.get('source_file'), "type": "scraped_data", "strain": name},
            collection_alias="master"
        )
        
        # 2. RELATIONS (Edges)
        # Try to find parents in description or explicit fields
        parents = self._extract_parents(item.get("description", ""))
        
        # If 'lineage' key exists in item (from CSV), use it
        if item.get("lineage"):
             parents.extend([p.strip() for p in item.get("lineage").split(",") if p.strip()])
             
        relations = []
        for parent_name in set(parents):
            if parent_name.lower() == name.lower(): continue # Self-ref loop check
            
            parent_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, parent_name))
            relations.append({
                "type": "bred_from",
                "target_id": parent_id,
                "target_label": parent_name # Store label to avoid fetching target just for name
            })

        # Upsert Entity with Relations
        name_emb = list(self.model.embed([name]))[0]
        name_vector = [float(x) for x in name_emb]
        
        payload = {**item, "entity_type": "strain", "label": name, "relations": relations}
        
        self.qdrant.upsert_entity(
            entity_id=entity_id,
            vector=name_vector,
            payload=payload,
            collection_name="botanical_entities"
        )
        
        self.qdrant.upsert_entity(
            entity_id=entity_id,
            vector=name_vector,
            payload=payload,
            collection_name=settings.QDRANT_ENTITY_COLLECTION_NAME 
        )

if __name__ == "__main__":
    ingestor = ScrapedDataIngestor()
    asyncio.run(ingestor.run())
