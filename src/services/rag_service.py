from typing import List, Dict, Any
from src.services.qdrant_service import QdrantService
from src.services.embedding_service import EmbeddingService
from src.services.kg_service import KnowledgeGraphService
from src.models.schemas import SearchResult

class RagService:
    def __init__(self):
        self.qdrant_service = QdrantService()
        self.embedding_service = EmbeddingService()
        self.kg_service = KnowledgeGraphService()

    def ingest(self, text: str, metadata: Dict[str, Any] = None):
        """Ingest text into both Vector DB and Knowledge Graph."""
        # 1. Vector Store
        vector = self.embedding_service.embed_query(text)
        self.qdrant_service.upsert(text, vector, metadata)

        # 2. Knowledge Graph (Simple extraction for demo)
        # Extract capitalized words as entities and link them sequentially
        words = text.split()
        entities = [w.strip(".,!?") for w in words if w[0].isupper() and len(w) > 1]
        
        for i in range(len(entities) - 1):
            source = entities[i]
            target = entities[i+1]
            self.kg_service.add_relation(source, target, "related_to")

    def query(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Query the RAG system."""
        # 1. Vector Search
        query_vector = self.embedding_service.embed_query(query)
        search_results = self.qdrant_service.search(query_vector, limit)
        
        # 2. Graph Context
        # Extract entities from query to find relevant subgraph
        query_words = query.split()
        query_entities = [w.strip(".,!?") for w in query_words if w[0].isupper() and len(w) > 1]
        
        graph_context = {}
        if query_entities:
            graph_context = self.kg_service.get_subgraph(query_entities, depth=1)

        # 3. Construct Answer (Mocked for now, usually would go to LLM)
        context_text = "\n".join([r["text"] for r in search_results])
        answer = f"Based on the context: {context_text[:100]}..." 

        return {
            "answer": answer,
            "context": search_results,
            "graph_context": graph_context
        }
