from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class IngestRequest(BaseModel):
    text: str
    metadata: Optional[Dict[str, Any]] = None

class IngestResponse(BaseModel):
    status: str
    message: str

class QueryRequest(BaseModel):
    query: str
    limit: int = 5

class SearchResult(BaseModel):
    text: str
    score: float
    metadata: Dict[str, Any]

class QueryResponse(BaseModel):
    answer: str
    context: List[SearchResult]
    graph_context: Dict[str, Any]
