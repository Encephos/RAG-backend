import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Mock dependencies before import
# Need to mock submodules explicitly because "from X.Y import Z" requires X.Y to exist
qdrant_mock = MagicMock()
http_mock = MagicMock()
models_mock = MagicMock()
http_mock.models = models_mock
qdrant_mock.http = http_mock

sys.modules['qdrant_client'] = qdrant_mock
sys.modules['qdrant_client.http'] = http_mock
sys.modules['qdrant_client.http.models'] = models_mock
sys.modules['sentence_transformers'] = MagicMock()

from src.scripts.ingest_strain_lineage import StrainIngester

# Complex HTML sample
html_real = """
<li class="strain-entry">
    <a href="...">Z and Z Auto</a>
    <ul>
        <li>»»» <a href="...">Z3</a> x <a href="...">Monster Mash</a></li>
        <li>
            <a href="...">Z3</a>
            <ul>
                 <li>»»» <a href="...">The Original Z</a> x <a href="...">Hindu Kush</a></li>
                 <li>
                     <a href="...">The Original Z</a>
                     <ul>
                         <li>»»» (Grape Ape x Grapefruit) x <a href="...">Unknown Strain</a></li>
                         <li>
                             (Grape Ape x Grapefruit)
                             <ul>
                                 <li>»»» <a href="...">Grape Ape</a> x <a href="...">Grapefruit</a></li>
                             </ul>
                         </li>
                     </ul>
                 </li>
            </ul>
        </li>
        <li>
            <a href="...">Monster Mash</a>
            <ul>
               <li>»»» ...</li>
            </ul>
        </li>
    </ul>
</li>
"""

def test_extraction():
    ingester = StrainIngester()
    
    print("--- Testing parse_lineage_tree_static with Real HTML ---")
    rels, found_strains = ingester.parse_lineage_tree_static(html_real, "Z and Z Auto")
    
    print(f"Found Strains: {found_strains}")
    print("\nRelations:")
    for child, parents in rels.items():
        print(f"{child} -> {parents}")

    # Manual Assertions for "Z and Z Auto"
    # Expected: Z and Z Auto -> [Z3, Monster Mash]
    #           Z3 -> [The Original Z, Hindu Kush]
    #           The Original Z -> [(Grape Ape x Grapefruit), Unknown Strain]
    #           (Grape Ape x Grapefruit) -> [Grape Ape, Grapefruit]
    
    # Check Z and Z Auto
    z_auto_parents = rels.get('z and z auto', [])
    if 'z3' in z_auto_parents and 'monster mash' in z_auto_parents:
        print("[PASS] Z and Z Auto parents found.")
    else:
        print(f"[FAIL] Z and Z Auto parents mismatch: {z_auto_parents}")

    # Check Z3
    z3_parents = rels.get('z3', [])
    if 'the original z' in z3_parents and 'hindu kush' in z3_parents:
        print("[PASS] Z3 parents found.")
    else:
        print(f"[FAIL] Z3 parents mismatch: {z3_parents}")
        
    # Check The Original Z (Testing the fallback/leaf logic or formula)
    oz_parents = rels.get('the original z', [])
    # Norm logic strips brackets? "(Grape Ape x Grapefruit)" -> "Grape Ape x Grapefruit"
    # Actually my normalization removes [] but not ().
    # Let's see what happens.
    print(f"The Original Z parents: {oz_parents}")
    
    # Check the intermediate node
    # Name likely "(Grape Ape x Grapefruit)" or normalized "grape ape x grapefruit"
    # Search for keys containing "grape ape"
    found_inter = [k for k in rels.keys() if "grape ape" in k and "grapefruit" in k]
    print(f"Intermediate Nodes found: {found_inter}")
    
    if found_inter:
        for k in found_inter:
            print(f"{k} -> {rels[k]}")

if __name__ == "__main__":
    test_extraction()
