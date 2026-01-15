import asyncio
import sys
import uuid
import pandas as pd
from pathlib import Path
from tqdm import tqdm
from qdrant_client import models
import logging
import csv
from bs4 import BeautifulSoup

# Increase CSV field size limit
csv.field_size_limit(sys.maxsize)

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.services.qdrant_service import QdrantService
from src.services.embedding_service import EmbeddingService
from src.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_PATH = PROJECT_ROOT / "scrape_data" / "scrape" / "scrape.csv"
COLLECTION_NAME = "strain_genetics"

def generate_deterministic_id(name: str) -> str:
    """Generate a deterministic UUID based on the strain name."""
    name_normalized = name.strip().lower()
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name_normalized))

def split_lineage_string(text: str) -> list[str]:
    """
    Splits a lineage string by ' x ' while respecting nested parentheses.
    Example: '(A x B) x C' -> ['(A x B)', 'C']
    """
    parts = []
    current_part = []
    paren_level = 0
    
    # Simple manual parser
    i = 0
    while i < len(text):
        char = text[i]
        
        if char == '(':
            paren_level += 1
            current_part.append(char)
        elif char == ')':
            paren_level -= 1
            current_part.append(char)
        elif char == ' ' and text[i:i+3] == ' x ' and paren_level == 0:
            # Split point found
            parts.append("".join(current_part).strip())
            current_part = []
            i += 2 # Skip ' x ' (loop increments by 1 so we add 2 to skip 3 chars total)
        else:
            current_part.append(char)
        i += 1
        
    parts.append("".join(current_part).strip())
    return [p for p in parts if p]

def clean_name(name: str) -> str:
    """Removes surrounding parentheses if they enclose the whole string."""
    name = name.strip()
    while name.startswith('(') and name.endswith(')'):
        # Check if the closing parens belongs to the opening one (balanced)
        # e.g. "(A) x (B)" should NOT start/end with parens stripped implies A) x (B which is wrong.
        # But "(A x B)" -> "A x B" is good.
        
        # Check balance
        level = 0
        balanced = True
        for j, c in enumerate(name):
            if c == '(': level += 1
            elif c == ')': level -= 1
            if level == 0 and j < len(name)-1:
                balanced = False # Closed before end
                break
        
        if balanced:
            name = name[1:-1].strip()
        else:
            break
            
    return name

async def process_parent_node(name: str, qdrant: QdrantService, embedder: EmbeddingService, parent_points_batch: list) -> str | None:
    """
    Recursively processes a parent name string.
    - Resolves 'Unknown' to None.
    - If it's a cross string (A x B), creates it as a hybrid node and recursively processes A and B.
    - Returns the UUID of the resolved node.
    
    Appends new nodes to parent_points_batch to be upserted.
    """
    name = clean_name(name)
    
    if not name:
        return None
        
    # Check if this is a hybrid formula
    components = split_lineage_string(name)
    
    doc_id = generate_deterministic_id(name)
    
    if len(components) > 1:
        # It's a hybrid/cross
        # Recursively process children
        resolved_children = []
        for comp in components:
            child_id = await process_parent_node(comp, qdrant, embedder, parent_points_batch)
            if child_id:
                resolved_children.append({
                    "id": child_id,
                    "name": clean_name(comp)
                })
        
        # Create this hybrid node
        # Even if name contains "Unknown", the specific Cross is a distinct entity.
        
        text_to_embed = f"Hybrid Cross: {name}"
        vector = await embedder.embed_query_384(text_to_embed)
        
        payload = {
            "uuid": doc_id,
            "name": name,
            "description": f"Intermediate hybrid cross: {name}",
            "type": "Hybrid Cross",
            "resolved_parents": resolved_children,
            "origin": "lineage-parser"
        }
        
        point = models.PointStruct(
            id=doc_id,
            vector=vector,
            payload=payload
        )
        parent_points_batch.append(point)
        
        return doc_id
        
    else:
        # Simple leaf parent
        # Check for Unknown
        name_lower = name.lower()
        if 'unknown' in name_lower or 'legendary' in name_lower:
            # Skip creating "Unknown" leaf nodes
            return None
            
        return doc_id


