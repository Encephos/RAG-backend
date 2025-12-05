import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.council_service import CouncilService
from src.models.schemas import SearchResult, CouncilMemberResult
from src.core.council_config import COUNCIL_MEMBERS

@pytest.fixture
def mock_llm_service():
    return AsyncMock()

@pytest.fixture
def mock_qdrant_service():
    return MagicMock()

@pytest.fixture
def mock_embedding_service():
    mock = AsyncMock()
    mock.embed_query.return_value = [0.1, 0.2, 0.3]
    return mock

@pytest.fixture
def council_service(mock_llm_service, mock_qdrant_service, mock_embedding_service):
    with patch("src.services.council_service.LLMService", return_value=mock_llm_service), \
         patch("src.services.council_service.QdrantService", return_value=mock_qdrant_service), \
         patch("src.services.council_service.EmbeddingService", return_value=mock_embedding_service):
        service = CouncilService()
        return service

@pytest.mark.asyncio
async def test_process_council_query_success(council_service):
    # Setup Mocks
    council_service.llm_service.orchestrate_council.return_value = [
        {"member_id": "botanist", "task": "Task 1"}
    ]
    
    council_service.qdrant_service.search.side_effect = [
        # First call: Expert search (botanical)
        [{"text": "Plant info", "score": 0.9, "metadata": {}}],
        # Second call: Master search
        [{"text": "Master info", "score": 0.8, "metadata": {}}]
    ]
    
    council_service.llm_service.generate_expert_answer.return_value = "Expert Answer"
    council_service.llm_service.synthesize_council_answer.return_value = "Final Answer"

    # Execute
    result = await council_service.process_council_query("query", ["botanist"])

    # Assertions
    assert result["answer"] == "Final Answer"
    assert len(result["council_results"]) == 1
    assert result["council_results"][0].member_id == "botanist"
    assert result["council_results"][0].answer == "Expert Answer"
    
    # Verify method calls
    council_service.llm_service.orchestrate_council.assert_called_once()
    council_service.qdrant_service.search.assert_any_call(
        vector=[0.1, 0.2, 0.3], 
        limit=3, 
        collection_alias="botanical_knowledge"
    )

@pytest.mark.asyncio
async def test_process_council_query_no_members(council_service):
    with pytest.raises(ValueError):
        await council_service.process_council_query("query", [])

@pytest.mark.asyncio
async def test_process_council_query_invalid_member(council_service):
    with pytest.raises(ValueError):
        await council_service.process_council_query("query", ["invalid_id"])
