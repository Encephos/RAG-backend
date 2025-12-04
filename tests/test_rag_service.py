import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from src.services.rag_service import RagService
from src.models.schemas import ExtractionResult, EntityNode, Relation

class TestRagService:
    
    @patch("src.services.rag_service.QdrantService")
    @patch("src.services.rag_service.EmbeddingService")
    @patch("src.services.rag_service.KnowledgeGraphService")
    @patch("src.services.rag_service.LLMService")
    async def test_ingest_flow(self, mock_llm, mock_kg, mock_emb, mock_qdrant):
        """Test the full ingestion flow including KG construction."""
        # Setup mocks
        service = RagService()
        
        # Mock Embedding
        mock_emb_instance = mock_emb.return_value
        mock_emb_instance.embed_query = AsyncMock(return_value=[0.1] * 384)
        service.embedding_service = mock_emb_instance
        
        # Mock LLM Extraction
        mock_llm_instance = mock_llm.return_value
        mock_extraction = ExtractionResult(
            entities=[
                EntityNode(name="Apple", type="Org", description="Tech Co"),
                EntityNode(name="Steve", type="Person", description="Founder")
            ],
            relations=[
                Relation(source="Apple", target="Steve", type="founded_by")
            ]
        )
        mock_llm_instance.extract_entities = AsyncMock(return_value=mock_extraction)
        service.llm_service = mock_llm_instance
        
        # Mock KG Resolution
        mock_kg_instance = mock_kg.return_value
        mock_kg_instance.add_entity_with_resolution = AsyncMock(side_effect=["id_apple", "id_steve"])
        service.kg_service = mock_kg_instance
        
        # Execute
        await service.ingest("Apple was founded by Steve.", {"source": "test"})
        
        # Verify
        service.qdrant_service.upsert.assert_called_once()
        service.llm_service.extract_entities.assert_called_once()
        assert service.kg_service.add_entity_with_resolution.call_count == 2
        service.kg_service.add_relation.assert_called_once_with(
            source_id="id_apple",
            target_id="id_steve",
            relation_type="founded_by"
        )

    @patch("src.services.rag_service.QdrantService")
    @patch("src.services.rag_service.EmbeddingService")
    @patch("src.services.rag_service.KnowledgeGraphService")
    @patch("src.services.rag_service.LLMService")
    async def test_query_flow(self, mock_llm, mock_kg, mock_emb, mock_qdrant):
        """Test the query flow with hybrid retrieval."""
        service = RagService()
        
        # Mock Embedding
        mock_emb_instance = mock_emb.return_value
        mock_emb_instance.embed_query = AsyncMock(return_value=[0.1] * 384)
        service.embedding_service = mock_emb_instance
        
        # Mock Vector Search
        service.qdrant_service.search.return_value = [
            {"text": "Chunk 1", "score": 0.9}
        ]
        
        # Mock Graph Retrieval
        mock_kg_instance = mock_kg.return_value
        mock_kg_instance.get_graph_context = AsyncMock(return_value="Graph Context")
        service.kg_service = mock_kg_instance
        
        # Mock LLM Generation
        mock_llm_instance = mock_llm.return_value
        mock_llm_instance.generate_answer = AsyncMock(return_value="Final Answer")
        service.llm_service = mock_llm_instance
        
        # Execute
        result = await service.query("Question")
        
        # Verify
        assert result["answer"] == "Final Answer"
        assert result["graph_context"]["summary"] == "Graph Context"
        
        service.qdrant_service.search.assert_called_once()
        service.kg_service.get_graph_context.assert_called_once()
        service.llm_service.generate_answer.assert_called_once()
