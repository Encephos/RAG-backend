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

# New schemas for file upload
class ChunkInfoResponse(BaseModel):
    text: str
    chunk_index: int
    start_char: int
    end_char: int

class FileIngestResponse(BaseModel):
    status: str
    message: str
    filename: str
    file_type: str
    num_pages: Optional[int]
    num_chunks: int
    total_characters: int
    chunks: List[ChunkInfoResponse]
