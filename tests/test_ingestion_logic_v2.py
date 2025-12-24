
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import sys
import os

# Adjust path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scripts.ingest_strain_lineage import StrainIngester, normalize_name

class TestIngestionLogicV2(unittest.TestCase):
    def setUp(self):
        # Mock Qdrant and Model to avoid heavy lifting
        with patch('src.scripts.ingest_strain_lineage.QdrantClient'), \
             patch('src.scripts.ingest_strain_lineage.SentenceTransformer'):
            self.ingester = StrainIngester()

    def test_primary_lock(self):
        """Test that Primary Source locks basic data."""
        # Simulate Primary Load
        name = "Blue Dream"
        norm = normalize_name(name)
        
        self.ingester.strains[norm] = self.ingester._init_strain_entry(name, norm, "primary")
        entry = self.ingester.strains[norm]
        entry["description"] = "Original Seedfinder Desc"
        entry["primary_source_loaded"] = True
        
        # Simulate Secondary Load (e.g. Leafly)
        secondary_row = pd.Series({
            "name": "Blue Dream", 
            "description": "Leafly Description", # Should be IGNORED
            "thc_level": 18.5,
            "most_common_terpene": "Myrcene"
        })
        
        self.ingester._enrich_entry(entry, secondary_row, "leafly")
        
        # Assertions
        self.assertEqual(entry["description"], "Original Seedfinder Desc", "Primary Description should be locked")
        self.assertIn(18.5, entry["thc"], "Secondary THC should be added")
        self.assertIn("Myrcene", entry["terpenes"], "Secondary Terpenes should be added")

    def test_enrichment_accumulation(self):
        """Test that multiple secondary sources accumulate data."""
        name = "OG Kush"
        norm = normalize_name(name)
        self.ingester.strains[norm] = self.ingester._init_strain_entry(name, norm, "primary")
        entry = self.ingester.strains[norm]
        
        # 1. Cannabis.csv (Effects)
        row1 = pd.Series({"Strain": "OG Kush", "Effects": "Happy, Hungry"})
        self.ingester._enrich_entry(entry, row1, "cannabis")
        
        # 2. OCPDB (THC)
        row2 = pd.Series({"Strain": "OG Kush", "TotalTHC": 24.5, "TotalCBD": 0.1})
        self.ingester._enrich_entry(entry, row2, "ocpdb")
        
        # 3. Results (More THC)
        row3 = pd.Series({"Sample Name": "OG Kush", "delta-9 THC": 22.0})
        self.ingester._enrich_entry(entry, row3, "results")
        
        self.assertIn("Happy", entry["effects"])
        self.assertIn("Hungry", entry["effects"])
        self.assertEqual(len(entry["thc"]), 2, "Should accumulate 2 THC tests")
        self.assertIn(24.5, entry["thc"])
        self.assertIn(22.0, entry["thc"])

    def test_new_from_secondary(self):
        """Test creation of new strain from secondary source."""
        name = "Rare Leafly Only"
        norm = normalize_name(name)
        
        # Init from secondary
        self.ingester.strains[norm] = self.ingester._init_strain_entry(name, norm, "secondary")
        entry = self.ingester.strains[norm]
        
        row = pd.Series({"name": name, "thc_level": 15.0})
        self.ingester._enrich_entry(entry, row, "leafly")
        
        self.assertFalse(entry["primary_source_loaded"])
        self.assertIn(15.0, entry["thc"])

if __name__ == '__main__':
    unittest.main()
