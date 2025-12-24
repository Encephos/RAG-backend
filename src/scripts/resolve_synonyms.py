
import asyncio
import sys
from pathlib import Path
from qdrant_client import models

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.services.kg_service import KnowledgeGraphService

async def main():
    kg = KnowledgeGraphService()
    client = kg.qdrant.client
    collection = "botanical_entities"
    
    # 1. Define Known Synonyms / Duplicates to Merge
    # Format: "Slave (Merge From)" -> "Master (Merge Into)"
    
    # Specific merges requested/implied by screenshot + Sour Diesel findings
    manual_merges = [
        ("GSC", "Girl Scout Cookies"),
        ("Star Killer", "Starkiller"),
        ("Platinum Girl Scout Cookies", "Platinum Cookies"),
        ("Chem Dog", "Chemdog"),
        ("Chemdawg", "Chemdog"),
        ("Gorilla Glue #4", "GG4"),
        ("Gorilla Glue 4", "GG4"),
        # Sour Diesel Fixes
        ("(Northern light", "Northern Lights"),
        ("Hawaiian)", "Hawaiian"),
        ("diesel", "Diesel"), 
        ("Unknown Strain", "Unknown"),
        ("Unknown Ruderalis", "Ruderalis")
    ]
    
    print("--- SYNONYM RESOLUTION STARTED ---")
    
    # 2. Execute Merges
    count = 0
    renamed_count = 0
    
    for slave_name, master_name in manual_merges:
        print(f"\nProcessing pair: '{slave_name}' -> '{master_name}'")
        
        # Fetch Master
        m_res = client.scroll(
            collection_name=collection,
            scroll_filter=models.Filter(must=[models.FieldCondition(key="name", match=models.MatchValue(value=master_name))]),
            limit=1,
            with_payload=True
        )[0]
        
        # Fetch Slave
        s_res = client.scroll(
            collection_name=collection,
            scroll_filter=models.Filter(must=[models.FieldCondition(key="name", match=models.MatchValue(value=slave_name))]),
            limit=1,
            with_payload=True
        )[0]
        
        if not s_res:
            print(f"  Slave '{slave_name}' not found. Skipping.")
            continue

        slave = s_res[0]
        
        # CASE 1: Rename (Slave exists, Master does not)
        if not m_res:
            print(f"  Master '{master_name}' not found. RENAMING '{slave_name}' -> '{master_name}'")
            new_payload = slave.payload
            new_payload["name"] = master_name
            
            client.set_payload(
                collection_name=collection,
                payload=new_payload,
                points=[slave.id]
            )
            renamed_count += 1
            print(f"    Renamed successfully.")
            continue
            
        # CASE 2: Merge (Both exist)
        master = m_res[0]
        
        if master.id == slave.id:
            print("  Same entity. Skipping.")
            continue
            
        print(f"  Merging {slave.payload.get('name')} ({slave.id}) -> {master.payload.get('name')} ({master.id})")
        
        # A. Rewire Incoming Relations (Anyone pointing to Slave -> Point to Master)
        incoming, _ = client.scroll(
            collection_name=collection,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="relations.target_id", match=models.MatchValue(value=slave.id))]
            ),
            limit=100,
            with_payload=True
        )
        
        for inc in incoming:
            rels = inc.payload.get("relations", [])
            updated = False
            for r in rels:
                if r.get("target_id") == slave.id:
                    r["target_id"] = master.id
                    r["target_label"] = master_name
                    updated = True
            
            if updated:
                client.set_payload(
                    collection_name=collection,
                    payload={"relations": rels},
                    points=[inc.id]
                )
                print(f"    Rewired incoming link from '{inc.payload.get('name')}'")
                
        # B. Move Outgoing Relations (Slave -> X) to Master
        # (Only if Master doesn't already have them)
        master_rels = master.payload.get("relations", [])
        slave_rels = slave.payload.get("relations", [])
        
        ids_in_master = set(r.get("target_id") for r in master_rels)
        
        for r in slave_rels:
            if r.get("target_id") not in ids_in_master:
                master_rels.append(r)
                print(f"    Moved relation {r.get('type')}->{r.get('target_label')}")
                
        # Update Master
        client.set_payload(
            collection_name=collection,
            payload={"relations": master_rels},
            points=[master.id]
        )
        
        # C. Delete Slave
        client.delete(collection_name=collection, points_selector=models.PointIdsList(points=[slave.id]))
        print(f"    Deleted '{slave_name}'")
        count += 1
 
    print(f"\nResolution Complete. Merged {count} pairs. Renamed {renamed_count} items.")
 
if __name__ == "__main__":
    asyncio.run(main())
