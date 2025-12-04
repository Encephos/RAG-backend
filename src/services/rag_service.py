from typing import List, Dict, Any
from src.services.qdrant_service import QdrantService
from src.services.embedding_service import EmbeddingService
from src.services.kg_service import KnowledgeGraphService
from src.services.llm_service import LLMService
from src.models.schemas import SearchResult
import logging

logger = logging.getLogger(__name__)

class RagService:
    """
    Orchestrator service for RAG operations.
    Combines Vector Search and Knowledge Graph Retrieval.
    """
    def __init__(self):
        self.qdrant_service = QdrantService()
        self.embedding_service = EmbeddingService()
        self.kg_service = KnowledgeGraphService()
        self.llm_service = LLMService()

    async def ingest(self, text: str, metadata: Dict[str, Any] = None):
        """
        Ingest text into both Vector DB and SOTA Knowledge Graph.
        
        Args:
            text: The text content to ingest.
            metadata: Optional metadata for the document.
        """
        logger.info("Starting ingestion process...")
        
        # 1. Vector Store (Document Chunk)
        vector = await self.embedding_service.embed_query(text)
        self.qdrant_service.upsert(text, vector, metadata)
        logger.debug("Upserted document chunk to Qdrant.")

        # 2. Knowledge Graph Construction
        # Extract entities and relations using LLM
        extraction = await self.llm_service.extract_entities(text)
        logger.debug(f"Extracted {len(extraction.entities)} entities and {len(extraction.relations)} relations.")
        
        # Map entity names to their resolved IDs
        entity_name_to_id = {}
        
        # Process Entities (Resolution & Persistence)
        for entity in extraction.entities:
            entity_id = await self.kg_service.add_entity_with_resolution(
                name=entity.name,
                type=entity.type,
                description=entity.description
            )
            entity_name_to_id[entity.name] = entity_id
            
        # Process Relations
        for relation in extraction.relations:
            source_id = entity_name_to_id.get(relation.source)
            target_id = entity_name_to_id.get(relation.target)
            
            if source_id and target_id:
                self.kg_service.add_relation(
                    source_id=source_id,
                    target_id=target_id,
                    relation_type=relation.type
                )
        logger.info("Ingestion complete.")

    async def query(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """
        Query the RAG system with Vector-Native Graph Retrieval.
        
        Args:
            query: The user's question.
            limit: Number of document chunks to retrieve.
            
        Returns:
            Dictionary containing answer, context, and graph context.
        """
        logger.info(f"Processing query: {query}")
        
        # 1. Vector Search (Document Chunks)
        query_vector = await self.embedding_service.embed_query(query)
        search_results = self.qdrant_service.search(query_vector, limit)
        logger.debug(f"Retrieved {len(search_results)} document chunks.")
        
        # 2. Graph Retrieval (Semantic Entry Points)
        graph_context_str = await self.kg_service.get_graph_context(query)
        logger.debug("Retrieved graph context.")

        # 3. Generate Answer using LLM
        context_text = "\n\n".join([r["text"] for r in search_results])
        answer = await self.llm_service.generate_answer(query, context_text, graph_context_str)
        logger.info("Generated answer.")

        return {
            "answer": answer,
            "context": search_results,
            "graph_context": {"summary": graph_context_str}
        }
