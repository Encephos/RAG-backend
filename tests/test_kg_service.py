import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from src.services.kg_service import KnowledgeGraphService

class TestKnowledgeGraphService:
    
    @patch("src.services.kg_service.QdrantService")
    @patch("src.services.kg_service.EmbeddingService")
    async def test_add_entity_with_resolution_new(self, mock_emb, mock_qdrant):
        """Test adding a new entity."""
        service = KnowledgeGraphService()
        
        # Mock Embedding
        mock_emb_instance = mock_emb.return_value
        mock_emb_instance.embed_query = AsyncMock(return_value=[0.1] * 384)
        service.embedder = mock_emb_instance
        
        # Mock Qdrant Search (No match)
        mock_qdrant_instance = mock_qdrant.return_value
        mock_qdrant_instance.search_entities.return_value = []
        service.qdrant = mock_qdrant_instance
        
        entity_id = await service.add_entity_with_resolution("Apple", "Org", "Tech Co")
        
        assert entity_id is not None
        service.qdrant.upsert_entity.assert_called_once()

    @patch("src.services.kg_service.QdrantService")
    @patch("src.services.kg_service.EmbeddingService")
    async def test_add_entity_with_resolution_existing(self, mock_emb, mock_qdrant):
        """Test resolving to an existing entity."""
        service = KnowledgeGraphService()
        
        # Mock Embedding
        mock_emb_instance = mock_emb.return_value
        mock_emb_instance.embed_query = AsyncMock(return_value=[0.1] * 384)
        service.embedder = mock_emb_instance
        
        # Mock Qdrant Search (Match found)
        mock_hit = MagicMock()
        mock_hit.id = "existing_id"
        mock_hit.metadata = {"id": "existing_id"}
        mock_qdrant_instance = mock_qdrant.return_value
        mock_qdrant_instance.search_entities.return_value = [mock_hit]
        service.qdrant = mock_qdrant_instance
        
        entity_id = await service.add_entity_with_resolution("Apple Inc", "Org", "Tech Co")
        
        assert entity_id == "existing_id"
        service.qdrant.upsert_entity.assert_not_called()

    @patch("src.services.kg_service.QdrantService")
    def test_add_relation(self, mock_qdrant):
        """Test adding a relation."""
        service = KnowledgeGraphService()
        mock_qdrant_instance = mock_qdrant.return_value
        service.qdrant = mock_qdrant_instance
        
        # Mock Source Entity
        mock_qdrant_instance.get_entity.return_value = {
            "id": "source",
            "relations": []
        }
        
        service.add_relation("source", "target", "rel_type")
        
        service.qdrant.update_entity_payload.assert_called_once()
        args = service.qdrant.update_entity_payload.call_args
        assert args[0][0] == "source"
        assert args[0][1]["relations"][0] == {"target_id": "target", "type": "rel_type"}

    @patch("src.services.kg_service.QdrantService")
    @patch("src.services.kg_service.EmbeddingService")
    async def test_get_graph_context(self, mock_emb, mock_qdrant):
        """Test retrieving graph context."""
        service = KnowledgeGraphService()
        
        # Mock Embedding
        mock_emb_instance = mock_emb.return_value
        mock_emb_instance.embed_query = AsyncMock(return_value=[0.1] * 384)
        service.embedder = mock_emb_instance
        
        # Mock Entry Points
        mock_hit = MagicMock()
        mock_hit.metadata = {
            "id": "e1",
            "name": "Entity1",
            "type": "Type",
            "description": "Desc",
            "relations": [{"target_id": "e2", "type": "rel"}]
        }
        mock_qdrant_instance = mock_qdrant.return_value
        mock_qdrant_instance.search_entities.return_value = [mock_hit]
        
        # Mock Target Entity
        mock_qdrant_instance.get_entity.return_value = {"name": "Entity2"}
        service.qdrant = mock_qdrant_instance
        
        context = await service.get_graph_context("query")
        
        assert "Entity: Entity1" in context
        assert "- rel -> Entity2" in context
