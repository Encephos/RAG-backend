from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import tempfile
import os
import fitz
import gc
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
    def __init__(self, chunk_size: int = 1500, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._docling_converter = None
    
    def _get_converter(self):
        """Lazy load Docling converter to avoid import time overhead."""
        if self._docling_converter is None:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
            from docling.datamodel.base_models import InputFormat

            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = True # Enable OCR fallback
            pipeline_options.do_table_structure = True 
            
            # Configure OCR to use Tesseract (CPU friendly) or EasyOCR
            # Tesseract is typically faster on CPU than EasyOCR for large batches if configured right
            # But Docling defaults are usually sane.
            
            self._docling_converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                }
            )
        return self._docling_converter

    def parse_document(self, file_path: str, progress_callback=None) -> Tuple[str, Dict[str, Any]]:
        """
        Parse a document using Docling and return extracted text with metadata.
        Supports: PDF, DOCX, PPTX, HTML, images.
        """
        if file_path.lower().endswith(".pdf"):
            return self._process_large_pdf(file_path, progress_callback=progress_callback)

        converter = self._get_converter()
        result = converter.convert(file_path)
        
        # Extract text in markdown format
        text = result.document.export_to_markdown()
        
        # Extract metadata
        num_pages = getattr(result.document, 'num_pages', None)
        if callable(num_pages):
            num_pages = num_pages()
            
        metadata = {
            "filename": Path(file_path).name,
            "file_type": Path(file_path).suffix.lower(),
            "num_pages": num_pages,
        }
        
        return text, metadata

    def _process_large_pdf(self, file_path: str, batch_size: int = 5, progress_callback=None) -> Tuple[str, Dict[str, Any]]:
        """
        Smartly process large PDFs by splitting them into batches of pages.
        Extracts text from each batch and merges the results.
        """
        
        doc = fitz.open(file_path)
        total_pages = len(doc)
        
        if total_pages <= batch_size:
            # Small enough, process normally
            doc.close()
            converter = self._get_converter()
            result = converter.convert(file_path)
            text = result.document.export_to_markdown()
            return text, {
                "filename": Path(file_path).name,
                "file_type": ".pdf",
                "num_pages": total_pages
            }

        # Large PDF logic
        full_text_parts = []
        import tempfile
        
        # We instantiate converter here, but we might want to clear it too?
        # Re-using the singleton self._docling_converter is efficient for model loading,
        # but might accumulate trash. Let's force GC.
        converter = self._get_converter()
        
        for i in range(0, total_pages, batch_size):
            end_page = min(i + batch_size, total_pages)
            
            # Report progress
            if progress_callback:
                progress_callback(i, total_pages)
                
            # Create a sub-document
            sub_doc = fitz.open()
            sub_doc.insert_pdf(doc, from_page=i, to_page=end_page - 1)
            
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
                sub_doc.save(tmp_pdf.name)
                tmp_path = tmp_pdf.name
            
            sub_doc.close()
            del sub_doc # Explicit delete
            
            try:
                # Convert the chunk
                result = converter.convert(tmp_path)
                part_text = result.document.export_to_markdown()
                full_text_parts.append(part_text)
                
                # Explicit cleanup
                del result
                del part_text
            except Exception as e:
                print(f"Error processing PDF chunk {i}-{end_page}: {e}")
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
            # Force Garbage Collection to prevent OOM
            gc.collect()
        
        doc.close()
        combined_text = "\n\n".join(full_text_parts)
        
        return combined_text, {
            "filename": Path(file_path).name,
            "file_type": ".pdf",
            "num_pages": total_pages
        }

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
