from typing import List, Dict, Any
from src.services.qdrant_service import QdrantService
from src.services.embedding_service import EmbeddingService
from src.services.kg_service import KnowledgeGraphService
from src.services.llm_service import LLMService
from src.models.schemas import SearchResult

class RagService:
    def __init__(self):
        self.qdrant_service = QdrantService()
        self.embedding_service = EmbeddingService()
        self.kg_service = KnowledgeGraphService()
        self.llm_service = LLMService()

    def ingest(self, text: str, metadata: Dict[str, Any] = None):
        """Ingest text into both Vector DB and Knowledge Graph."""
        # 1. Vector Store
        vector = self.embedding_service.embed_query(text)
        self.qdrant_service.upsert(text, vector, metadata)

        # 2. Knowledge Graph - Extract entities using LLM
        triples = self.llm_service.extract_entities(text)
        for triple in triples:
            self.kg_service.add_triple(
                subject=triple.subject,
                predicate=triple.predicate,
                obj=triple.object,
                confidence=triple.confidence
            )

    def query(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Query the RAG system with LLM-generated answer."""
        # 1. Vector Search
        query_vector = self.embedding_service.embed_query(query)
        search_results = self.qdrant_service.search(query_vector, limit)
        
        # 2. Graph Context - Extract entities from search results
        all_text = " ".join([r["text"] for r in search_results])
        # Simple entity extraction for graph lookup (capitalized words)
        words = query.split() + all_text.split()
        query_entities = list(set([
            w.strip(".,!?") for w in words 
            if len(w) > 1 and w[0].isupper()
        ]))
        
        graph_context_str = self.kg_service.get_graph_context_string(query_entities, depth=1)
        graph_context_dict = self.kg_service.get_subgraph(query_entities, depth=1)

        # 3. Generate Answer using LLM
        context_text = "\n\n".join([r["text"] for r in search_results])
        answer = self.llm_service.generate_answer(query, context_text, graph_context_str)

        return {
            "answer": answer,
            "context": search_results,
            "graph_context": graph_context_dict
        }
