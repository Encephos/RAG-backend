
import asyncio
import logging
from src.services.llm_service import LLMService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Initializing Dependencies...")
    # Inject QdrantService (Mock or Real)
    from src.services.qdrant_service import QdrantService
    qdrant = QdrantService()
    
    logger.info("Initializing LLMService with Qdrant...")
    service = LLMService(qdrant_service=qdrant)
    
    query = "Wie gehe ich am besten vor beim Anbau von Cannabis auf Erde?"
    members = [
        {"id": "botanist", "role": "Botaniker", "description": "Experte für Pflanzenbiologie und Anbaumethoden."},
        {"id": "soil_expert", "role": "Bodenkundler", "description": "Experte für Substrate und Düngung."}
    ]
    
    logger.info(f"\n--- Testing Council Graph ---\nQuery: {query}")
    try:
        final_answer = await service.run_council_flow(query, members)
        logger.info("\n✅ Final Council Answer:\n")
        print(final_answer)
    except Exception as e:
        logger.error(f"❌ Council Graph Failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
