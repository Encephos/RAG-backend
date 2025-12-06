import pytest
from unittest.mock import MagicMock, patch
from src.services.embedding_service import EmbeddingService
import numpy as np

class TestEmbeddingService:
    
    @patch("src.services.embedding_service.TextEmbedding")
    async def test_embed_texts(self, mock_model_class):
        """Test embedding a list of texts."""
        mock_model = mock_model_class.return_value
        # Mock generator return
        mock_model.embed.return_value = (np.array([0.1, 0.2]) for _ in range(2))
        
        service = EmbeddingService()
        embeddings = await service.embed(["text1", "text2"])
        
        assert len(embeddings) == 2
        assert isinstance(embeddings[0], list) # Should be converted to list
        assert embeddings[0] == [0.1, 0.2]
        
    @patch("src.services.embedding_service.TextEmbedding")
    async def test_embed_query(self, mock_model_class):
        """Test embedding a single query."""
        mock_model = mock_model_class.return_value
        mock_model.embed.return_value = (np.array([0.1, 0.2]) for _ in range(1))
        
        service = EmbeddingService()
        embedding = await service.embed_query("query")
        
        assert isinstance(embedding, list)
        assert embedding == [0.1, 0.2]
