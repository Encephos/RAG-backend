
import asyncio
import csv
import sys
import os
from collections import defaultdict
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.services.kg_service import KnowledgeGraphService
from src.services.qdrant_service import QdrantService
from src.core.config import settings

# Terpenes of interest to extract
TARGET_TERPENES = [
    "α-Pinene", "Camphene", "Myrcene", "β-Pinene", "3-Carene", 
    "α-Terpinene", "D-Limonene", "p-Cymene", "Ocimene", "Eucalyptol", 
    "γ-Terpinene", "Terpinolene", "Linalool", "Isopulegol", "Geraniol", 
    "β-Caryophyllene", "α-Humelene", "Nerolidol-1", "Nerolidol-2", 
    "Guaiol", "CaryophylleneOxide", "α-Bisabolol"
]

def parse_float(value):
    if not value or value.strip() == '':
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0

async def main():
    file_path = "scrape_data/scrape/OCPDB.csv"
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print("Reading CSV...")
    
    strain_data = defaultdict(list)
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            strain = row.get("Strain")
            if not strain:
                continue
                
            # Normalize strain name (lowercase, strip)? 
            # Better keep implementation casing but strip
            strain = strain.strip()
            
            data_point = {
                "thc": parse_float(row.get("TotalTHC", "0")),
                "cbd": parse_float(row.get("TotalCBD", "0")),
                "cbg": parse_float(row.get("CBG", "0")),
                "cbn": parse_float(row.get("CBN", "0")),
                "thcv": parse_float(row.get("THCV", "0")),
                "terpenes": {}
            }
            
            for terp in TARGET_TERPENES:
                val = parse_float(row.get(terp, "0"))
                if val > 0:
                    data_point["terpenes"][terp] = val
            
            strain_data[strain].append(data_point)
            count += 1
            
    print(f"Loaded {count} samples for {len(strain_data)} unique strains.")
    
    kg_service = KnowledgeGraphService()
    # We need to access qdrant directly to scroll/search
    qdrant = kg_service.qdrant
    
    # We will target the botanical_entities collection
    collection = "botanical_entities" 
    
    print("Starting ingestion...")
    updated_count = 0
    created_count = 0
    
    # Process averaged data
    for strain_name, samples in strain_data.items():
        # Average the values
        n = len(samples)
        avg_thc = sum(s["thc"] for s in samples) / n
        avg_cbd = sum(s["cbd"] for s in samples) / n
        avg_cbg = sum(s["cbg"] for s in samples) / n
        avg_cbn = sum(s["cbn"] for s in samples) / n
        avg_thcv = sum(s["thcv"] for s in samples) / n
        
        # Average terpenes
        avg_terpenes = {}
        for terp in TARGET_TERPENES:
            total_val = sum(s["terpenes"].get(terp, 0) for s in samples)
            avg_val = total_val / n
            if avg_val > 0.01: # Filter trace amounts
                avg_terpenes[terp] = round(avg_val, 3)

        # Prepare payload update
        chem_profile = {
            "thc": round(avg_thc, 2),
            "cbd": round(avg_cbd, 2),
            "cbg": round(avg_cbg, 2),
            "cbn": round(avg_cbn, 2),
            "thcv": round(avg_thcv, 2),
            "terpenes": avg_terpenes,
            "sample_count": n
        }
        
        # Check if entity exists
        # Use simple Scroll by name filter first (faster than embedding for exact match)
        # Note: 'name' field in payload
        # This duplicates logic in get_lineage but useful here
        from qdrant_client import models
        
        existing_points = qdrant.client.scroll(
            collection_name=collection,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="name",
                        match=models.MatchValue(value=strain_name)
                    )
                ]
            ),
            limit=1,
            with_payload=True
        )[0]
        
        if existing_points:
            # Update existing
            point = existing_points[0]
            current_payload = point.payload
            
            # Merge payload
            current_payload.update(chem_profile)
            
            qdrant.client.set_payload(
                collection_name=collection,
                payload=current_payload,
                points=[point.id]
            )
            updated_count += 1
            if updated_count % 50 == 0:
                print(f"Updated {updated_count} strains...")
        else:
            # Create new entity
            # We need an embedding for the new entity
            # Description is just basic info since we only have chem data
            description = f"Strain: {strain_name}. Chemical Profile: THC {chem_profile['thc']}%, CBD {chem_profile['cbd']}%."
            top_terps = sorted(avg_terpenes.items(), key=lambda x: x[1], reverse=True)[:3]
            if top_terps:
                description += f" Top Terpenes: {', '.join([f'{t[0]} ({t[1]}%)' for t in top_terps])}."
            
            try:
                # Add via KG Service to handle embedding and ID creation
                await kg_service.add_entity_with_resolution(
                    name=strain_name,
                    type="Strain",
                    description=description,
                    collection_name=collection
                )
                
                # Now we need to add the extra fields (thc, cbd, terpenes) which add_entity doesn't natively support
                # We fetch it back (should be found by scroll now)
                # Or we can just update the payload if we had the ID. 
                # add_entity returns ID.
                # Oh wait, I see `add_entity_with_resolution` logic.. let's check it. 
                # It accepts name, type, description.
                # Returns ID.
                
                # Re-fetch or search to update payload isn't efficient but we can't easily pass extra payload to that function currently.
                # Let's modify the function later or just use the ID returned.
                
                # Re-scroll to find ID (since add_entity uses resolution, it might return existing ID if fuzzy match matches)
                # Actually let's assume we want to update it regardless.
                
                # Rerunning scroll finding...
                new_points = qdrant.client.scroll(
                   collection_name=collection,
                    scroll_filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="name",
                                match=models.MatchValue(value=strain_name)
                            )
                        ]
                    ),
                    limit=1
                )[0]
                
                if new_points:
                     qdrant.client.set_payload(
                        collection_name=collection,
                        payload=chem_profile,
                        points=[new_points[0].id]
                    )
                
                created_count += 1
                if created_count % 50 == 0:
                    print(f"Created {created_count} strains...")

            except Exception as e:
                print(f"Error creating {strain_name}: {e}")

    print(f"Done. Updated: {updated_count}, Created: {created_count}")

if __name__ == "__main__":
    asyncio.run(main())
