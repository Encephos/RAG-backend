
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scripts.ingest_strain_lineage import StrainIngester

@pytest.fixture
def ingester():
    with patch('src.scripts.ingest_strain_lineage.QdrantClient'), \
         patch('src.scripts.ingest_strain_lineage.SentenceTransformer'):
        return StrainIngester()

def test_normalize_name(ingester):
    assert ingester.normalize_name("  White Widow  ") == "white widow"
    assert ingester.normalize_name(None) is None

def test_generate_uuid(ingester):
    u1 = ingester.generate_uuid("white widow")
    u2 = ingester.generate_uuid("white widow")
    assert u1 == u2

def test_merge_strain_data(ingester):
    ingester._merge_strain_data("test strain", {
        "source_files": ["file1.csv"],
        "parents": ["parent1"],
        "description": "Short desc",
        "breeders": set(["Breeder A"]),
        "type": "Indica",
        "effects": [],
        "html_tree": None
    })
    
    data = ingester.strains["test strain"]
    assert data["name"] == "test strain"
    assert data["breeders"] == {"Breeder A"}
    
    ingester._merge_strain_data("test strain", {
        "source_files": ["file2.csv"],
        "parents": [],
        "description": "Longer desc",
        "breeders": set(["Breeder B"]),
        "type": "",
        "effects": [],
        "html_tree": "<div>Tree</div>"
    })
    
    updated = ingester.strains["test strain"]
    assert updated["breeders"] == {"Breeder A", "Breeder B"}
    assert updated["html_tree"] == "<div>Tree</div>"

def test_parse_lineage_tree_simple(ingester):
    # Mock BeautifulSoup since we want to test the parsing logic
    # Assuming bs4 is installed in test env (it was in requirements)
    
    html = """
    <li><a href="link">Current Strain</a>
        <ul>
            <li><a href="link">Parent A</a></li>
            <li><a href="link">Parent B</a></li>
        </ul>
    </li>
    """
    
    # We mock or ensure bs4 is available. 
    # If not, the method returns {}, set().
    # Let's assume it works or skip if ImportError.
    try:
        import bs4
    except ImportError:
        pytest.skip("bs4 not installed")

    relations, found = ingester.parse_lineage_tree(html, "current strain")
    
    assert "current strain" in relations
    assert "parent a" in relations["current strain"]
    assert "parent b" in relations["current strain"]
    assert "parent a" in found
    assert "parent b" in found

def test_parse_lineage_tree_formula(ingester):
    # Test with the »»» formula structure commonly seen in Seedfinder
    html = """
    <li><a href="link">Current Strain</a>
        <ul>
            <li>
                 »»» <a href="link">Parent One</a> x <a href="link">Parent Two</a>
            </li>
        </ul>
    </li>
    """
    try:
        import bs4
    except ImportError:
        pytest.skip("bs4 not installed")

    relations, found = ingester.parse_lineage_tree(html, "current strain")
    
    assert "current strain" in relations
    parents = relations["current strain"]
    assert "parent one" in parents
    assert "parent one" in parents
    assert "parent two" in parents

def test_parse_intermediate_nodes(ingester):
    # Test case: "Link A x Link B" should be a single intermediate node
    html = """
    <li>Root
        <ul>
            <li>
                <a href="a">Starkiller</a> x <a href="b">Hash Plant</a>
                <ul>
                    <li><a href="c">Starkiller</a></li>
                    <li><a href="d">Hash Plant</a></li>
                </ul>
            </li>
        </ul>
    </li>
    """
    try:
        import bs4
    except ImportError:
        pytest.skip("bs4 not installed")

    relations, found = ingester.parse_lineage_tree(html, "root")
    
    # 1. Root should have 1 parent: "starkiller x hash plant"
    assert "root" in relations
    root_parents = relations["root"]
    assert len(root_parents) == 1
    intermediate = "starkiller x hash plant"
    assert intermediate in root_parents
    
    # 2. Intermediate should exist and have parents
    assert intermediate in relations
    inter_parents = relations[intermediate]
    assert "starkiller" in inter_parents
    assert "hash plant" in inter_parents
