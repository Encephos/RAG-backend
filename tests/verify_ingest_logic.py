
import sys
import os
import uuid
from unittest.mock import MagicMock
import multiprocessing

# Allow import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock dependencies before import
mock_qdrant = MagicMock()
sys.modules['qdrant_client'] = mock_qdrant
sys.modules['qdrant_client.http'] = MagicMock()
sys.modules['qdrant_client.http.models'] = MagicMock()

sys.modules['sentence_transformers'] = MagicMock()

# IMPORTANT: Fix for multiprocessing in tests/scripts when checking logic
# We need to ensure we can import the script without it running immediately
if __name__ == "__main__":
    multiprocessing.freeze_support()

from src.scripts.ingest_strain_lineage import StrainIngester

def verify_logic():
    ingester = StrainIngester()
    
    # 1. Setup Data with:
    # - Known Parents
    # - Missing Parents
    # - Self-Loop
    # - Cycle (A -> B -> A)
    
    print("Setting up test data...")
    ingester.strains["strain_a"] = {
        "name": "strain_a", "uuid": ingester.generate_uuid("strain_a"),
        "parents": ["strain_b"], "breeders": set(), "description": "", 
        "type": "", "effects": [], "sources": [], "html_tree": None
    }
    
    ingester.strains["strain_b"] = {
        "name": "strain_b", "uuid": ingester.generate_uuid("strain_b"),
        "parents": ["strain_a", "missing_parent"], "breeders": set(), "description": "", 
        "type": "", "effects": [], "sources": [], "html_tree": None
    }
    
    ingester.strains["self_looper"] = {
        "name": "self_looper", "uuid": ingester.generate_uuid("self_looper"),
        "parents": ["self_looper", "strain_a"], "breeders": set(), "description": "", 
        "type": "", "effects": [], "sources": [], "html_tree": None
    }

    print("Running resolve_references...")
    ingester.resolve_references()
    
    # 2. Verify Missing Node Creation
    if "missing_parent" in ingester.strains:
        print("[SUCCESS] Missing parent node created.")
        node = ingester.strains["missing_parent"]
        if "Unknown" in node["breeders"]:
            print("[SUCCESS] Missing node has 'Unknown' breeder.")
    else:
        print("[FAIL] Missing parent node NOT created.")

    # 3. Verify Self-Loop Prevention
    looper = ingester.strains.get("self_looper")
    parents = [p["name"] for p in looper.get("resolved_parents", [])]
    if "self_looper" not in parents:
        print("[SUCCESS] Self-loop removed.")
    else:
        print("[FAIL] Self-loop persists.")
        
    if "strain_a" in parents:
        print("[SUCCESS] Valid parent retained.")

    # 4. Verify Cycle Handling (A <-> B)
    # The script allows cycles (biological reality or data quality), but should handle them gracefully.
    # We just check if they are linked.
    a = ingester.strains["strain_a"]
    b = ingester.strains["strain_b"]
    
    a_parents = [p["name"] for p in a["resolved_parents"]]
    b_parents = [p["name"] for p in b["resolved_parents"]]
    
    if "strain_b" in a_parents and "strain_a" in b_parents:
        print("[SUCCESS] Cycle preserved (A->B, B->A).")
    else:
        print("[FAIL] Links broken.")

if __name__ == "__main__":
    verify_logic()
