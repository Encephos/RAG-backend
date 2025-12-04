from fastapi.testclient import TestClient
from src.main import app
from unittest.mock import MagicMock, patch

client = TestClient(app)

# Mock Qdrant and Embedding services to avoid external calls during tests
@patch("src.services.rag_service.QdrantService")
@patch("src.services.rag_service.EmbeddingService")
def test_ingest_document(mock_embedding, mock_qdrant):
    # Setup mocks
    mock_embedding_instance = mock_embedding.return_value
    mock_embedding_instance.embed_query.return_value = [0.1] * 384
    
    mock_qdrant_instance = mock_qdrant.return_value
    
    response = client.post(
        "/api/v1/ingest",
        json={"text": "Qdrant is a vector database. It is fast.", "metadata": {"source": "test"}}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Verify interactions
    mock_embedding_instance.embed_query.assert_called()
    mock_qdrant_instance.upsert.assert_called()

@patch("src.services.rag_service.QdrantService")
@patch("src.services.rag_service.EmbeddingService")
def test_query_rag(mock_embedding, mock_qdrant):
    # Setup mocks
    mock_embedding_instance = mock_embedding.return_value
    mock_embedding_instance.embed_query.return_value = [0.1] * 384
    
    mock_qdrant_instance = mock_qdrant.return_value
    mock_qdrant_instance.search.return_value = [
        {"text": "Qdrant is fast.", "score": 0.9, "metadata": {}}
    ]
    
    response = client.post(
        "/api/v1/query",
        json={"query": "What is Qdrant?", "limit": 3}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "context" in data
    assert len(data["context"]) == 1
    assert data["context"][0]["text"] == "Qdrant is fast."
