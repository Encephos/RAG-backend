from typing import List, Dict, Any, Optional
import httpx
import json
from src.core.config import settings
from pydantic import BaseModel
from src.models.schemas import EntityNode, Relation, ExtractionResult
import logging
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

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
        
    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(10),
        retry=retry_if_exception_type(httpx.HTTPStatusError)
    )
    async def _call_llm(self, messages: List[Dict[str, str]], temperature: float = 0.0, response_format: Optional[Dict[str, str]] = {"type": "json_object"}) -> str:
        """
        Make an asynchronous call to OpenRouter API.
        
        Args:
            messages: List of message dictionaries (role, content).
            temperature: Sampling temperature.
            response_format: The format of the response (e.g. {"type": "json_object"} or None for text).
            
        Returns:
            The content of the LLM response.
            
        Raises:
            httpx.HTTPError: If the API call fails.
        """
        # Calculate approximate token count for logging
        user_content = next((m["content"] for m in messages if m["role"] == "user"), "")
        approx_input_tokens = len(user_content) // 4  # Rough estimate: 1 token ≈ 4 chars
        
        logger.info(f"🔵 LLM Request | Model: {self.model} | Approx Input Tokens: {approx_input_tokens}")
        
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
        }
        
        if response_format:
            payload["response_format"] = response_format
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            if response.is_error:
                logger.error(f"LLM API Error Status: {response.status_code}")
                logger.error(f"LLM API Error Body: {response.text}")
            
            response.raise_for_status()
            data = response.json()
            
            # Log usage statistics if available
            usage = data.get("usage", {})
            if usage:
                logger.info(f"✅ LLM Response | Input: {usage.get('prompt_tokens', 'N/A')} tokens | "
                           f"Output: {usage.get('completion_tokens', 'N/A')} tokens | "
                           f"Total: {usage.get('total_tokens', 'N/A')} tokens")
            
            return data["choices"][0]["message"]["content"]

    async def extract_entities(self, text: str) -> ExtractionResult:
        """
        Extract entities (with descriptions) and relations from text using LLM.
        
        Args:
            text: The input text to analyze.
            
        Returns:
            ExtractionResult containing entities and relations.
        """
        system_prompt = """You are an expert Knowledge Graph builder. Extract entities and relations from the text.
        
        STRICTLY return a valid JSON object with two keys: "entities" and "relations".
        Do NOT wrap the JSON in markdown code blocks. Return raw JSON only.
        
        1. "entities": List of objects with:
           - "name": Canonical name of the entity
           - "type": Type (Person, Organization, Location, Concept, etc.)
           - "description": A concise (max 10 words) summary.
           
        2. "relations": List of objects with:
           - "source": Name of source entity
           - "target": Name of target entity
           - "type": Relationship type (snake_case)
           
        Ensure the JSON is valid and complete.
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract from:\n\n{text}"}
        ]
        
        try:
            # Explicitly request JSON format
            response = await self._call_llm(messages, temperature=0.0, response_format={"type": "json_object"})
            
            # Robust JSON extraction
            import re
            # Find the first '{' and the last '}'
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                json_str = match.group(0)
            else:
                json_str = response
            
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                # Fallback: try to clean markdown code blocks if regex failed or wasn't enough
                clean_response = response.strip()
                if clean_response.startswith("```"):
                    clean_response = clean_response.split("```")[1]
                    if clean_response.strip().lower().startswith("json"):
                        clean_response = clean_response.strip()[4:]
                data = json.loads(clean_response)
            
            # Validate and clean relations before Pydantic validation
            if "relations" in data:
                valid_relations = []
                for rel in data["relations"]:
                    # Check if all required fields are present
                    if isinstance(rel, dict) and "source" in rel and "target" in rel and "type" in rel:
                        valid_relations.append(rel)
                    else:
                        logger.warning(f"Skipping malformed relation: {rel}")
                data["relations"] = valid_relations
            
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
        
        Instructions:
        1. Use ONLY the information from the context to answer. If the context doesn't contain the answer, say so.
        2. Format your answer using Markdown (e.g., use **bold** for key terms, lists for steps, > for quotes, and headers where appropriate).
        3. Be concise, accurate, and structured.
        4. Do NOT output JSON. Output normal text formatted with Markdown.
        5. IMPORTANT: Always answer in the same language as the user's question (e.g., if asked in German, answer in German; if English, answer in English).
        """

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
            # Request None (text) format for normal chat answer
            return await self._call_llm(messages, temperature=0.3, response_format=None)
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return f"Error generating answer: {e}"
