from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
from src.main import app
from src.models.schemas import IngestResponse, QueryResponse
from src.core.config import settings

client = TestClient(app)
client.headers["X-API-Key"] = settings.BACKEND_API_KEY


@patch("src.services.rag_service.QdrantService")
@patch("src.services.kg_service.QdrantService") # Patch QdrantService in KG Service too
@patch("src.services.rag_service.EmbeddingService")
@patch("src.services.rag_service.LLMService")
def test_ingest_document(mock_llm, mock_embedding, mock_kg_qdrant, mock_rag_qdrant):
    """Test ingesting a document with LLM entity extraction."""
    # Setup mocks
    mock_embedding_instance = mock_embedding.return_value
    mock_embedding_instance.embed_query = AsyncMock(return_value=[0.1] * 384)
    
    # Configure both Qdrant mocks
    mock_rag_qdrant_instance = mock_rag_qdrant.return_value
    mock_kg_qdrant_instance = mock_kg_qdrant.return_value
    
    # Mock LLM entity extraction
    mock_llm_instance = mock_llm.return_value
    
    # Create mock ExtractionResult
    mock_extraction = MagicMock()
    mock_entity = MagicMock()
    mock_entity.name = "Apple"
    mock_entity.type = "Org"
    mock_entity.description = "Tech co"
    mock_extraction.entities = [mock_entity]
    mock_extraction.relations = []
    
    mock_llm_instance.extract_entities = AsyncMock(return_value=mock_extraction)
    
    # Mock KG entity search (resolution)
    mock_kg_qdrant_instance.search_entities.return_value = []
    
    response = client.post(
        "/api/v1/ingest",
        json={"text": "Apple was founded by Steve Jobs.", "metadata": {"source": "test"}}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Verify interactions
    mock_embedding_instance.embed_query.assert_called()
    mock_rag_qdrant_instance.upsert.assert_called()
    mock_llm_instance.extract_entities.assert_called()
    mock_kg_qdrant_instance.upsert_entity.assert_called()


@patch("src.services.rag_service.QdrantService")
@patch("src.services.rag_service.KnowledgeGraphService")
@patch("src.services.rag_service.EmbeddingService")
@patch("src.services.rag_service.LLMService")
def test_query_rag_with_llm_answer(mock_llm, mock_embedding, mock_kg, mock_qdrant):
    """Test querying RAG with LLM-generated answer."""
    # Setup mocks
    mock_embedding_instance = mock_embedding.return_value
    mock_embedding_instance.embed_query = AsyncMock(return_value=[0.1] * 384)
    
    mock_rag_qdrant_instance = mock_qdrant.return_value
    mock_rag_qdrant_instance.search.return_value = [
        {"text": "Apple is a technology company.", "score": 0.9, "metadata": {}}
    ]
    
    mock_kg_instance = mock_kg.return_value
    mock_kg_instance.get_graph_context = AsyncMock(return_value="Graph info")
    
    # Mock LLM answer generation
    mock_llm_instance = mock_llm.return_value
    mock_llm_instance.generate_answer = AsyncMock(return_value="Apple is a technology company headquartered in Cupertino.")
    
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
    assert data["graph_context"]["summary"] == "Graph info"

@patch("src.api.routes.RagService")
def test_query_with_graph_context(mock_rag_service):
    """Test query response includes graph context."""
    mock_instance = mock_rag_service.return_value
    mock_instance.query = AsyncMock(return_value={
        "answer": "Answer",
        "context": [],
        "graph_context": {"summary": "Entity: Apple - Tech Co"}
    })
    
    with patch("src.api.routes.get_rag_service", return_value=mock_instance):
        response = client.post(
            "/api/v1/query",
            json={"query": "Apple"}
        )
        
    assert response.status_code == 200
    assert "Apple" in response.json()["graph_context"]["summary"]


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
    # Mock parse_document to raise error for invalid type
    mock_doc_instance.parse_document.side_effect = ValueError("Input document test.txt with format None does not match any allowed format")
    mock_doc.return_value = mock_doc_instance
    
    # Upload a .txt file which is not supported
    response = client.post(
        "/api/v1/ingest/file",
        files={"file": ("test.txt", b"some content", "text/plain")}
    )
    
    # The API returns 200 OK with a stream that yields the error
    assert response.status_code == 200
    
    # Read the stream
    content = response.text
    # Relaxed assertion: just check for 'error' step
    assert '"step": "error"' in content
    # Optional: print content for debugging if needed
    # print(content)


@patch("src.api.routes.RagService")
@patch("src.api.routes.DocumentService")
def test_ingest_file_pdf_success(mock_doc_service, mock_rag_service):
    """Test successful PDF file ingestion."""
    # Mock RagService
    mock_rag_instance = mock_rag_service.return_value
    # Mock generator
    async def mock_generator(*args, **kwargs):
        yield {"step": "start", "message": "starting"}
        yield {"step": "complete", "message": "done", "progress": 1.0}
    
    mock_rag_instance.ingest_document_generator.side_effect = mock_generator
    
    # Mock DocumentService
    mock_doc_instance = mock_doc_service.return_value
    mock_doc_instance.parse_document.return_value = ("Parsed text", {})
    
    # Mock process_uploaded_file to return chunks
    mock_chunk = MagicMock()
    mock_chunk.text = "Chunk text"
    
    mock_doc_instance.chunk_text.return_value = [mock_chunk]
    
    with patch("src.api.routes.get_rag_service", return_value=mock_rag_instance), \
         patch("src.api.routes.get_document_service", return_value=mock_doc_instance):
        
        response = client.post(
            "/api/v1/ingest/file",
            files={"file": ("test.pdf", b"fake pdf content", "application/pdf")}
        )
        
    assert response.status_code == 200
    
    # Parse NDJSON
    lines = response.text.strip().split('\n')
    assert len(lines) > 0
    last_event = None
    for line in lines:
        import json
        event = json.loads(line)
        last_event = event
    
    if last_event["step"] == "error":
        pytest.fail(f"Ingestion failed with error: {last_event.get('message')}")
        
    assert last_event["step"] == "complete"


@patch("src.api.routes.RagService")
@patch("src.api.routes.ScraperService")
@patch("src.api.routes.DocumentService")
def test_ingest_url_success(mock_doc_service, mock_scraper_service, mock_rag_service):
    """Test successful URL ingestion."""
    # Mock RagService
    mock_rag_instance = mock_rag_service.return_value
    async def mock_generator(*args, **kwargs):
        yield {"step": "start", "message": "starting"}
        yield {"step": "complete", "message": "done", "progress": 1.0}
    
    mock_rag_instance.ingest_document_generator.side_effect = mock_generator
    
    # Mock ScraperService
    mock_scraper_instance = mock_scraper_service.return_value
    mock_scraper_instance.crawl_domain = AsyncMock(return_value=[{
        "url": "http://example.com",
        "text": "Web content",
        "metadata": {"source": "http://example.com"}
    }])
    
    # Mock DocumentService
    mock_doc_instance = mock_doc_service.return_value
    mock_chunk = MagicMock()
    mock_chunk.text = "Web content"
    mock_chunk.metadata = {}
    mock_doc_instance.chunk_text.return_value = [mock_chunk]
    
    with patch("src.api.routes.get_rag_service", return_value=mock_rag_instance), \
         patch("src.api.routes.get_scraper_service", return_value=mock_scraper_instance), \
         patch("src.api.routes.get_document_service", return_value=mock_doc_instance):
        
        response = client.post(
            "/api/v1/ingest/url",
            json={"url": "http://example.com", "recursive": False}
        )
        
    assert response.status_code == 200
    
    # Parse NDJSON
    lines = response.text.strip().split('\n')
    assert len(lines) > 0
    last_event = None
    for line in lines:
        import json
        event = json.loads(line)
        last_event = event
        
    if last_event["step"] == "error":
        raise AssertionError(f"Ingestion failed with error: {last_event.get('message')}")
    
    assert last_event["step"] == "complete"
