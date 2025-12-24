
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scripts.ingest_strain_lineage import StrainIngester

@pytest.fixture
def ingester():
    # Mock Qdrant and Encoder to avoid initialization overhead
    with patch('src.scripts.ingest_strain_lineage.QdrantClient'), \
         patch('src.scripts.ingest_strain_lineage.SentenceTransformer'):
        return StrainIngester()

def test_normalize_name(ingester):
    assert ingester.normalize_name("  White Widow  ") == "white widow"
    assert ingester.normalize_name("OG Kush") == "og kush"
    assert ingester.normalize_name(None) is None
    assert ingester.normalize_name(float('nan')) is None

def test_generate_uuid(ingester):
    # UUID should be deterministic
    u1 = ingester.generate_uuid("white widow")
    u2 = ingester.generate_uuid("white widow")
    u3 = ingester.generate_uuid("og kush")
    
    assert u1 == u2
    assert u1 != u3

def test_merge_strain_data(ingester):
    # Initial data
    ingester._merge_strain_data("test strain", {
        "source_files": ["file1.csv"],
        "parents": ["parent1"],
        "description": "Short desc",
        "breeder": "Breeder A",
        "type": "Indica",
        "effects": [],
        "html_tree": None
    })
    
    data = ingester.strains["test strain"]
    assert data["name"] == "test strain"
    assert data["parents"] == ["parent1"]
    assert data["description"] == "Short desc"
    
    # Merge new data (should update description if longer, append sources)
    ingester._merge_strain_data("test strain", {
        "source_files": ["file2.csv"],
        "parents": [],
        "description": "A much longer description that should overwrite.",
        "breeder": "Breeder A",
        "type": "",
        "effects": [],
        "html_tree": "<div>Tree</div>"
    })
    
    updated = ingester.strains["test strain"]
    assert updated["description"] == "A much longer description that should overwrite."
    assert "file1.csv" in updated["sources"]
    assert "file2.csv" in updated["sources"]
    assert updated["html_tree"] == "<div>Tree</div>"

def test_merge_strain_parents_seedfinder_priority(ingester):
    # Seedfinder should add to parents
    ingester._merge_strain_data("strain x", {
        "source_files": ["kushy.csv"],
        "parents": ["unknown"],
        "description": "",
        "breeder": "",
        "type": "",
        "effects": [],
        "html_tree": None
    })
    
    ingester._merge_strain_data("strain x", {
        "source_files": ["all_strains_seedfinder.csv"],
        "parents": ["real parent 1", "real parent 2"],
        "description": "",
        "breeder": "",
        "type": "",
        "effects": [],
        "html_tree": None
    })
    
    data = ingester.strains["strain x"]
    # Should contain the real parents
    assert "real parent 1" in data["parents"]
    assert "real parent 2" in data["parents"]