async def main():
    if not DATA_PATH.exists():
        logger.error(f"Data file not found: {DATA_PATH}")
        return
        
    logger.info(f"Connecting to Qdrant at {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
    qdrant = QdrantService()
    
    try:
        collections = qdrant.client.get_collections()
        logger.info(f"Connected to Qdrant. Found {len(collections.collections)} collections.")
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant: {e}")
        return

    embedder = EmbeddingService()
    
    chunk_size = 1000
    total_processed = 0
    
    logger.info(f"Processing {DATA_PATH} in chunks of {chunk_size}...")
    
    for chunk in pd.read_csv(DATA_PATH, sep=';', chunksize=chunk_size, on_bad_lines='skip', engine='python'):
        points = []
        
        for index, row in chunk.iterrows():
            try:
                strain_name = str(row.get('Name', '')).strip()
                if not strain_name or strain_name.lower() == 'nan':
                    continue
                    
                doc_id = generate_deterministic_id(strain_name)
                
                description = str(row.get('Description', '')).replace('nan', '')
                breeder = str(row.get('Breeder', '')).replace('nan', '')
                strain_url = str(row.get('strain_detail_link-href', '')).replace('nan', '')
                
                # --- New Lineage Parsing Logic ---
                parent_tree_html = str(row.get('parent_tree', ''))
                resolved_parents_payload = []
                
                if parent_tree_html and not pd.isna(parent_tree_html):
                    soup = BeautifulSoup(parent_tree_html, 'html.parser')
                    
                    # 1. Get the first list item in the first UL. 
                    # Usually: StrainName »»» <span...>Formula</span>
                    # The structure is messy.
                    # Looking at verified Zam's Poison structure:
                    # <a...>Zam's Poison ... »»» </a> <span> ( <a...>Zamaldelica Express</a> x <a...>Mango Smile</a> ) </span> ...
                    # The formula seems to be in the first <span> AFTER the first anchor?
                    # Or just: convert the whole first block to text and split by "»»»" then take the right side?
                    
                    # Robust strategy:
                    # Remove all <ul> (recursive children) first.
                    for ul in soup.find_all('ul'):
                        ul.decompose()
                        
                    # Get text
                    full_text = soup.get_text(" ", strip=True)
                    # "Zam's Poison »»» ( Zamaldelica Express x Mango Smile ) x ( Durban Poison x Unknown Ruderalis )"
                    
                    if "»»»" in full_text:
                        formula = full_text.split("»»»", 1)[1].strip()
                        # "( Zamaldelica Express x Mango Smile ) x ( Durban Poison x Unknown Ruderalis )"
                        
                        # Process this formula using our recursive parser
                        # We gather any new intermediate nodes in `points` list too?
                        # `process_parent_node` adds to `points`.
                        
                        root_parents = split_lineage_string(formula)
                        for p_str in root_parents:
                            p_id = await process_parent_node(p_str, qdrant, embedder, points)
                            if p_id:
                                resolved_parents_payload.append({
                                    "id": p_id,
                                    "name": clean_name(p_str)
                                })
                
                payload = {
                    "uuid": doc_id,
                    "name": strain_name,
                    "breeders": [breeder] if breeder else [],
                    "description": description,
                    "resolved_parents": resolved_parents_payload,
                    "type": "Unknown",
                    "url": strain_url,
                    "html_tree": parent_tree_html[:5000],
                    "origin": "seedfinder-scrape"
                }
                
                text_to_embed = f"{strain_name} {breeder} {description}"[:1000]
                vector = await embedder.embed_query_384(text_to_embed)
                
                point = models.PointStruct(
                    id=doc_id,
                    vector=vector,
                    payload=payload
                )
                points.append(point)
                
            except Exception as e:
                # logger.warning(f"Error processing row: {e}")
                continue
        
        if points:
            try:
                qdrant.client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=points
                )
                total_processed += len(points)
                logger.info(f"Processed {total_processed} strains...")
            except Exception as e:
                logger.error(f"Error upserting batch: {e}")

    logger.info("Ingestion complete.")

if __name__ == "__main__":
    asyncio.run(main())
