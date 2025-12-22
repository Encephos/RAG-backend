from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Request
from typing import List, Optional
from pathlib import Path
from src.services.rag_service import RagService
from src.services.document_service import DocumentService
from src.services.scraper_service import ScraperService
from src.services.academic_scraper import AcademicSourceScraper
from src.services.kg_service import KnowledgeGraphService # Added import for KnowledgeGraphService
from src.models.schemas import (
    IngestRequest, IngestResponse, 
    QueryRequest, QueryResponse,
    UrlIngestRequest, AcademicIngestRequest
)
from src.core.limiter import limiter
from src.core.config import settings
import logging

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nexus.api")

router = APIRouter()

def get_rag_service():
    return RagService()

def get_document_service():
    return DocumentService()

def get_scraper_service():
    return ScraperService()

def get_academic_scraper():
    return AcademicSourceScraper()

def get_kg_service():
    return KnowledgeGraphService()

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
    
    # Sanitize filename to prevent path traversal
    original_filename = file.filename or "unknown"
    safe_filename = Path(original_filename).name # Keeps only the basename
    # Further ensure no weird characters if needed, but basename is usually enough for traversal
    
    file_path = source_dir / safe_filename

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
                
            yield json.dumps({"step": "parsing", "message": "Parsing document structure (this may take a while)...", "progress": 0.05}) + "\n"
            
            # Shared state for progress reporting
            progress_state = {"message": "Parsing...", "progress": 0.05}
            
            def progress_handler(current_page, total_pages):
                batch_num = (current_page // 10) + 1
                total_batches = (total_pages // 10) + 1 if total_pages % 10 != 0 else total_pages // 10
                progress_state["message"] = f"Processing PDF Part {batch_num}/{total_batches}"
                # Progress ranges from 0.05 to 0.7 during parsing
                progress_state["progress"] = 0.05 + (0.65 * (current_page / total_pages))
            
            # Run parsing in threadpool and poll for completion to keep connection alive
            import asyncio
            from starlette.concurrency import run_in_threadpool
            from functools import partial
            
            # Create a wrapped function with the callback pre-bound
            parse_func = partial(document_service.parse_document, str(file_path), progress_callback=progress_handler)
            
            # Create a future for the parsing task
            parse_task = asyncio.create_task(run_in_threadpool(parse_func))
            
            start_time = asyncio.get_event_loop().time()
            last_message = ""
            
            while not parse_task.done():
                elapsed = int(asyncio.get_event_loop().time() - start_time)
                
                # Emit update if message changed or every 2 seconds heartbeat
                if (progress_state["message"] != last_message) or (elapsed > 0 and elapsed % 2 == 0):
                    last_message = progress_state["message"]
                    yield json.dumps({"step": "parsing", "message": f"{last_message} ({elapsed}s)", "progress": progress_state["progress"]}) + "\n"
                
                await asyncio.sleep(0.5)
                
            # Get result or raise exception
            text, parse_metadata = await parse_task
            
            source_url = f"http://localhost:8000/sources/{safe_filename}"
            parse_metadata["source_url"] = source_url
            
            logger.info(f"[{safe_filename}] Parsed successfully. Text length: {len(text)}. Metadata: {parse_metadata}")

            chunks = document_service.chunk_text(text, parse_metadata)
            full_text = "\n\n".join([c.text for c in chunks])
            
            logger.info(f"[{safe_filename}] Created {len(chunks)} chunks. Starting RAG ingestion...")

            async for event in rag_service.ingest_document_generator(full_text, chunks, target_collections=target_cols, source_name=safe_filename):
                yield json.dumps(event) + "\n"
                
        except Exception as e:
            logger.error(f"[{safe_filename}] Ingestion failed: {e}")
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
            
            full_text = "\n\n---PAGE BREAK---\n\n".join(combined_text)
            
            logger.info(f"[{url_request.url}] Starting RAG ingestion for {len(all_chunks)} chunks...")
            
            async for event in rag_service.ingest_document_generator(full_text, all_chunks, target_collections=target_cols, source_name=url_request.url):
                yield json.dumps(event) + "\n"
                
        except Exception as e:
            logger.error(f"[{url_request.url}] Ingestion failed: {e}")
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

@router.post("/ingest/strains")
@limiter.limit("5/minute")
async def ingest_strains(
    request: Request,
    rag_service: RagService = Depends(get_rag_service)
):
    """
    Trigger ingestion of Cannabis Strains from local CSV file.
    Default path: data/sources/all_strains_seedfinder.csv
    Streams progress updates.
    """
    file_path = "data/sources/all_strains_seedfinder.csv"
    path_obj = Path(file_path)
    
    if not path_obj.exists():
        raise HTTPException(status_code=404, detail=f"Strains file not found at {file_path}")

    async def event_generator():
        try:
            async for event in rag_service.ingest_strains_generator(file_path):
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
                    
                    async for event in rag_service.ingest_document_generator(full_text, chunks, target_collections=target_cols, source_name=doc.get("title")):
                         pass
                    
                    logger.info(f"[{doc.get('title')}] Ingestion complete.")
                    
                    processed_count += 1
                    
                except Exception as e:
                    yield json.dumps({"step": "warning", "message": f"Failed to ingest {doc.get('title')}: {str(e)}"}) + "\n"

            yield json.dumps({"step": "complete", "message": f"Successfully ingested {processed_count} papers.", "progress": 1.0}) + "\n"

        except Exception as e:
            yield json.dumps({"step": "error", "message": str(e)}) + "\n"


@router.post("/ingest/snapshot")
@limiter.limit("5/minute")
async def ingest_snapshot(
    request: Request,
    file: UploadFile = File(...),
    rag_service: RagService = Depends(get_rag_service)
):
    """
    Upload and recover a Qdrant snapshot.
    Collection is auto-detected from filename.
    """
    async def event_generator():
        try:
            filename = file.filename or "snapshot.snapshot"
            yield json.dumps({"step": "upload", "message": f"Reading snapshot '{filename}'...", "progress": 0.0}) + "\n"
            
            # Read file into memory (Warning: High memory usage for huge snapshots)
            # For purely streaming proxy, we'd need more complex httpx streaming
            content = await file.read()
            
            yield json.dumps({"step": "restoring", "message": f"Uploading to Qdrant ({len(content) / 1024 / 1024:.1f} MB)...", "progress": 0.3}) + "\n"
            
            target_col = await rag_service.qdrant_service.recover_snapshot_from_file(content, filename)
            
            yield json.dumps({"step": "complete", "message": f"Successfully restored to '{target_col}'!", "progress": 1.0}) + "\n"
            
        except Exception as e:
            logger.error(f"Snapshot restore failed: {e}")
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

@router.get("/graph/visualize")
async def visualize_graph(
    query: str,
    collection: Optional[str] = None,
    kg_service: KnowledgeGraphService = Depends(get_kg_service)
):
    """
    Get graph nodes and edges for visualization based on query.
    """
    try:
        data = await kg_service.get_visualization_data(query, collection_name=collection)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/graph/lineage")
async def get_lineage_graph(
    strain: str,
    depth: int = 10,
    direction: str = "parents", # 'parents' or 'children' (future)
    kg_service: KnowledgeGraphService = Depends(get_kg_service)
):
    """
    Get genealogy graph for a specific strain.
    """
    try:
        # We can map direction to different logic if needed later
        data = await kg_service.get_lineage(strain, depth=depth, collection_name="botanical_entities_768")
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_stats(
    rag_service: RagService = Depends(get_rag_service)
):
    stats = await rag_service.qdrant_service.get_total_points()
    return {
        "version": settings.VERSION,
        "total_points": stats["total_points"],
        "details": stats["details"]
    }

import base64

@router.post("/tools/diagnose-leaf")
async def diagnose_leaf(
    file: UploadFile = File(...),
    rag_service: RagService = Depends(get_rag_service)
):
    """
    Diagnose a cannabis leaf image using Gemini Vision + Botanical Agent.
    """
    # 1. Read and encode image
    contents = await file.read()
    image_b64 = base64.b64encode(contents).decode("utf-8")

    # 2. Vision Analysis (Gemini 2.5)
    vision_prompt = "Beschreibe rein sachlich und detailliert, was visuell auf diesem Bild (Cannabis-Blatt)zu sehen ist (Farbe der Blätter, Flecken, Textur, eventuelle Insekten). Stelle KEINE Diagnosen und nenne KEINE möglichen Mangelerscheinungen oder Krankheiten. Bleibe rein deskriptiv."
    img_description = await rag_service.llm_service.analyze_image(image_b64, vision_prompt)

    # 3. RAG Query (Botanist)
    query = f"Basierend auf dieser visuellen Analyse: '{img_description}' - Was fehlt der Pflanze und wie behandle ich es?"
    
    query_vector = await rag_service.embedding_service.embed_query(query)
    
    # Search in Botanical knowledge base
    rag_results = rag_service.qdrant_service.search(
        vector=query_vector,
        limit=3,
        collection_alias="botanical",
        query_text=query # Enable Hybrid Search
    )
    
    context = "\n".join([f"- {doc['text']}" for doc in rag_results])
    
    # 4. Generate Diagnosis
    final_diagnosis = await rag_service.llm_service.generate_answer(query, context)

    # 5. Fetch Knowledge Graph Visualization
    # unique to botanical collection
    entity_col = rag_service.qdrant_service.entity_collections.get("botanical")
    graph_data = {"nodes": [], "edges": []}
    if entity_col:
        try:
             graph_data = await rag_service.kg_service.get_visualization_data(query, collection_name=entity_col)
        except Exception:
            pass # Fail silently for graph viz if empty

    return {
        "visual_analysis": img_description,
        "diagnosis": final_diagnosis,
        "rag_context": rag_results.to_dict() if hasattr(rag_results, "to_dict") else rag_results,
        "graph_data": graph_data
    }
