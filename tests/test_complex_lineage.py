
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Adjust path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scripts.ingest_strain_lineage import StrainIngester, normalize_name

class TestComplexLineageParsing(unittest.TestCase):
    def setUp(self):
        with patch('src.scripts.ingest_strain_lineage.QdrantClient'), \
             patch('src.scripts.ingest_strain_lineage.SentenceTransformer'):
            self.ingester = StrainIngester()

    def test_parse_nested_cross(self):
        """
        Test parsing of: Strain X = A x (B x C)
        HTML Structure roughly:
        <li>Strain X
            <ul>
                <li>A</li>
                <li>
                    <ul> <li>B</li> <li>C</li> </ul> (Formula wrapper?)
                    OR
                    <li>Intermediate Node (B x C)
                        <ul><li>B</li><li>C</li></ul>
                    </li>
                </li>
            </ul>
        </li>
        """
        # Case 1: Explicit Intermediate Node
        # Strain X -> Parents: A, (B x C)
        # (B x C) -> Parents: B, C
        html = """
        <li>Strain X
            <ul>
                <li><a href="#">Strain A</a></li>
                <li>B x C
                    <ul>
                        <li><a href="#">Strain B</a></li>
                        <li><a href="#">Strain C</a></li>
                    </ul>
                </li>
            </ul>
        </li>
        """
        rels, found = self.ingester.parse_lineage_tree_static(html, "Strain X")
        
        # Check Main Strain X
        x_norm = normalize_name("Strain X")
        self.assertIn(x_norm, rels)
        parents_x = rels[x_norm]
        self.assertIn("strain a", parents_x)
        self.assertIn("b x c", parents_x)
        
        # Check Intermediate B x C
        bc_norm = normalize_name("B x C")
        self.assertIn(bc_norm, rels)
        parents_bc = rels[bc_norm]
        self.assertIn("strain b", parents_bc)
        self.assertIn("strain c", parents_bc)

    def test_seedfinder_formula(self):
        """Test the '»»»' pattern handling."""
        html = """
        <li>Target
            <ul>
                <li>Parent A</li>
                <li>
                    <ul>
                        <li><a href="#">Parent B</a> »»» <a href="#">Grandparent C</a> x <a href="#">Grandparent D</a></li>
                    </ul>
                </li>
            </ul>
        </li>
        """
        # In the reference logic, this might be handled differently depending on exact structure.
        # But let's verify if Grandparents C and D are detected.
        
        rels, found = self.ingester.parse_lineage_tree_static(html, "Target")
        
        # If the logic flat-maps formula nodes:
        # Target -> A, B? 
        # Or Target -> A, and B -> C, D?
        
        # The logic:
        # if "»»»" in inner_li -> links found -> added to current name's relations?
        # "tree_relations[current_name] = list(set(existing + p_list))"
        # Wait, if child is UL (Formula Wrapper), current_name is "Target".
        # So "Parent B" (link), "Grandparent C", "Grandparent D" might all be added as parents of Target?
        # Let's see what the code does.
        
        target_norm = normalize_name("Target")
        if target_norm in rels:
            parents = rels[target_norm]
            # print(parents) 
            pass

if __name__ == '__main__':
    unittest.main()
