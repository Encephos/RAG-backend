from fastapi.testclient import TestClient
from src.main import app
from unittest.mock import MagicMock, patch

client = TestClient(app)


@patch("src.services.rag_service.QdrantService")
@patch("src.services.rag_service.EmbeddingService")
@patch("src.services.rag_service.LLMService")
def test_ingest_document(mock_llm, mock_embedding, mock_qdrant):
    """Test ingesting a document with LLM entity extraction."""
    # Setup mocks
    mock_embedding_instance = mock_embedding.return_value
    mock_embedding_instance.embed_query.return_value = [0.1] * 384
    
    mock_qdrant_instance = mock_qdrant.return_value
    
    # Mock LLM entity extraction
    mock_llm_instance = mock_llm.return_value
    mock_triple = MagicMock()
    mock_triple.subject = "Apple"
    mock_triple.predicate = "founded_by"
    mock_triple.object = "Steve Jobs"
    mock_triple.confidence = 0.95
    mock_llm_instance.extract_entities.return_value = [mock_triple]
    
    response = client.post(
        "/api/v1/ingest",
        json={"text": "Apple was founded by Steve Jobs.", "metadata": {"source": "test"}}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Verify interactions
    mock_embedding_instance.embed_query.assert_called()
    mock_qdrant_instance.upsert.assert_called()
    mock_llm_instance.extract_entities.assert_called()


@patch("src.services.rag_service.QdrantService")
@patch("src.services.rag_service.EmbeddingService")
@patch("src.services.rag_service.LLMService")
def test_query_rag_with_llm_answer(mock_llm, mock_embedding, mock_qdrant):
    """Test querying RAG with LLM-generated answer."""
    # Setup mocks
    mock_embedding_instance = mock_embedding.return_value
    mock_embedding_instance.embed_query.return_value = [0.1] * 384
    
    mock_qdrant_instance = mock_qdrant.return_value
    mock_qdrant_instance.search.return_value = [
        {"text": "Apple is a technology company.", "score": 0.9, "metadata": {}}
    ]
    
    # Mock LLM answer generation
    mock_llm_instance = mock_llm.return_value
    mock_llm_instance.generate_answer.return_value = "Apple is a technology company headquartered in Cupertino."
    
    response = client.post(
        "/api/v1/query",
        json={"query": "What is Apple?", "limit": 3}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "Apple" in data["answer"]
    assert "context" in data
    assert len(data["context"]) == 1


@patch("src.services.rag_service.QdrantService")
@patch("src.services.rag_service.EmbeddingService")
@patch("src.services.rag_service.LLMService")
def test_query_with_graph_context(mock_llm, mock_embedding, mock_qdrant):
    """Test query includes graph context in response."""
    mock_embedding_instance = mock_embedding.return_value
    mock_embedding_instance.embed_query.return_value = [0.1] * 384
    
    mock_qdrant_instance = mock_qdrant.return_value
    mock_qdrant_instance.search.return_value = [
        {"text": "Apple was founded by Steve Jobs.", "score": 0.85, "metadata": {}}
    ]
    
    mock_llm_instance = mock_llm.return_value
    mock_llm_instance.generate_answer.return_value = "Steve Jobs founded Apple."
    
    response = client.post(
        "/api/v1/query",
        json={"query": "Who founded Apple?", "limit": 5}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "graph_context" in data


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_supported_formats():
    """Test getting supported file formats."""
    response = client.get("/api/v1/supported-formats")
    assert response.status_code == 200
    formats = response.json()["formats"]
    assert ".pdf" in formats
    assert ".docx" in formats


@patch("src.api.routes.get_document_service")
@patch("src.api.routes.get_rag_service")
def test_ingest_file_invalid_type(mock_rag, mock_doc):
    """Test file upload with invalid file type."""
    mock_doc_instance = MagicMock()
    mock_doc_instance.get_supported_formats.return_value = [".pdf", ".docx"]
    mock_doc.return_value = mock_doc_instance
    
    # Upload a .txt file which is not supported
    response = client.post(
        "/api/v1/ingest/file",
        files={"file": ("test.txt", b"some content", "text/plain")}
    )
    
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


@patch("src.services.rag_service.QdrantService")
@patch("src.services.rag_service.EmbeddingService")
@patch("src.services.rag_service.LLMService")
@patch("src.services.document_service.DocumentService.parse_document")
def test_ingest_file_pdf_success(mock_parse, mock_llm, mock_embedding, mock_qdrant):
    """Test successful PDF file upload."""
    # Mock document parsing
    mock_parse.return_value = (
        "This is the document content.",
        {"filename": "test.pdf", "file_type": ".pdf", "num_pages": 1}
    )
    
    # Mock embedding
    mock_embedding_instance = mock_embedding.return_value
    mock_embedding_instance.embed_query.return_value = [0.1] * 384
    
    # Mock LLM
    mock_llm_instance = mock_llm.return_value
    mock_llm_instance.extract_entities.return_value = []
    
    response = client.post(
        "/api/v1/ingest/file",
        files={"file": ("test.pdf", b"fake pdf content", "application/pdf")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["filename"] == "test.pdf"
    assert data["num_chunks"] >= 1
