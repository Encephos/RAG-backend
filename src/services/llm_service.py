from typing import List, Dict, Any, Optional
import httpx
import json
from src.core.config import settings
from pydantic import BaseModel, Field
from src.models.schemas import EntityNode, Relation, ExtractionResult
import logging
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# LangChain Imports
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated, Optional, Any
import operator

# Internal Imports
from src.services.qdrant_service import QdrantService

logger = logging.getLogger(__name__)

# Helper models for Council Orchestration (Internal)
class Assignment(BaseModel):
    member_id: str = Field(description="The ID of the council member expert.")
    task: str = Field(description="The specific task assigned to this member in German.")

class CouncilAssignments(BaseModel):
    assignments: List[Assignment]

class CouncilState(TypedDict):
    query: str
    members_info: List[Dict]
    assignments: List[Assignment]
    # Use operator.add to accumulate expert results from parallel branches
    expert_results: Annotated[List[Dict[str, Any]], operator.add] 
    final_answer: str

class LLMService:
    """
    Service for interacting with Large Language Models via OpenRouter using LangChain.
    Handles entity extraction and answer generation.
    """
    def __init__(self, qdrant_service: Optional[QdrantService] = None):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = settings.OPENROUTER_BASE_URL
        self.model = settings.LLM_MODEL
        
        # Optional Qdrant Service for RAG
        self.qdrant_service = qdrant_service
        
        # Initialize LangChain Chat Model
        self.llm = ChatOpenAI(
            model=self.model,
            openai_api_key=self.api_key,
            openai_api_base=f"{self.base_url}",
            default_headers={
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "RAG Backend"
            },
            temperature=0,
            max_retries=2
        )
        
        # Initialize Embedding Model for Retrieval
        # Configuration for OpenRouter Embeddings
        try:
             # We use the OpenRouter Base URL and Key
             # Model name usually needs provider prefix for OpenRouter e.g. "openai/text-embedding-3-small"
             embedding_model = "openai/text-embedding-3-small" 
             
             self.embeddings = OpenAIEmbeddings(
                 model=embedding_model,
                 openai_api_key=settings.OPENAI_API_KEY or self.api_key,
                 openai_api_base=self.base_url, # Key fix: Point to OpenRouter
                 check_embedding_ctx_length=False # Disable check as it might fail on non-standard providers
             )
        except Exception as e:
            logger.warning(f"Failed to intialize Embeddings: {e}")
            self.embeddings = None

    def _get_collection_for_role(self, role: str) -> str:
        """Map expert role to specific Qdrant collection."""
        role_lower = role.lower()
        if any(x in role_lower for x in ["botan", "plant", "pflanze", "geneti"]):
            return "botanical"
        elif any(x in role_lower for x in ["pharma", "neuro", "medic", "arznei", "wirkug"]):
            return "pharmacological" 
        elif any(x in role_lower for x in ["prod", "grow", "anbau", "gärtner", "soil", "boden"]):
            return "production"
        elif "stud" in role_lower:
            return "studies"
        else:
            return "master"
        
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
        
        # Handle list content (multimodal) for logging safety
        if isinstance(user_content, list):
             text_parts = [item["text"] for item in user_content if item.get("type") == "text"]
             approx_input_tokens = sum(len(t) for t in text_parts) // 4
        else:
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

    async def analyze_image(self, image_base64: str, prompt: str = "Beschreibe visuelle Anomalien.") -> str:
        """
        Send an image to Gemini 2.5 Flash for analysis.
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ]
        return await self._call_llm(messages, temperature=0.2, response_format=None)

    async def extract_entities(self, text: str) -> ExtractionResult:
        """
        Extract entities (with descriptions) and relations from text using LangChain Structured Output.
        """
        system_prompt = """You are an expert Knowledge Graph builder. Extract entities and relations from the text.
        
        1. Identify key entities (Person, Organization, Concept, Strain, etc.).
        2. Identify relationships between them.
        3. Be precise and concise.
        """
        
        # Define the structured LLM
        structured_llm = self.llm.with_structured_output(ExtractionResult)
        
        try:
            logger.info(f"🔵 Extracting entities via LangChain | Text len: {len(text)}")
            result = await structured_llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Extract from:\n\n{text}")
            ])
            return result
            
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            # Return empty result on failure
            return ExtractionResult(entities=[], relations=[])
    
    async def generate_answer(self, query: str, context: str, graph_context: str = "") -> str:
        """
        Generate an answer using the retrieved context.
        """
        system_prompt = """You are a helpful assistant that answers questions based on the provided context.
        
        Instructions:
        1. Use ONLY the information from the context to answer. If the context doesn't contain the answer, say so.
        2. Format your answer using Markdown (e.g., use **bold** for key terms, lists for steps, > for quotes, and headers where appropriate).
        3. Be concise but DETAILED and COMPREHENSIVE. Explain concepts thoroughly.
        4. Do NOT output JSON. Output normal text formatted with Markdown.
        5. IMPORTANT: You must ALWAYS answer in GERMAN (Deutsch), regardless of the input language.
        """

        user_content = f"""Context from documents:
{context}

