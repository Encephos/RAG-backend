from typing import List, Dict, Any, Optional
import httpx
import json
from src.core.config import settings
from pydantic import BaseModel
from src.models.schemas import EntityNode, Relation, ExtractionResult
import logging

logger = logging.getLogger(__name__)

class LLMService:
    """
    Service for interacting with Large Language Models via OpenRouter.
    Handles entity extraction and answer generation.
    """
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = settings.OPENROUTER_BASE_URL
        self.model = settings.LLM_MODEL
        
    async def _call_llm(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> str:
        """
        Make an asynchronous call to OpenRouter API.
        
        Args:
            messages: List of message dictionaries (role, content).
            temperature: Sampling temperature.
            
        Returns:
            The content of the LLM response.
            
        Raises:
            httpx.HTTPError: If the API call fails.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "RAG Backend"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"} # Force JSON mode if supported
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except httpx.HTTPError as e:
            logger.error(f"LLM API Error: {e}")
            raise

    async def extract_entities(self, text: str) -> ExtractionResult:
        """
        Extract entities (with descriptions) and relations from text using LLM.
        
        Args:
            text: The input text to analyze.
            
        Returns:
            ExtractionResult containing entities and relations.
        """
        system_prompt = """You are an expert Knowledge Graph builder. Extract entities and relations from the text.
        
        Return a JSON object with two keys: "entities" and "relations".
        
        1. "entities": List of objects with:
           - "name": Canonical name of the entity
           - "type": Type (Person, Organization, Location, Concept, etc.)
           - "description": A short, descriptive summary of what this entity is based on the text (crucial for semantic search).
           
        2. "relations": List of objects with:
           - "source": Name of source entity
           - "target": Name of target entity
           - "type": Relationship type (snake_case, e.g., founded_by, located_in)
           
        Example:
        {
          "entities": [
            {"name": "Apple", "type": "Organization", "description": "Technology company known for iPhone."},
            {"name": "Steve Jobs", "type": "Person", "description": "Co-founder of Apple."}
          ],
          "relations": [
            {"source": "Apple", "target": "Steve Jobs", "type": "founded_by"}
          ]
        }
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract from:\n\n{text}"}
        ]
        
        try:
            response = await self._call_llm(messages, temperature=0.0)
            
            # Clean response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            data = json.loads(response)
            return ExtractionResult(**data)
            
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return ExtractionResult(entities=[], relations=[])
    
    async def generate_answer(self, query: str, context: str, graph_context: str = "") -> str:
        """
        Generate an answer using the retrieved context.
        
        Args:
            query: The user's question.
            context: Retrieved document chunks.
            graph_context: Retrieved graph information.
            
        Returns:
            The generated answer string.
        """
        system_prompt = """You are a helpful assistant that answers questions based on the provided context.
Use ONLY the information from the context to answer. If the context doesn't contain the answer, say so.
Be concise and accurate."""

        user_content = f"""Context from documents:
{context}

Knowledge graph context:
{graph_context if graph_context else "No graph context available."}

Question: {query}

Answer based on the above context:"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        try:
            return await self._call_llm(messages, temperature=0.3)
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return f"Error generating answer: {e}"
