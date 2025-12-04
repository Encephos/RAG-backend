from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Request
from typing import List, Optional
from pathlib import Path
from src.services.rag_service import RagService
from src.services.document_service import DocumentService
from src.services.scraper_service import ScraperService
from src.models.schemas import (
    IngestRequest, IngestResponse, 
    QueryRequest, QueryResponse,
    UrlIngestRequest
)
from src.core.limiter import limiter

router = APIRouter()

def get_rag_service():
    return RagService()

def get_document_service():
    return DocumentService()

def get_scraper_service():
    return ScraperService()

@router.post("/ingest", response_model=IngestResponse)
@limiter.limit("50/minute")
async def ingest_document(
    request: Request,
    ingest_request: IngestRequest,
    rag_service: RagService = Depends(get_rag_service)
):
    try:
        await rag_service.ingest(ingest_request.text, ingest_request.metadata)
        return IngestResponse(
            status="success",
            message="Document ingested successfully"
        )
    except Exception as e:
        # Log error here
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ingest/file", response_model=IngestResponse)
@limiter.limit("20/minute")
async def ingest_file(
    request: Request,
    file: UploadFile = File(...),
    rag_service: RagService = Depends(get_rag_service),
    document_service: DocumentService = Depends(get_document_service)
):
    try:
        filename = file.filename or "unknown"
        suffix = Path(filename).suffix.lower()
        supported = document_service.get_supported_formats()
        
        if suffix not in supported:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")
            
        content = await file.read()
        chunks, metadata = await document_service.process_uploaded_file(content, filename)
        
        for chunk in chunks:
            await rag_service.ingest(chunk.text, chunk.metadata)
            
        return IngestResponse(
            status="success",
            message=f"File {filename} ingested successfully",
            filename=filename,
            num_chunks=len(chunks)
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"File ingest error: {e}")
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ingest/url", response_model=IngestResponse)
@limiter.limit("10/minute")
async def ingest_url(
    request: Request,
    url_request: UrlIngestRequest,
    rag_service: RagService = Depends(get_rag_service),
    scraper_service: ScraperService = Depends(get_scraper_service),
    document_service: DocumentService = Depends(get_document_service)
):
    try:
        max_pages = 5 if url_request.recursive else 1
        scraped_data = await scraper_service.crawl_domain(url_request.url, max_pages=max_pages)
        
        for page in scraped_data:
            chunk = document_service.chunk_text(page["text"], page)
            for c in chunk:
                 await rag_service.ingest(c.text, c.metadata)
                 
        return IngestResponse(
            status="success",
            message=f"URL {url_request.url} ingested successfully",
            pages_processed=len(scraped_data)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query", response_model=QueryResponse)
@limiter.limit("100/minute")
async def query_rag(
    request: Request,
    query_request: QueryRequest,
    rag_service: RagService = Depends(get_rag_service)
):
    try:
        result = await rag_service.query(query_request.query, query_request.limit)
        return QueryResponse(
            answer=result["answer"],
            context=result["context"],
            graph_context=result["graph_context"]
        )
    except Exception as e:
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
