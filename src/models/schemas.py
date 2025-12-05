from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class IngestRequest(BaseModel):
    text: str
    metadata: Optional[Dict[str, Any]] = None
    collections: Optional[List[str]] = None

class IngestResponse(BaseModel):
    status: str
    message: str
    filename: Optional[str] = None
    num_chunks: Optional[int] = None
    pages_processed: Optional[int] = None

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

# File upload schemas
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

# Web Scraping schemas
class UrlIngestRequest(BaseModel):
    url: str
    recursive: bool = False
    max_pages: int = 10
    max_depth: int = 2

class UrlIngestResponse(BaseModel):
    status: str
    message: str
    pages_processed: int
    total_chunks: int

# Knowledge Graph Schemas
class EntityNode(BaseModel):
    name: str
    type: str
    description: str

class Relation(BaseModel):
    source: str
    target: str
    type: str

class ExtractionResult(BaseModel):
    entities: List[EntityNode]
    relations: List[Relation]
