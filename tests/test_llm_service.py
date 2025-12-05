import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import json # Added for json.dumps
from src.services.llm_service import LLMService, EntityNode, Relation, ExtractionResult

class TestLLMService:
    
    @patch("src.services.llm_service.httpx.AsyncClient")
    async def test_extract_entities_success(self, mock_client_class):
        """Test successful entity extraction."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "entities": [{"name": "Apple", "type": "Org", "description": "Tech Co"}],
                        "relations": []
                    })
                }
            }]
        }
        
        # Setup AsyncClient mock context manager
        mock_client_instance = MagicMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client_instance
        
        service = LLMService()
        result = await service.extract_entities("Apple is a tech company.")
        
        assert len(result.entities) == 1
        assert result.entities[0].name == "Apple"

    @patch("src.services.llm_service.httpx.AsyncClient")
    async def test_generate_answer_success(self, mock_client_class):
        """Test successful answer generation."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "The answer is 42."}}]
        }
        
        mock_client_instance = MagicMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client_instance
        
        service = LLMService()
        answer = await service.generate_answer("Question", "Context")
        
        assert answer == "The answer is 42."
    @patch("src.services.llm_service.LLMService._call_llm")
    async def test_orchestrate_council_success(self, mock_call_llm):
        """Test successful council orchestration."""
        mock_call_llm.return_value = json.dumps({
            "assignments": [
                {"member_id": "botanist", "task": "Task 1"},
                {"member_id": "unknown", "task": "Task 2"}
            ]
        })
        
        service = LLMService()
        members = [{"id": "botanist", "role": "Botanist", "description": "Plants"}]
        result = await service.orchestrate_council("Query", members)
        
        # Should filter out 'unknown' member
        assert len(result) == 1
        assert result[0]["member_id"] == "botanist"
        assert result[0]["task"] == "Task 1"

    @patch("src.services.llm_service.LLMService._call_llm")
    async def test_generate_expert_answer(self, mock_call_llm):
        mock_call_llm.return_value = "Expert Answer"
        service = LLMService()
        answer = await service.generate_expert_answer("Task", "Context", "Role", "Prompt")
        assert answer == "Expert Answer"

    @patch("src.services.llm_service.LLMService._call_llm")
    async def test_synthesize_council_answer(self, mock_call_llm):
        mock_call_llm.return_value = "Final Synthesis"
        service = LLMService()
        answer = await service.synthesize_council_answer("Query", "Master Context", [{"role": "R", "task": "T", "answer": "A"}])
        assert answer == "Final Synthesis"
