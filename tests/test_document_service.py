import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from src.services.document_service import DocumentService, ChunkInfo, DocumentMetadata

class TestDocumentService:
    
    def test_chunk_text_basic(self):
        """Test basic text chunking."""
        service = DocumentService(chunk_size=100, chunk_overlap=20)
        text = "This is sentence one. This is sentence two. This is sentence three. This is sentence four."
        
        chunks = service.chunk_text(text)
        
        assert len(chunks) >= 1
        assert all(isinstance(c, ChunkInfo) for c in chunks)
        assert chunks[0].chunk_index == 0

    def test_chunk_text_with_overlap(self):
        """Test that chunks have proper overlap."""
        service = DocumentService(chunk_size=50, chunk_overlap=10)
        text = "First sentence here. Second sentence here. Third sentence here. Fourth sentence here."
        
        chunks = service.chunk_text(text)
        
        # With small chunk size, we should get multiple chunks
        assert len(chunks) >= 2

    def test_chunk_text_with_metadata(self):
        """Test chunking preserves metadata."""
        service = DocumentService(chunk_size=200, chunk_overlap=20)
        text = "Sample text for testing chunking functionality."
        metadata = {"source": "test", "page": 1}
        
        chunks = service.chunk_text(text, metadata)
        
        assert chunks[0].metadata["source"] == "test"
        assert chunks[0].metadata["page"] == 1
        assert "chunk_index" in chunks[0].metadata

    def test_split_into_sentences(self):
        """Test sentence splitting."""
        service = DocumentService()
        text = "First sentence. Second sentence! Third sentence?"
        
        sentences = service._split_into_sentences(text)
        
        assert len(sentences) == 3
        assert "First sentence." in sentences[0]

    def test_get_supported_formats(self):
        """Test supported formats list."""
        service = DocumentService()
        formats = service.get_supported_formats()
        
        assert ".pdf" in formats
        assert ".docx" in formats
        assert ".pptx" in formats

    @patch("src.services.document_service.DocumentService._get_converter")
    def test_parse_document_success(self, mock_get_converter):
        """Test document parsing with mocked Docling."""
        mock_converter = MagicMock()
        mock_result = MagicMock()
        mock_result.document.export_to_markdown.return_value = "# Title\n\nSome content."
        mock_result.document.num_pages = 5
        mock_converter.convert.return_value = mock_result
        mock_get_converter.return_value = mock_converter
        
        service = DocumentService()
        text, metadata = service.parse_document("/fake/path/document.pdf")
        
        assert "# Title" in text
        assert metadata["filename"] == "document.pdf"
        assert metadata["file_type"] == ".pdf"

    @patch("src.services.document_service.DocumentService.parse_document")
    def test_process_uploaded_file(self, mock_parse):
        """Test processing an uploaded file."""
        import asyncio
        mock_parse.return_value = ("Sample document content for testing.", {"filename": "test.pdf", "file_type": ".pdf", "num_pages": 3})
        
        service = DocumentService(chunk_size=100, chunk_overlap=10)
        content = b"fake pdf content"
        
        # Run async function        # Execute
        chunks, metadata = asyncio.run(
            service.process_uploaded_file(content, "test.pdf")
        )
        
        assert len(chunks) >= 1
        assert metadata.filename == "test.pdf"
        assert metadata.file_type == ".pdf"


class TestChunkInfo:
    def test_chunk_info_creation(self):
        """Test ChunkInfo dataclass."""
        chunk = ChunkInfo(
            text="Sample text",
            chunk_index=0,
            start_char=0,
            end_char=11,
            metadata={"source": "test"}
        )
        
        assert chunk.text == "Sample text"
        assert chunk.chunk_index == 0
        assert chunk.metadata["source"] == "test"


class TestDocumentMetadata:
    def test_document_metadata_creation(self):
        """Test DocumentMetadata dataclass."""
        metadata = DocumentMetadata(
            filename="test.pdf",
            file_type=".pdf",
            num_pages=10,
            num_chunks=5,
            total_characters=1000
        )
        
        assert metadata.filename == "test.pdf"
        assert metadata.num_pages == 10
        assert metadata.num_chunks == 5
