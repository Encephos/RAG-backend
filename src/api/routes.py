from fastapi import APIRouter, HTTPException, Depends
from src.models.schemas import IngestRequest, IngestResponse, QueryRequest, QueryResponse
from src.services.rag_service import RagService

router = APIRouter()

# Dependency to get RagService instance
def get_rag_service():
    return RagService()

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
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    return {"status": "ok"}
