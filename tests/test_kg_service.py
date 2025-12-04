import pytest
from src.services.kg_service import KnowledgeGraphService

class TestKnowledgeGraphService:
    
    def test_add_entity(self):
        """Test adding an entity to the graph."""
        kg = KnowledgeGraphService()
        kg.add_entity("Apple")
        
        assert "Apple" in kg.graph
        assert kg.graph["Apple"] == {}

    def test_add_relation(self):
        """Test adding a relation between entities."""
        kg = KnowledgeGraphService()
        kg.add_relation("Apple", "Cupertino", "headquartered_in", 0.95)
        
        assert "Apple" in kg.graph
        assert "Cupertino" in kg.graph["Apple"]
        assert kg.graph["Apple"]["Cupertino"]["relation"] == "headquartered_in"
        assert kg.graph["Apple"]["Cupertino"]["confidence"] == 0.95

    def test_add_triple(self):
        """Test adding a semantic triple."""
        kg = KnowledgeGraphService()
        kg.add_triple("Steve Jobs", "founded", "Apple", 0.99)
        
        assert "Steve Jobs" in kg.graph
        assert "Apple" in kg.graph["Steve Jobs"]
        assert kg.graph["Steve Jobs"]["Apple"]["relation"] == "founded"

    def test_get_neighbors(self):
        """Test getting neighbors of an entity."""
        kg = KnowledgeGraphService()
        kg.add_triple("Apple", "founded_by", "Steve Jobs", 0.95)
        kg.add_triple("Apple", "headquartered_in", "Cupertino", 0.9)
        
        neighbors = kg.get_neighbors("Apple")
        
        assert "Steve Jobs" in neighbors
        assert "Cupertino" in neighbors
        assert neighbors["Steve Jobs"]["relation"] == "founded_by"

    def test_get_subgraph(self):
        """Test getting a subgraph from starting entities."""
        kg = KnowledgeGraphService()
        kg.add_triple("Apple", "founded_by", "Steve Jobs", 0.95)
        kg.add_triple("Steve Jobs", "born_in", "San Francisco", 0.9)
        kg.add_triple("Apple", "headquartered_in", "Cupertino", 0.9)
        
        subgraph = kg.get_subgraph(["Apple"], depth=1)
        
        assert "Apple" in subgraph
        assert "Steve Jobs" in subgraph["Apple"]
        assert "Cupertino" in subgraph["Apple"]

    def test_get_subgraph_depth_2(self):
        """Test getting a subgraph with depth 2."""
        kg = KnowledgeGraphService()
        kg.add_triple("Apple", "founded_by", "Steve Jobs", 0.95)
        kg.add_triple("Steve Jobs", "born_in", "San Francisco", 0.9)
        
        subgraph = kg.get_subgraph(["Apple"], depth=2)
        
        assert "Apple" in subgraph
        assert "Steve Jobs" in subgraph

    def test_get_graph_context_string(self):
        """Test getting a human-readable graph context string."""
        kg = KnowledgeGraphService()
        kg.add_triple("Apple", "founded_by", "Steve Jobs", 0.95)
        
        context = kg.get_graph_context_string(["Apple"], depth=1)
        
        assert "Apple" in context
        assert "founded_by" in context
        assert "Steve Jobs" in context

    def test_clear(self):
        """Test clearing the graph."""
        kg = KnowledgeGraphService()
        kg.add_triple("Apple", "founded_by", "Steve Jobs", 0.95)
        kg.clear()
        
        assert kg.graph == {}
