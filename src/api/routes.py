from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from src.models.schemas import (
    IngestRequest, IngestResponse, QueryRequest, QueryResponse,
    FileIngestResponse, ChunkInfoResponse
)
from src.services.rag_service import RagService
from src.services.document_service import DocumentService
import traceback

router = APIRouter()

# Dependency to get RagService instance
def get_rag_service():
    return RagService()

def get_document_service():
    return DocumentService()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    request: IngestRequest,
    rag_service: RagService = Depends(get_rag_service)
):
    try:
        rag_service.ingest(request.text, request.metadata)
        return IngestResponse(
            status="success",
            message="Document ingested successfully"
        )
    except Exception as e:
        print(f"Ingest error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ingest/file", response_model=FileIngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    rag_service: RagService = Depends(get_rag_service),
    doc_service: DocumentService = Depends(get_document_service)
):
    """
    Upload and ingest a document file (PDF, DOCX, PPTX, HTML).
    The document will be parsed, chunked, and each chunk ingested into the RAG system.
    """
    try:
        # Validate file type
        filename = file.filename or "unknown"
        suffix = filename.lower().split('.')[-1] if '.' in filename else ''
        supported = [fmt.lstrip('.') for fmt in doc_service.get_supported_formats()]
        
        if suffix not in supported:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: .{suffix}. Supported: {supported}"
            )
        
        # Read file content
        content = await file.read()
        
        # Check file size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Process document
        chunks, metadata = await doc_service.process_uploaded_file(content, filename)
        
        # Ingest each chunk
        for chunk in chunks:
            rag_service.ingest(chunk.text, chunk.metadata)
        
        # Build response
        chunk_responses = [
            ChunkInfoResponse(
                text=chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text,
                chunk_index=chunk.chunk_index,
                start_char=chunk.start_char,
                end_char=chunk.end_char
            )
            for chunk in chunks
        ]
        
        return FileIngestResponse(
            status="success",
            message=f"Document ingested successfully with {len(chunks)} chunks",
            filename=metadata.filename,
            file_type=metadata.file_type,
            num_pages=metadata.num_pages,
            num_chunks=metadata.num_chunks,
            total_characters=metadata.total_characters,
            chunks=chunk_responses
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"File ingest error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query", response_model=QueryResponse)
async def query_rag(
    request: QueryRequest,
    rag_service: RagService = Depends(get_rag_service)
):
    try:
        result = rag_service.query(request.query, request.limit)
        return QueryResponse(**result)
    except Exception as e:
        print(f"Query error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    return {"status": "ok"}

@router.get("/supported-formats")
async def get_supported_formats(
    doc_service: DocumentService = Depends(get_document_service)
):
    """Get list of supported file formats for upload."""
    return {"formats": doc_service.get_supported_formats()}
