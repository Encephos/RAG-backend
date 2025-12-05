from typing import List, Dict, Any
from src.services.qdrant_service import QdrantService
from src.services.embedding_service import EmbeddingService
from src.services.kg_service import KnowledgeGraphService
from src.services.llm_service import LLMService
from src.models.schemas import SearchResult
from src.core.config import settings
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

    async def ingest_document(self, full_text: str, chunks: List[Any], target_collections: List[str] = None):
        """
        Legacy ingestion method. Consumes the generator.
        """
        async for _ in self.ingest_document_generator(full_text, chunks, target_collections):
            pass

    async def ingest_document_generator(self, full_text: str, chunks: List[Any], target_collections: List[str] = None):
        """
        Generator that yields progress updates during ingestion.
        Yields: Dict[str, Any] with keys 'step', 'message', 'progress'
        """
        logger.info(f"Starting document ingestion. Size: {len(full_text)} chars, Chunks: {len(chunks)}")
        
        # Ensure target_collections is a list and contains 'master'
        if not target_collections:
            target_collections = []
        
        # Normalize to lower case just in case
        target_collections = [t.lower() for t in target_collections]
        
        if "master" not in target_collections:
            target_collections.append("master")
            
        logger.info(f"Ingesting into collections: {target_collections}")
        
        yield {"step": "start", "message": "Starting ingestion...", "progress": 0.05}
        
        # 1. Vector Store (Document Chunks)
        total_chunks = len(chunks)
        for i, chunk in enumerate(chunks):
            # Handle both ChunkInfo objects and dicts
            c_text = chunk.text if hasattr(chunk, 'text') else chunk["text"]
            c_meta = chunk.metadata if hasattr(chunk, 'metadata') else chunk["metadata"]
            
            vector = await self.embedding_service.embed_query(c_text)
            
            # UPSERT to ALL selected collections
            for col in target_collections:
                self.qdrant_service.upsert(c_text, vector, c_meta, collection_alias=col)
            
            if i % 5 == 0 or i == total_chunks - 1:
                progress = 0.05 + (0.25 * ((i + 1) / total_chunks)) # Max 30% for vector indexing
                yield {"step": "indexing", "message": f"Indexing chunk {i+1}/{total_chunks}...", "progress": progress}
                
        logger.debug(f"Upserted {total_chunks} chunks to Qdrant collections: {target_collections}.")
        yield {"step": "indexing_complete", "message": "Vector indexing complete", "progress": 0.30}

        # 2. Knowledge Graph Construction
        chunk_size = 300000 # Increased to ~75k tokens per request
        text_blocks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
        total_blocks = len(text_blocks)
        
        for i, block in enumerate(text_blocks):
            yield {"step": "extraction", "message": f"Extracting entities from block {i+1}/{total_blocks} (this may take a while)...", "progress": 0.30 + (0.60 * (i / total_blocks))}
            
            extraction = await self.llm_service.extract_entities(block)
            logger.debug(f"Extracted {len(extraction.entities)} entities from block.")
            
            # Identify all target entity collections (Always Master + mapped from target_collections)
            # target_collections contains alias names like 'botanical', 'studies'
            # rag_entities (master) is automatic
            target_entity_collections = [settings.QDRANT_ENTITY_COLLECTION_NAME] # Master
            
            for col_alias in target_collections:
                if col_alias == "master": continue # Handled above
                # Map alias to entity collection name if it exists in QdrantService map
                mapped_entity_col = self.qdrant_service.entity_collections.get(col_alias)
                if mapped_entity_col:
                    target_entity_collections.append(mapped_entity_col)
            
            # Iterate through each collection and build the graph
            for graph_col in target_entity_collections:
                # Map entity names to their resolved IDs (Per Graph to avoid cross-sharing ID confusion if we want strict separation, 
                # though effectively reusing IDs across graphs is also fine.
                # However, add_entity_with_resolution checks existence. If we want separate graphs, we must resolve per graph.)
                entity_name_to_id = {}
                
                # Process Entities
                for entity in extraction.entities:
                    entity_id = await self.kg_service.add_entity_with_resolution(
                        name=entity.name,
                        type=entity.type,
                        description=entity.description,
                        collection_name=graph_col
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
                            relation_type=relation.type,
                            collection_name=graph_col
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

    async def ingest_cannabis_compounds_generator(self, file_path: str):
        """
        Ingest Cannabis Compounds from structured XML.
        Source: data/sources/compounds.xml
        Strategy: Direct KG mapping + Vector Summary
        Target Collections: 'pharmacological', 'master'
        Yields progress updates.
        Handles concatenated XML files by wrapping them in a pseudo-root.
        """
        import xml.etree.ElementTree as ET
        import math
        
        logger.info(f"Starting Cannabis Compound ingestion from {file_path}")
        yield {"step": "start", "message": "Starting XML parsing...", "progress": 0.0}
        
        target_data_collections = ["pharmacological", "master"]
        target_entity_collections = [
            self.qdrant_service.entity_collections["pharmacological"], 
            settings.QDRANT_ENTITY_COLLECTION_NAME
        ]
        
        # Generator to wrap the file content in a root element and strip XML declarations
        def xml_stream_wrapper(path):
            yield b"<compounds>"
            with open(path, "rb") as f:
                for line in f:
                    if line.strip().startswith(b"<?xml"):
                        continue
                    yield line
            yield b"</compounds>"
            
        # Helper to treat generator as file object for iterparse
        class StreamFile:
            def __init__(self, generator):
                self.gen = generator
                self.buf = b""
                
            def read(self, size):
                if len(self.buf) >= size:
                    chunk = self.buf[:size]
                    self.buf = self.buf[size:]
                    return chunk
                
                try:
                    while len(self.buf) < size:
                        self.buf += next(self.gen)
                except StopIteration:
                    pass
                    
                chunk = self.buf[:size]
                self.buf = self.buf[size:]
                return chunk

        total_compounds = 0
        
        # Initialize iterparse with our stream wrapper
        stream = StreamFile(xml_stream_wrapper(file_path))
        context = ET.iterparse(stream, events=("end",))
        
        yield {"step": "parsing", "message": "Parsing compounds...", "progress": 0.05}

        batch_size = 50
        
        for event, elem in context:
            if elem.tag == "compound":
                try:
                    # 1. Extract Data
                    name = elem.findtext("name", default="Unknown Compound")
                    description = elem.findtext("description", default="")
                    
                    # Taxonomy
                    taxonomy = elem.find("taxonomy")
                    direct_parent = taxonomy.findtext("direct_parent") if taxonomy is not None else "Chemical Compound"
                    kingdom = taxonomy.findtext("kingdom") if taxonomy is not None else "Organic compounds"
                    
                    # Properties (Just a few key ones)
                    formula = elem.findtext("chemical_formula", default="")
                    
                    # 2. Vector Store Document
                    # Create a rich text representation
                    doc_text = f"Compound: {name}\nClass: {direct_parent}\nFormula: {formula}\nDescription: {description}"
                    
                    vector = await self.embedding_service.embed_query(doc_text)
                    metadata = {
                        "source": "compounds.xml",
                        "type": "compound",
                        "name": name,
                        "class": direct_parent
                    }
                    
                    for col in target_data_collections:
                        self.qdrant_service.upsert(
                            text=doc_text,
                            vector=vector,
                            metadata=metadata,
                            collection_alias=col
                        )
                        
                    # 3. Knowledge Graph Construction
                    # Create entities and relations in BOTH graphs
                    for graph_col in target_entity_collections:
                        # Entity: Compound
                        compound_id = await self.kg_service.add_entity_with_resolution(
                            name=name,
                            type="Chemical Compound",
                            description=description[:500], # Trucate desc for KG
                            collection_name=graph_col
                        )
                        
                        # Entity: Class (Parent)
                        class_id = await self.kg_service.add_entity_with_resolution(
                            name=direct_parent,
                            type="Chemical Class",
                            description=f"Class of compounds belonging to {kingdom}",
                            collection_name=graph_col
                        )
                        
                        # Relation
                        self.kg_service.add_relation(
                            source_id=compound_id,
                            target_id=class_id,
                            relation_type="belongs_to",
                            collection_name=graph_col
                        )
                        
                    total_compounds += 1
                    if total_compounds % batch_size == 0:
                        yield {"step": "ingesting", "message": f"Ingested {total_compounds} compounds...", "progress": 0.1 + (0.01 * (total_compounds / 50))} # Fake progress increment
                        logger.info(f"Processed {total_compounds} compounds...")

                    # Clear element to save memory
                    elem.clear()

                except Exception as e:
                    logger.error(f"Error processing compound: {e}")
                    continue

        logger.info(f"Finished ingesting {total_compounds} compounds.")
        yield {"step": "complete", "message": f"Successfully ingested {total_compounds} compounds from XML.", "progress": 1.0}
