from typing import List, Dict, Any
from sentence_transformers import CrossEncoder
from src.core.config import settings
import logging

logger = logging.getLogger(__name__)

class RerankService:
    """
    Service for reranking retrieved documents using a Cross-Encoder model.
    Improves relevance by scoring query-document pairs.
    """
    def __init__(self):
        try:
            logger.info(f"Loading Reranker model: {settings.RERANKER_MODEL_NAME}")
            self.model = CrossEncoder(settings.RERANKER_MODEL_NAME)
        except Exception as e:
            logger.error(f"Failed to load Reranker model: {e}")
            raise

    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Rerank a list of documents based on their relevance to the query.
        
        Args:
            query: The user query.
            documents: List of document dictionaries (must contain 'text').
            top_k: Number of top results to return.
            
        Returns:
            List of the top_k most relevant documents.
        """
        if not documents:
            return []
            
        # Prepare pairs for scoring: (query, document_text)
        pairs = []
        for doc in documents:
            text = doc.get("text", "")
            pairs.append([query, text])
            
        # Predict scores
        scores = self.model.predict(pairs)
        
        # Combine docs with scores
        doc_scores = []
        for i, doc in enumerate(documents):
            doc_scores.append({"doc": doc, "score": scores[i]})
            
        # Sort by score descending
        doc_scores.sort(key=lambda x: x["score"], reverse=True)
        
        # Select top k
        top_results = [item["doc"] for item in doc_scores[:top_k]]
        
        logger.info(f"Reranked {len(documents)} documents to top {len(top_results)}")
        return top_results
