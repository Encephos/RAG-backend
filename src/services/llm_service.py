from typing import List, Dict, Any, Optional
import httpx
import json
from src.core.config import settings

class Triple:
    def __init__(self, subject: str, predicate: str, obj: str, confidence: float = 1.0):
        self.subject = subject
        self.predicate = predicate
        self.object = obj
        self.confidence = confidence
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "confidence": self.confidence
        }

class LLMService:
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = settings.OPENROUTER_BASE_URL
        self.model = settings.LLM_MODEL
        
    def _call_llm(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> str:
        """Make a call to OpenRouter API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "RAG Backend"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    def extract_entities(self, text: str) -> List[Triple]:
        """Extract entities and relations from text using LLM."""
        system_prompt = """You are an entity and relation extractor. Extract semantic triples from the given text.
Output ONLY valid JSON array of objects with keys: subject, predicate, object, confidence.
- subject: the entity performing or being described
- predicate: the relationship or action (use snake_case like: works_for, located_in, is_a, founded_by, etc.)
- object: the target entity or value
- confidence: your confidence 0.0-1.0

Example output:
[
  {"subject": "Apple", "predicate": "founded_by", "object": "Steve Jobs", "confidence": 0.95},
  {"subject": "Apple", "predicate": "headquartered_in", "object": "Cupertino", "confidence": 0.90}
]

If no entities found, return empty array: []"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract triples from:\n\n{text}"}
        ]
        
        try:
            response = self._call_llm(messages, temperature=0.0)
            # Parse JSON from response
            # Handle potential markdown code blocks
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            triples_data = json.loads(response)
            return [
                Triple(
                    subject=t["subject"],
                    predicate=t["predicate"],
                    obj=t["object"],
                    confidence=t.get("confidence", 1.0)
                )
                for t in triples_data
            ]
        except (json.JSONDecodeError, KeyError, httpx.HTTPError) as e:
            print(f"Error extracting entities: {e}")
            return []
    
    def generate_answer(self, query: str, context: str, graph_context: str = "") -> str:
        """Generate an answer using the retrieved context."""
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
            return self._call_llm(messages, temperature=0.3)
        except httpx.HTTPError as e:
            return f"Error generating answer: {e}"
