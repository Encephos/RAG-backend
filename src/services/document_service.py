from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import tempfile
import os
from dataclasses import dataclass

@dataclass
class ChunkInfo:
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: Dict[str, Any]

@dataclass
class DocumentMetadata:
    filename: str
    file_type: str
    num_pages: Optional[int]
    num_chunks: int
    total_characters: int

class DocumentService:
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._docling_converter = None
    
    def _get_converter(self):
        """Lazy load Docling converter to avoid import time overhead."""
        if self._docling_converter is None:
            from docling.document_converter import DocumentConverter
            self._docling_converter = DocumentConverter()
        return self._docling_converter

    def parse_document(self, file_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Parse a document using Docling and return extracted text with metadata.
        Supports: PDF, DOCX, PPTX, HTML, images.
        """
        converter = self._get_converter()
        result = converter.convert(file_path)
        
        # Extract text in markdown format
        text = result.document.export_to_markdown()
        
        # Extract metadata
        metadata = {
            "filename": Path(file_path).name,
            "file_type": Path(file_path).suffix.lower(),
            "num_pages": getattr(result.document, 'num_pages', None),
        }
        
        return text, metadata

    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[ChunkInfo]:
        """
        Split text into overlapping chunks using sentence-aware splitting.
        """
        if metadata is None:
            metadata = {}
        
        # Simple sentence-aware chunking
        sentences = self._split_into_sentences(text)
        chunks = []
        current_chunk = []
        current_length = 0
        chunk_index = 0
        start_char = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            if current_length + sentence_length > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = " ".join(current_chunk)
                chunks.append(ChunkInfo(
                    text=chunk_text,
                    chunk_index=chunk_index,
                    start_char=start_char,
                    end_char=start_char + len(chunk_text),
                    metadata={**metadata, "chunk_index": chunk_index}
                ))
                
                # Calculate overlap - keep last few sentences
                overlap_sentences = []
                overlap_length = 0
                for s in reversed(current_chunk):
                    if overlap_length + len(s) <= self.chunk_overlap:
                        overlap_sentences.insert(0, s)
                        overlap_length += len(s)
                    else:
                        break
                
                start_char = start_char + len(chunk_text) - overlap_length
                current_chunk = overlap_sentences
                current_length = overlap_length
                chunk_index += 1
            
            current_chunk.append(sentence)
            current_length += sentence_length
        
        # Don't forget the last chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append(ChunkInfo(
                text=chunk_text,
                chunk_index=chunk_index,
                start_char=start_char,
                end_char=start_char + len(chunk_text),
                metadata={**metadata, "chunk_index": chunk_index}
            ))
        
        return chunks

    def _split_into_sentences(self, text: str) -> List[str]:
        """Simple sentence splitting."""
        import re
        # Split on sentence endings, keeping the delimiter
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    async def process_uploaded_file(self, file_content: bytes, filename: str) -> Tuple[List[ChunkInfo], DocumentMetadata]:
        """
        Process an uploaded file: parse, chunk, and return results.
        """
        # Save to temp file
        suffix = Path(filename).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            # Parse document
            text, parse_metadata = self.parse_document(tmp_path)
            
            # Chunk text
            chunks = self.chunk_text(text, parse_metadata)
            
            # Build final metadata
            doc_metadata = DocumentMetadata(
                filename=filename,
                file_type=suffix.lower(),
                num_pages=parse_metadata.get("num_pages"),
                num_chunks=len(chunks),
                total_characters=len(text)
            )
            
            return chunks, doc_metadata
        finally:
            # Cleanup temp file
            os.unlink(tmp_path)

    def get_supported_formats(self) -> List[str]:
        """Return list of supported file formats."""
        return [".pdf", ".docx", ".pptx", ".html", ".htm", ".png", ".jpg", ".jpeg"]