Knowledge graph context:
{graph_context if graph_context else "No graph context available."}

Question: {query}

Answer based on the above context (in German, detailed):"""

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

    async def orchestrate_council(self, query: str, members_info: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Orchestrate the council by assigning tasks to selected members based on the user's query.
        """
        members_desc = "\n".join([f"- ID: {m['id']} | Role: {m['role']} | Description: {m['description']}" for m in members_info])
        
        system_prompt = f"""You are the Orchestrator of the Nexus Council. 
        Your goal is to break down a user's request into specific sub-tasks for the available experts.
        
        Available Experts:
        {members_desc}
        
        1. Analyze the user's query.
        2. Assign a specific task to EACH relevant expert.
        3. The 'task' description must be in GERMAN, detailed, and specific.
        4. If an expert is not needed, do not assign a task.
        """
        
        structured_llm = self.llm.with_structured_output(CouncilAssignments)
        
        try:
            logger.info(f"🔵 Orchestrating Council via LangChain")
            result = await structured_llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"User Query: {query}")
            ])
            
            # Convert Pydantic assignments back to list of dicts
            valid_assignments = []
            valid_ids = {m['id'] for m in members_info}
            
            if result and result.assignments:
                for req in result.assignments:
                    if req.member_id in valid_ids and req.task:
                         valid_assignments.append({"member_id": req.member_id, "task": req.task})
                    
            return valid_assignments
            
        except Exception as e:
            logger.error(f"Error orchestrating council: {e}")
            return []

    async def generate_expert_answer(self, task: str, context: str, role: str, system_instruction: str) -> str:
        """
        Generate an answer from a specific expert persona.
        """
        system_prompt = f"""You are a {role}.
        {system_instruction}
        
        Instructions:
        1. Answer the assigned task based ONLY on the provided context.
        2. If context is insufficient, state what is known and what is missing based on your expertise.
        3. Provide a DETAILED, SCIENTIFIC, and COMPREHENSIVE answer.
        4. Do NOT output JSON. Output Markdown text.
        5. IMPORTANT: You must ALWAYS answer in GERMAN (Deutsch).
        """
        
        user_content = f"""Context:
        {context}
        
        Task: {task}
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        try:
            return await self._call_llm(messages, temperature=0.3, response_format=None)
        except Exception as e:
            logger.error(f"Error generating expert answer ({role}): {e}")
            return "Unable to generate answer due to an internal error."

    async def synthesize_council_answer(self, query: str, master_context: str, member_results: List[Dict[str, Any]]) -> str:
        """
        Synthesize the final answer from the Council Master (Synthesizer).
        """
        
        # Format member contributions
        contributions = ""
        for res in member_results:
            contributions += f"""
            ### Report from {res.get('role', 'Expert')}:
            **Task**: {res.get('task', 'N/A')}
            **Findings**:
            {res.get('answer', 'No answer provided')}
            ---
            """
            
        system_prompt = """You are the Head of the Nexus Council.
        Your goal is to synthesize a comprehensive answer to the user's query by integrating reports from your panel of experts and your own master knowledge.
        
        Instructions:
        1. Answer the User Query comprehensively and in great detail.
        2. Integrate insights from the Expert Reports. Explicitly cite the experts (e.g., "Wie unser Botaniker anmerkte...", "Der Toxikologe warnt...").
        3. Use the Master Context to fill in gaps or provide general overview.
        4. Structure the answer logically with Markdown (Headers, Bullet points).
        5. Tone: Authoritative, balanced, and scientifically grounded.
        6. IMPORTANT: You must ALWAYS answer in GERMAN (Deutsch).
        """
        
        user_content = f"""User Query: {query}
        
        Master Context (General Knowledge):
        {master_context}
        
        Expert Council Reports:
        {contributions}
        
        Please provide the final synthesized response in German (Detailed).
        """
        
        try:
             result = await self.llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_content)
             ])
             return result.content
        except Exception as e:
            logger.error(f"Error synthesizing answer: {e}")
            return "Error synthesizing final council response."
            
    # --- LangGraph Implementation ---
    
    async def run_council_flow(self, query: str, members_info: List[Dict[str, str]], master_context: str = "") -> str:
        """
        Run the full Council Orchestration using LangGraph.
        Orchestrator -> Parallel Experts -> Synthesizer
        """
        from langgraph.types import Send
        
        # 1. Define Nodes
        
        async def orchestrator_node(state: CouncilState):
            assignments_list = await self.orchestrate_council(state['query'], state['members_info'])
            # Convert dicts back to Assignment objects for internal consistency or just use lists
            # The verify script showed orchestrate_council returns List[Dict]. 
            # We map them to Assignment objects manually if needed, or just store as is.
            # State expects List[Assignment]. 
            
            assignments = []
            for a in assignments_list:
                assignments.append(Assignment(member_id=a['member_id'], task=a['task']))
            
            return {"assignments": assignments}

        async def expert_node(state: dict):
            # State here is passed via Send, so it's just the assignment payload
            member_id = state['member_id']
            task = state['task']
            role = state.get('role', 'Expert')
            
            context = "No specific context retrieved."
            
            # --- RAG RETRIEVAL ---
            if self.qdrant_service and self.embeddings:
                try:
                    # 1. Determine collection
                    collection_alias = self._get_collection_for_role(role)
                    
                    # 2. Embed the task/query
                    # Using the specific task as the query for retrieval is usually better than the generic user query
                    query_vector = await self.embeddings.aembed_query(task)
                    
                    # 3. Search Qdrant
                    search_results = self.qdrant_service.search(
                        vector=query_vector, 
                        limit=3, 
                        collection_alias=collection_alias
                    )
                    
                    # 4. Format Context
                    if search_results:
                        context = "\n\n".join([f"- {res['text']}" for res in search_results])
                        logger.info(f"✅ RAG Retrieval Success | Role: {role} | Collection: {collection_alias} | Docs: {len(search_results)}")
                    else:
                        logger.info(f"⚠️ RAG Retrieval Empty | Role: {role} | Collection: {collection_alias}")

                except Exception as e:
                    logger.error(f"❌ RAG Retrieval Failed for {role}: {e}")
                    context = f"Error retrieving context: {e}"
            else:
                if not self.qdrant_service:
                    logger.warning("QdrantService not available for expert node.")
                if not self.embeddings:
                    logger.warning("Embeddings not initialized for expert node.")

            system_instr = f"Act as a {role}. Base your answer on the provided Context."
            
            answer = await self.generate_expert_answer(task, context, role, system_instr)
            
            return {"expert_results": [{
                "member_id": member_id, 
                "role": role, 
                "task": task, 
                "answer": answer
            }]}

        async def synthesizer_node(state: CouncilState):
            final_ans = await self.synthesize_council_answer(
                state['query'], 
                master_context, 
                state['expert_results']
            )
            return {"final_answer": final_ans}

        # 2. Define Routing Logic
        def route_to_experts(state: CouncilState):
            assignments = state['assignments']
            if not assignments:
                return "synthesizer"
                
            tasks = []
            members_map = {m['id']: m for m in state['members_info']}
            
            for assignment in assignments:
                m_info = members_map.get(assignment.member_id, {})
                tasks.append(Send("expert", {
                    "member_id": assignment.member_id,
                    "task": assignment.task,
                    "role": m_info.get('role', 'Expert')
                }))
            return tasks

        # 3. Build Graph
        workflow = StateGraph(CouncilState)
        
        workflow.add_node("orchestrator", orchestrator_node)
        workflow.add_node("expert", expert_node)
        workflow.add_node("synthesizer", synthesizer_node)
        
        workflow.add_edge(START, "orchestrator")
        workflow.add_conditional_edges("orchestrator", route_to_experts, ["expert", "synthesizer"])
        workflow.add_edge("expert", "synthesizer")
        workflow.add_edge("synthesizer", END)
        
        app = workflow.compile()
        
        # 4. Run
        final_state = await app.ainvoke({
            "query": query,
            "members_info": members_info,
            "assignments": [],
            "expert_results": [],
            "final_answer": ""
        })
        
        return final_state["final_answer"]
