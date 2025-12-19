
import asyncio
import logging
from src.services.llm_service import LLMService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Initializing LLMService...")
    service = LLMService()
    
    # Test 1: Extract Entities
    text = "Oskar lebt in Berlin und arbeitet an einem RAG System."
    logger.info(f"\n--- Testing Extract Entities ---\nInput: {text}")
    try:
        result = await service.extract_entities(text)
        logger.info(f"Result (Type: {type(result)}):")
        print(result)
        # Verify it's the correct Pydantic model
        assert isinstance(result.entities, list)
        assert len(result.entities) > 0
        logger.info("✅ Extract Entities Passed")
    except Exception as e:
        logger.error(f"❌ Extract Entities Failed: {e}")

    # Test 2: Orchestrate Council
    query = "Wie wirkt sich THC auf das Gedächtnis aus?"
    members = [
        {"id": "botanist", "role": "Botaniker", "description": "Experte für Pflanzenbiologie und Genetik."},
        {"id": "neurologist", "role": "Neurologe", "description": "Experte für das Gehirn und Nervensystem."}
    ]
    logger.info(f"\n--- Testing Orchestrate Council ---\nQuery: {query}")
    try:
        assignments = await service.orchestrate_council(query, members)
        logger.info(f"Assignments (Type: {type(assignments)}):")
        print(assignments)
        assert isinstance(assignments, list)
        if len(assignments) > 0:
             logger.info("✅ Orchestrate Council Passed")
        else:
             logger.warning("⚠️ Orchestrate Council returned empty list (might be valid depending on LLM)")
    except Exception as e:
        logger.error(f"❌ Orchestrate Council Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
