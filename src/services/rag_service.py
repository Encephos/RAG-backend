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
        Legacy ingestion method. Consumes the generator.
        """
        async for _ in self.ingest_document_generator(full_text, chunks):
            pass

    async def ingest_document_generator(self, full_text: str, chunks: List[Any]):
        """
        Generator that yields progress updates during ingestion.
        Yields: Dict[str, Any] with keys 'step', 'message', 'progress'
        """
        logger.info(f"Starting document ingestion. Size: {len(full_text)} chars, Chunks: {len(chunks)}")
        
        yield {"step": "start", "message": "Starting ingestion...", "progress": 0.05}
        
        # 1. Vector Store (Document Chunks)
        total_chunks = len(chunks)
        for i, chunk in enumerate(chunks):
            # Handle both ChunkInfo objects and dicts
            c_text = chunk.text if hasattr(chunk, 'text') else chunk["text"]
            c_meta = chunk.metadata if hasattr(chunk, 'metadata') else chunk["metadata"]
            
            vector = await self.embedding_service.embed_query(c_text)
            self.qdrant_service.upsert(c_text, vector, c_meta)
            
            if i % 5 == 0 or i == total_chunks - 1:
                progress = 0.05 + (0.25 * ((i + 1) / total_chunks)) # Max 30% for vector indexing
                yield {"step": "indexing", "message": f"Indexing chunk {i+1}/{total_chunks}...", "progress": progress}
                
        logger.debug(f"Upserted {total_chunks} chunks to Qdrant.")
        yield {"step": "indexing_complete", "message": "Vector indexing complete", "progress": 0.30}

        # 2. Knowledge Graph Construction
        chunk_size = 50000 
        text_blocks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
        total_blocks = len(text_blocks)
        
        for i, block in enumerate(text_blocks):
            yield {"step": "extraction", "message": f"Extracting entities from block {i+1}/{total_blocks} (this may take a while)...", "progress": 0.30 + (0.60 * (i / total_blocks))}
            
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
            
            # Update progress after block is done
            yield {"step": "extraction_block_done", "message": f"Finished block {i+1}/{total_blocks}", "progress": 0.30 + (0.60 * ((i + 1) / total_blocks))}

        logger.info("Document ingestion complete.")
        yield {"step": "complete", "message": "Ingestion complete!", "progress": 1.0}

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
