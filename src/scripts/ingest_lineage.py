
import asyncio
import csv
import sys
import os
import re
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.services.kg_service import KnowledgeGraphService
from src.core.config import settings

def parse_float_percent(value):
    if not value: return 0.0
    # Remove % and parse
    clean = value.replace('%', '').strip()
    try:
        return float(clean)
    except ValueError:
        return 0.0

async def main():
    file_path = "scrape_data/scrape/cepas.csv"
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print(f"Reading {file_path} for lineage data...")
    
    kg_service = KnowledgeGraphService()
    collection = "botanical_entities"
    
    updated_count = 0
    created_count = 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            strain_name = row.get("Cepa", "").strip()
            if not strain_name: continue
            
            genetics = row.get("Origen génetico", "").strip()
            effects = row.get("Efecto", "").strip()
            flavor = row.get("Sabor", "").strip()
            thc_str = row.get("THC", "")
            cbd_str = row.get("CBD", "")
            
            # Parse Parents
            parents = []
            if genetics and genetics.lower() != "desconocido":
                # Split by ' x ' usually
                # Sometimes comma? Let's assume ' x ' for now based on header view
                parts = re.split(r'\s+x\s+', genetics)
                if len(parts) > 1:
                    parents = [p.strip() for p in parts]
                else:
                    # Maybe single parent or descriptive text
                    parents = [genetics]

            # Parse Description from other fields
            description = f"Strain: {strain_name}."
            if genetics:
                description += f" Genetics: {genetics}."
            if effects:
                description += f" Effects: {effects}."
            if flavor:
                description += f" Flavor: {flavor}."
                
            print(f"Processing {strain_name} (Parents: {parents})...")
            
            try:
                # 1. Ensure Strain Exists / Create it
                strain_id = await kg_service.add_entity_with_resolution(
                    name=strain_name,
                    type="Strain",
                    description=description,
                    collection_name=collection
                )
                
                # 2. Update Payload (Metadata)
                # We need to fetch the existing payload first to merge? 
                # Or we can just overwrite/merge with updated fields if we had a direct update method.
                # `add_entity_with_resolution` creates if new.
                # Let's use Qdrant directly to update metadata like we did in OCPDB ingest
                
                payload_update = {
                    "effects": effects,
                    "flavor": flavor
                }
                if thc_str:
                    payload_update["thc_ref"] = parse_float_percent(thc_str) # Keep separate from lab data?
                if cbd_str:
                    payload_update["cbd_ref"] = cbd_str # Allow string for 'Low/High'
                    
                kg_service.qdrant.client.set_payload(
                    collection_name=collection,
                    payload=payload_update,
                    points=[strain_id]
                )
                
                # 3. Create Parents and Relations
                for parent_name in parents:
                    if not parent_name or len(parent_name) < 2: continue
                    
                    # Create Parent Entity (Stub if not detailed)
                    parent_id = await kg_service.add_entity_with_resolution(
                        name=parent_name,
                        type="Strain", # Assume parent is strain
                        description=f"Parent strain of {strain_name}",
                        collection_name=collection
                    )
                    
                    # Add Relation: Strain -> bred_from -> Parent
                    kg_service.add_relation(
                        source_id=strain_id,
                        target_id=parent_id,
                        relation_type="bred_from",
                        collection_name=collection
                    )
                    
                    print(f"  + Relation: {strain_name} -> bred_from -> {parent_name}")
                
                updated_count += 1
                
            except Exception as e:
                print(f"Error processing {strain_name}: {e}")
                
    print(f"Lineage Ingest Complete. Processed {updated_count} strains.")

if __name__ == "__main__":
    asyncio.run(main())
