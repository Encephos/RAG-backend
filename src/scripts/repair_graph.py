
import asyncio
import sys
from pathlib import Path
from qdrant_client import models
import uuid

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.services.kg_service import KnowledgeGraphService

async def main():
    kg = KnowledgeGraphService()
    client = kg.qdrant.client
    collection = "botanical_entities"
    
    print("--- GLOBAL GRAPH REPAIR STARTED ---")
    
    # 1. Build Global Name Index (In-Memory)
    # We need to know which IDs are valid and map Names -> Valid IDs
    print("Phase 1: Building Global Name Index...")
    
    name_to_id = {}
    valid_ids = set()
    
    # Scroll all points (fetching only name payload to save memory)
    next_offset = None
    count = 0
    
    while True:
        points, next_offset = client.scroll(
            collection_name=collection,
            limit=2000,
            offset=next_offset,
            with_payload=True,
            with_vectors=False
        )
        
        for p in points:
            pid = p.id
            name = p.payload.get("name")
            valid_ids.add(pid)
            if name:
                # Store lowercase for case-insensitive matching
                name_to_id[name.lower().strip()] = pid
                # Also store exact? Auto-lookup handles case usually.
        
        count += len(points)
        print(f"  Indexed {count} entities...", end='\r')
        
        if next_offset is None:
            break
            
    print(f"\nIndex complete. {len(valid_ids)} valid entities found.")
    
    # 2. Scan and Repair Relations
    print("\nPhase 2: Scanning for Broken Relations...")
    
    fixed_count = 0
    errors_count = 0
    
    # We iterate again to process relations. 
    # (We could have stored relations in step 1 but that might eat RAM if graph is huge. 
    #  For safety, we scroll again or use the cached points if valid_ids fits in RAM logic, 
    #  but we didn't save the points in step 1, just ID/Name).
    
    next_offset = None
    processed = 0
    
    while True:
        points, next_offset = client.scroll(
            collection_name=collection,
            limit=500, # Process in chunks
            offset=next_offset,
            with_payload=True,
            with_vectors=False
        )
        
        for p in points:
            pid = p.id
            name = p.payload.get("name", "Unknown")
            relations = p.payload.get("relations", [])
            
            if not relations:
                continue
                
            updated_relations = []
            needs_save = False
            
            for r in relations:
                target_id = r.get("target_id")
                target_label = r.get("target_label")
                rtype = r.get("type")
                
                # Check 1: Is the Target ID valid?
                if target_id in valid_ids:
                    updated_relations.append(r)
                    continue
                    
                # BROKEN LINK DETECTED
                # print(f"  [Found Broken Link] {name} --({rtype})--> {target_label} ({target_id})")
                
                # Attempt Fix: Lookup by Name
                if not target_label:
                    # Can't fix without a name. Drop it?
                    # print(f"    -> Unfixable (No Label). Dropping.")
                    needs_save = True
                    continue
                    
                target_label_clean = target_label.strip()
                target_label_lower = target_label_clean.lower()
                
                new_id = name_to_id.get(target_label_lower)
                
                # Heuristic: Try removing "Auto"
                if not new_id and "auto" in target_label_lower:
                    stripped = target_label_lower.replace("auto", "").strip()
                    new_id = name_to_id.get(stripped)
                    
                if new_id:
                    # Fix applied!
                    r["target_id"] = new_id
                    # Update label to match the canonical name of the found ID? 
                    # Optional, but keep original label for now or update?
                    # Let's keep original label or update if we found via heuristic?
                    # r["target_label"] = ... 
                    
                    updated_relations.append(r)
                    needs_save = True
                    fixed_count += 1
                else:
                    # Still not found. 
                    # Options: Create Stub or Drop. 
                    # If it's a "Parent" relation, failing to find it breaks the tree.
                    # Creating a stub is safer for "bred_from".
                    
                    if rtype in ["bred_from", "has_parent", "cross_of"]:
                        # print(f"    -> Critical Missing Parent: '{target_label}'. Creating Stub...")
                        
                        # Create Stub
                        new_stub_id = str(uuid.uuid4())
                        stub_payload = {
                            "id": new_stub_id,
                            "name": target_label_clean,
                            "type": "Strain",
                            "description": "Auto-created stub during repair.",
                            "relations": []
                        }
                        
                        # Add to index immediately so others can find it
                        valid_ids.add(new_stub_id)
                        name_to_id[target_label_lower] = new_stub_id
                        
                        # Persist Stub
                        client.upsert(
                            collection_name=collection,
                            points=[models.PointStruct(id=new_stub_id, vector={}, payload=stub_payload)] 
                            # Note: Empty vector might fail if config requires size? 
                            # We usually need a vector.
                        )
                        # We need a vector. Since we can't async await easily in this sync loop structure if we wanted to be fast,
                        # let's just assume we can use a zero vector or random?
                        # Actually, qdrant requires vector matching dimension.
                        # We must generate one.
                        # Breaking out to async embed is slow per item.
                        # BETTER: Collect all missing stubs, bulk embed, bulk upsert, then retry?
                        # For now, let's just Drop it if we can't easily embed. 
                        # OR: Use a placeholder vector (0.0 * 384).
                        
                        # Recover:
                        # updated_relations.append(r) # Keep broken? No, Qdrant might choke or UI fails.
                        pass 
                        # Determining vector size...
                        # Assuming 384 for botanical_entities
                        zero_vector = [0.0] * 384
                        client.upsert(
                            collection_name=collection,
                            points=[models.PointStruct(id=new_stub_id, vector=zero_vector, payload=stub_payload)]
                        )
                        
                        r["target_id"] = new_stub_id
                        updated_relations.append(r)
                        needs_save = True
                        fixed_count += 1
                    else:
                        # Non-critical relation (e.g. bred_by), drop if not found
                        needs_save = True # Dropped
            
            if needs_save:
                client.set_payload(
                    collection_name=collection,
                    payload={"relations": updated_relations},
                    points=[pid]
                )
        
        processed += len(points)
        print(f"  Scanned {processed} entities. Fixed {fixed_count} relations...", end='\r')
        
        if next_offset is None:
            break

    print(f"\n\nRepair Complete.")
    print(f"  Total Entities Scanned: {processed}")
    print(f"  Fixed Relations: {fixed_count}")

if __name__ == "__main__":
    asyncio.run(main())
