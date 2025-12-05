import pytest
from unittest.mock import MagicMock, patch
from src.services.qdrant_service import QdrantService
from src.core.config import settings
from qdrant_client.http import models

class TestQdrantService:
    
    @patch("src.services.qdrant_service.QdrantClient")
    def test_init_creates_collections(self, mock_client_class):
        """Test that collections are created on initialization if they don't exist."""
        mock_client = mock_client_class.return_value
        # Mock get_collections to return empty list initially
        mock_client.get_collections.return_value.collections = []
        
        service = QdrantService()
        
        # Should call create_collection 10 times (5 data + 5 entity collections)
        assert mock_client.create_collection.call_count == 10
        
    @patch("src.services.qdrant_service.QdrantClient")
    def test_upsert_document(self, mock_client_class):
        """Test upserting a document chunk."""
        mock_client = mock_client_class.return_value
        service = QdrantService()
        
        service.upsert(
            text="Test text",
            vector=[0.1] * 384,
            metadata={"source": "test"}
        )
        
        mock_client.upsert.assert_called_once()
        call_args = mock_client.upsert.call_args
        # Should default to master collection name
        assert call_args.kwargs["collection_name"] == service.collections["master"]
        assert len(call_args.kwargs["points"]) == 1
        
    @patch("src.services.qdrant_service.QdrantClient")
    def test_search_documents(self, mock_client_class):
        """Test searching for documents."""
        mock_client = mock_client_class.return_value
        # Mock search result
        mock_hit = MagicMock()
        mock_hit.payload = {"text": "Result", "meta": "data"}
        mock_hit.score = 0.9
        
        mock_result = MagicMock()
        mock_result.points = [mock_hit]
        mock_client.query_points.return_value = mock_result
        
        service = QdrantService()
        results = service.search(vector=[0.1] * 384, limit=5)
        
        assert len(results) == 1
        assert results[0]["text"] == "Result"
        assert results[0]["score"] == 0.9
        
    @patch("src.services.qdrant_service.QdrantClient")
    def test_upsert_entity(self, mock_client_class):
        """Test upserting a graph entity."""
        mock_client = mock_client_class.return_value
        service = QdrantService()
        
        service.upsert_entity(
            entity_id="123",
            vector=[0.1] * 384,
            payload={"name": "Test Entity"}
        )
        
        mock_client.upsert.assert_called()
        call_args = mock_client.upsert.call_args
        # Should default to master entity collection name
        assert call_args.kwargs["collection_name"] == settings.QDRANT_ENTITY_COLLECTION_NAME
        
    @patch("src.services.qdrant_service.QdrantClient")
    def test_search_entities(self, mock_client_class):
        """Test searching for entities."""
        mock_client = mock_client_class.return_value
        service = QdrantService()
        
        service.search_entities(vector=[0.1] * 384, limit=1)
        
        mock_client.query_points.assert_called()
        call_args = mock_client.query_points.call_args
        assert call_args.kwargs["collection_name"] == settings.QDRANT_ENTITY_COLLECTION_NAME
