import pytest
from unittest.mock import MagicMock, patch
from src.services.llm_service import LLMService, Triple

class TestLLMService:
    
    @patch("src.services.llm_service.httpx.Client")
    def test_extract_entities_success(self, mock_client):
        """Test successful entity extraction."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '[{"subject": "Apple", "predicate": "founded_by", "object": "Steve Jobs", "confidence": 0.95}]'
                }
            }]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.return_value.__enter__.return_value.post.return_value = mock_response
        
        llm_service = LLMService()
        triples = llm_service.extract_entities("Apple was founded by Steve Jobs.")
        
        assert len(triples) == 1
        assert triples[0].subject == "Apple"
        assert triples[0].predicate == "founded_by"
        assert triples[0].object == "Steve Jobs"
        assert triples[0].confidence == 0.95

    @patch("src.services.llm_service.httpx.Client")
    def test_extract_entities_with_markdown_code_block(self, mock_client):
        """Test entity extraction when LLM returns markdown code block."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '```json\n[{"subject": "Google", "predicate": "located_in", "object": "Mountain View", "confidence": 0.9}]\n```'
                }
            }]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.return_value.__enter__.return_value.post.return_value = mock_response
        
        llm_service = LLMService()
        triples = llm_service.extract_entities("Google is located in Mountain View.")
        
        assert len(triples) == 1
        assert triples[0].subject == "Google"

    @patch("src.services.llm_service.httpx.Client")
    def test_extract_entities_empty_result(self, mock_client):
        """Test entity extraction with no entities found."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "[]"}
            }]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.return_value.__enter__.return_value.post.return_value = mock_response
        
        llm_service = LLMService()
        triples = llm_service.extract_entities("Hello world.")
        
        assert len(triples) == 0

    @patch("src.services.llm_service.httpx.Client")
    def test_generate_answer_success(self, mock_client):
        """Test successful answer generation."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "Apple is a technology company headquartered in Cupertino."}
            }]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.return_value.__enter__.return_value.post.return_value = mock_response
        
        llm_service = LLMService()
        answer = llm_service.generate_answer(
            query="What is Apple?",
            context="Apple is a technology company.",
            graph_context="Apple --[located_in]--> Cupertino"
        )
        
        assert "Apple" in answer
        assert "technology" in answer.lower() or "Cupertino" in answer

    @patch("src.services.llm_service.httpx.Client")
    def test_api_error_handling(self, mock_client):
        """Test error handling for API failures."""
        import httpx
        mock_client.return_value.__enter__.return_value.post.side_effect = httpx.HTTPError("API Error")
        
        llm_service = LLMService()
        triples = llm_service.extract_entities("Test text")
        
        assert triples == []


class TestTriple:
    def test_triple_to_dict(self):
        """Test Triple.to_dict() method."""
        triple = Triple("Apple", "founded_by", "Steve Jobs", 0.95)
        result = triple.to_dict()
        
        assert result["subject"] == "Apple"
        assert result["predicate"] == "founded_by"
        assert result["object"] == "Steve Jobs"
        assert result["confidence"] == 0.95
