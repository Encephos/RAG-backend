import asyncio
import logging
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.append(os.getcwd())

from src.services.rag_service import RagService
from src.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Initializing RagService...")
    # Mocking QdrantService to avoid connection errors
    with unittest.mock.patch('src.services.qdrant_service.QdrantService') as text_qdrant_mock:
         rag_service = RagService()
         
         # Mock search results (50 documents)
         mock_docs = []
         for i in range(50):
             mock_docs.append({
                 "text": f"This is document number {i}. Pinene is a terpene found in pine trees and cannabis. It has anti-inflammatory properties.", 
                 "metadata": {"id": i}
             })
             
         # The reranker will score these. Let's make one strictly irrelevant to see if it drops.
         mock_docs[49] = {"text": "This is a document about cars and engines. Unrelated to biology.", "metadata": {"id": 49}}
         
         rag_service.qdrant_service.search = MagicMock(return_value=mock_docs)
         rag_service.kg_service.get_graph_context = AsyncMock(return_value="Graph Context")
         rag_service.llm_service.generate_answer = AsyncMock(return_value="Answer")
         
         query = "What are the effects of Pinene?"
         logger.info(f"Running query: '{query}'")
         
         # Run query
         result = await rag_service.query(query)
         
         context = result["context"]
         logger.info(f"Final context count: {len(context)}")
         
         if len(context) == settings.FINAL_K:
             logger.info(f"SUCCESS: Retrieved exactly {settings.FINAL_K} context items after reranking.")
         else:
             logger.error(f"FAILURE: Expected {settings.FINAL_K} items, got {len(context)}")
             
         # Check if the unrelated doc is likely at the bottom or removed (since we only keep top 15)
         ids = [c["metadata"]["id"] for c in context]
         if 49 in ids:
             logger.warning("Unrelated document (id: 49) was still in top 15. Reranker might be weak or queries too similar.")
         else:
             logger.info("Unrelated document correctly filtered out.")

import unittest.mock

if __name__ == "__main__":
    asyncio.run(main())
