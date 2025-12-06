from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Request
from typing import List, Optional
from pathlib import Path
from src.services.rag_service import RagService
from src.services.document_service import DocumentService
from src.services.scraper_service import ScraperService
from src.services.academic_scraper import AcademicSourceScraper
from src.models.schemas import (
    IngestRequest, IngestResponse, 
    QueryRequest, QueryResponse,
    UrlIngestRequest, AcademicIngestRequest
)
from src.core.limiter import limiter

router = APIRouter()

def get_rag_service():
    return RagService()

def get_document_service():
    return DocumentService()

def get_scraper_service():
    return ScraperService()

def get_academic_scraper():
    return AcademicSourceScraper()

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

from fastapi.responses import StreamingResponse
import json

from fastapi import Form

@router.post("/ingest/file")
@limiter.limit("20/minute")
async def ingest_file(
    request: Request,
    file: UploadFile = File(...),
    collections: Optional[str] = Form(None),
    rag_service: RagService = Depends(get_rag_service),
    document_service: DocumentService = Depends(get_document_service)
):
    source_dir = Path("data/sources")
    source_dir.mkdir(parents=True, exist_ok=True)
    filename = file.filename or "unknown"
    file_path = source_dir / filename

    # Parse Collections
    target_cols = []
    if collections:
        # Handle comma-separated string
        target_cols = [c.strip() for c in collections.split(",") if c.strip()]

    async def event_generator():
        try:
            yield json.dumps({"step": "upload", "message": f"Uploading and saving file... (Collections: {target_cols})", "progress": 0.0}) + "\n"
            
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
                
            yield json.dumps({"step": "parsing", "message": "Parsing document structure...", "progress": 0.02}) + "\n"
            text, parse_metadata = document_service.parse_document(str(file_path))
            
            source_url = f"http://localhost:8000/sources/{filename}"
            parse_metadata["source_url"] = source_url
            
            chunks = document_service.chunk_text(text, parse_metadata)
            full_text = "\n\n".join([c.text for c in chunks])
            
            async for event in rag_service.ingest_document_generator(full_text, chunks, target_collections=target_cols):
                yield json.dumps(event) + "\n"
                
        except Exception as e:
            yield json.dumps({"step": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@router.post("/ingest/url")
@limiter.limit("10/minute")
async def ingest_url(
    request: Request,
    url_request: UrlIngestRequest,
    rag_service: RagService = Depends(get_rag_service),
    scraper_service: ScraperService = Depends(get_scraper_service),
    document_service: DocumentService = Depends(get_document_service)
):
    async def event_generator():
        try:
            target_cols = url_request.collections or []
            yield json.dumps({"step": "scraping", "message": f"Crawling {url_request.url}... (Collections: {target_cols})", "progress": 0.0}) + "\n"
            
            max_pages = 5 if url_request.recursive else 1
            scraped_data = await scraper_service.crawl_domain(url_request.url, max_pages=max_pages)
            
            yield json.dumps({"step": "chunking", "message": f"Processed {len(scraped_data)} pages. Chunking text...", "progress": 0.05}) + "\n"
            
            all_chunks = []
            combined_text = []
            
            for page in scraped_data:
                page_metadata = {
                    "source": page["url"],
                    "source_url": page["url"],
                    "type": "web_page",
                    "depth": page.get("metadata", {}).get("depth", 0)
                }
                chunks = document_service.chunk_text(page["text"], page_metadata)
                all_chunks.extend(chunks)
                combined_text.append(page["text"])
            
            full_text = "\n\n---PAGE BREAK---\n\n".join(combined_text)
            
            async for event in rag_service.ingest_document_generator(full_text, all_chunks, target_collections=target_cols):
                yield json.dumps(event) + "\n"
                
        except Exception as e:
            yield json.dumps({"step": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@router.post("/ingest/compounds")
@limiter.limit("5/minute")
async def ingest_compounds(
    request: Request,
    rag_service: RagService = Depends(get_rag_service)
):
    """
    Trigger ingestion of Cannabis Compounds from local XML file.
    Default path: data/sources/compounds.xml
    Streams progress updates.
    """
    file_path = "data/sources/compounds.xml"
    path_obj = Path(file_path)
    
    if not path_obj.exists():
        raise HTTPException(status_code=404, detail=f"Compounds file not found at {file_path}")

    async def event_generator():
        try:
            async for event in rag_service.ingest_cannabis_compounds_generator(file_path):
                yield json.dumps(event) + "\n"
        except Exception as e:
            yield json.dumps({"step": "error", "message": f"Ingestion failed: {str(e)}"}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@router.post("/ingest/academic")
@limiter.limit("5/minute")
async def ingest_academic(
    request: Request,
    ingest_request: AcademicIngestRequest,
    rag_service: RagService = Depends(get_rag_service),
    academic_scraper: AcademicSourceScraper = Depends(get_academic_scraper),
    scraper_service: ScraperService = Depends(get_scraper_service),
    document_service: DocumentService = Depends(get_document_service)
):
    async def event_generator():
        try:
            target_cols = ingest_request.collections or []
            yield json.dumps({"step": "search", "message": f"Searching for academic papers on '{ingest_request.query}'...", "progress": 0.0}) + "\n"
            
            candidates = academic_scraper.search_sources(
                query=ingest_request.query, 
                limit=ingest_request.limit, 
                category=ingest_request.category
            )
            
            yield json.dumps({"step": "processing", "message": f"Found {len(candidates)} candidates. Processing...", "progress": 0.1}) + "\n"
            
            processed_count = 0
            
            for doc in candidates:
                yield json.dumps({"step": "ingest", "message": f"Processing: {doc.get('title', 'Unknown')}", "progress": 0.1 + (0.8 * (processed_count / len(candidates)))}) + "\n"
                
                try:
                    full_text = ""
                    # Strategy A: If valid open access PDF/URL, try to scrape/download
                    if doc.get("url") and (doc.get("metadata", {}).get("is_open_access") or doc["url"].endswith(".pdf")):
                        
                        # 1. Try PDF Download
                        if doc["url"].endswith(".pdf"):
                            yield json.dumps({"step": "download", "message": f"Downloading PDF: {doc.get('title')}...", "progress": 0.1}) + "\n"
                            
                            # Use scraper service to download (non-blocking)
                            from starlette.concurrency import run_in_threadpool
                            pdf_bytes = await run_in_threadpool(scraper_service.download_file, doc["url"])
                            
                            if pdf_bytes:
                                yield json.dumps({"step": "parsing", "message": "Parsing PDF content...", "progress": 0.15}) + "\n"
                                # Reuse DocumentService to parse the bytes
                                chunks_info, pdf_meta = await document_service.process_uploaded_file(pdf_bytes, doc.get("title", "downloaded.pdf") + ".pdf")
                                full_text = "\n\n".join([c.text for c in chunks_info])
                            else:
                                 yield json.dumps({"step": "warning", "message": "PDF download failed. Falling back to Abstract."}) + "\n"

                        # 2. If no PDF or download failed, try scraping HTML if it's a URL
                        if not full_text and not doc["url"].endswith(".pdf"):
                            scrape_data = await scraper_service.crawl_domain(doc["url"], max_pages=1)
                            if scrape_data:
                                full_text = scrape_data[0]["text"]
                                yield json.dumps({"step": "ingest", "message": f"Scraped Web Page: {len(full_text)} chars", "progress": 0.2}) + "\n"

                        # 3. Fallback to Abstract
                        if not full_text:
                            yield json.dumps({"step": "warning", "message": "No full text/PDF found. Ingesting Abstract only."}) + "\n"
                            full_text = doc.get("abstract", "") # Fallback
                        
                    else:
                        yield json.dumps({"step": "info", "message": "Ingesting Abstract (No URL).", "progress": 0.2}) + "\n"
                        # Strategy B: Ingest Abstract direclty
                        full_text = f"Title: {doc['title']}\nAbstract: {doc.get('abstract', '')}\nURL: {doc.get('url', 'N/A')}\nMetadata: {doc.get('metadata', {})}"

                    if not full_text.strip():
                         yield json.dumps({"step": "warning", "message": "Skipping empty document."}) + "\n"
                         continue

                    # Chunk and Ingest (if not already done via PDF parser)
                    # If we parsed PDF, we effectively have better chunks.
                    # But ingest_document_generator expects full_text.
                    
                    base_metadata = {
                        "source": doc.get("url") or f"academic_search_{ingest_request.query}",
                        "source_url": doc.get("url"),
                        "title": doc.get("title"),
                        "type": "academic_paper",
                        "category": ingest_request.category
                    }
                    
                    # If we didn't get chunks from PDF parser, chunk now
                    # Note: We can optimize this by using PDF chunks if available
                    # For now, let's keep it simple: re-chunking is fine or passing explicit chunks.
                    chunks = document_service.chunk_text(full_text, base_metadata)
                    
                    async for event in rag_service.ingest_document_generator(full_text, chunks, target_collections=target_cols):
                         pass
                    
                    processed_count += 1
                    
                except Exception as e:
                    yield json.dumps({"step": "warning", "message": f"Failed to ingest {doc.get('title')}: {str(e)}"}) + "\n"

            yield json.dumps({"step": "complete", "message": f"Successfully ingested {processed_count} papers.", "progress": 1.0}) + "\n"

        except Exception as e:
            yield json.dumps({"step": "error", "message": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

from src.services.council_service import CouncilService

def get_council_service():
    return CouncilService()

@router.post("/query", response_model=QueryResponse)
@limiter.limit("100/minute")
async def query_rag(
    request: Request,
    query_request: QueryRequest,
    rag_service: RagService = Depends(get_rag_service),
    council_service: CouncilService = Depends(get_council_service)
):
    try:
        if query_request.selected_council_members and len(query_request.selected_council_members) > 0:
            # Council Mode
            result = await council_service.process_council_query(
                query_request.query, 
                query_request.selected_council_members
            )
            return QueryResponse(
                answer=result["answer"],
                context=result["context"],
                graph_context=result.get("graph_context", {}),
                council_results=result.get("council_results")
            )
        else:
            # Standard Mode
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

@router.get("/stats")
async def get_system_stats(
    rag_service: RagService = Depends(get_rag_service)
):
    """Get system statistics."""
    total_points = rag_service.qdrant_service.count_points("master")
    # You could also sum up other collections if they are separate
    
    return {
        "version": "0.4.2", # Nexus AI Beta
        "total_points": total_points,
        "collections": {
            "master": total_points
        }
    }
