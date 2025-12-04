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
        Ingest a single chunk/text. 
        Legacy method, kept for simple text ingestion.
        """
        await self.ingest_document(text, [{"text": text, "metadata": metadata}])

    async def ingest_document(self, full_text: str, chunks: List[Any]):
        """
        Ingest a full document.
        - Upserts small chunks to Vector DB.
        - Extracts entities from full text (or large blocks) for Knowledge Graph.
        """
        logger.info(f"Starting document ingestion. Size: {len(full_text)} chars, Chunks: {len(chunks)}")
        
        # 1. Vector Store (Document Chunks)
        # Process chunks in parallel or batch if possible, but loop is fine for now
        for chunk in chunks:
            # Handle both ChunkInfo objects and dicts
            c_text = chunk.text if hasattr(chunk, 'text') else chunk["text"]
            c_meta = chunk.metadata if hasattr(chunk, 'metadata') else chunk["metadata"]
            
            vector = await self.embedding_service.embed_query(c_text)
            self.qdrant_service.upsert(c_text, vector, c_meta)
        logger.debug(f"Upserted {len(chunks)} chunks to Qdrant.")

        # 2. Knowledge Graph Construction
        # Use full_text for extraction to reduce API calls and improve context
        # User has 1M token context window, so we can send very large blocks
        # 200k chars ~ 50k tokens, well within the 1M token limit
        
        chunk_size = 200000 # 200k chars ~ 50k tokens
        text_blocks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
        
        for block in text_blocks:
            extraction = await self.llm_service.extract_entities(block)
            logger.debug(f"Extracted {len(extraction.entities)} entities from block.")
            
            # Map entity names to their resolved IDs
            entity_name_to_id = {}
            
            # Process Entities
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
        logger.info("Document ingestion complete.")

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
