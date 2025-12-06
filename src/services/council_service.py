import logging
import asyncio
from typing import List, Dict, Any
from src.core.council_config import COUNCIL_MEMBERS
from src.services.llm_service import LLMService
from src.services.qdrant_service import QdrantService
from src.services.embedding_service import EmbeddingService
from src.models.schemas import CouncilMemberResult, SearchResult

logger = logging.getLogger(__name__)

class CouncilService:
    def __init__(self):
        self.llm_service = LLMService()
        self.qdrant_service = QdrantService()
        self.embedding_service = EmbeddingService()

    async def process_council_query(self, query: str, selected_member_ids: List[str]) -> Dict[str, Any]:
        logger.info(f"Processing Council Query with members: {selected_member_ids}")
        
        # 0. Validate Members
        active_members = []
        for mid in selected_member_ids:
            if mid in COUNCIL_MEMBERS:
                active_members.append(COUNCIL_MEMBERS[mid])
        
        if not active_members:
            raise ValueError("No valid council members selected.")

        # 1. Orchestration (Select Tasks)
        members_info = [
            {"id": m.id, "role": m.role, "description": m.description} 
            for m in active_members
        ]
        
        assignments = await self.llm_service.orchestrate_council(query, members_info)
        logger.info(f"Council Assignments: {assignments}")
        
        # 2. Parallel Execution (Experts)
        expert_results: List[CouncilMemberResult] = []
        
        async def process_expert(assignment):
            member_id = assignment["member_id"]
            task = assignment["task"]
            member_config = COUNCIL_MEMBERS[member_id]
            
            # Vector Search in specific collection
            query_vector = await self.embedding_service.embed_query(task)
            search_results = self.qdrant_service.search(
                vector=query_vector, 
                limit=3, 
                collection_alias=member_config.collection
            )
            
            context_text = "\n\n".join([r["text"] for r in search_results])
            
            # Generate Answer
            answer = await self.llm_service.generate_expert_answer(
                task=task,
                context=context_text,
                role=member_config.role,
                system_instruction=member_config.system_prompt
            )
            
            # Convert dict results to Pydantic models for response
            pydantic_context = [
                SearchResult(text=r["text"], score=r["score"], metadata=r["metadata"]) 
                for r in search_results
            ]
            
            # Graph Search (Simple Entity Lookup for now)
            # We search for entities matching the task in the same collection
            graph_nodes = self.qdrant_service.search_entities(
                vector=query_vector,
                limit=2,
                collection_name=member_config.collection.replace("_knowledge", "_entities").replace("_data", "_entities") if "collection" not in member_config.collection else settings.QDRANT_ENTITY_COLLECTION_NAME
            )
            
            graph_summary = ""
            if graph_nodes:
                 graph_summary = "Found entities: " + ", ".join([node.payload.get("name", "Unknown") for node in graph_nodes])

            return CouncilMemberResult(
                member_id=member_id,
                role=member_config.role,
                task=task,
                answer=answer,
                used_context=pydantic_context,
                graph_context={"summary": graph_summary, "nodes": []} if graph_summary else {}
            )

        # Run all experts in parallel
        tasks = [process_expert(assignment) for assignment in assignments]
        if tasks:
            expert_results = await asyncio.gather(*tasks)
            
        # 2.1 Backfill Unassigned Members
        assigned_ids = {a["member_id"] for a in assignments}
        
        for member in active_members:
            if member.id not in assigned_ids:
                expert_results.append(CouncilMemberResult(
                    member_id=member.id,
                    role=member.role,
                    task="Standby",
                    answer="No specific contribution required for this query.",
                    used_context=[]
                ))
            
        # 3. Master Context Retrieval (Global retrieval for Synthesizer)
        master_vector = await self.embedding_service.embed_query(query)
        master_results_dicts = self.qdrant_service.search(master_vector, limit=5, collection_alias="master")
        master_context_text = "\n\n".join([r["text"] for r in master_results_dicts])
        
        master_context_pydantic = [
            SearchResult(text=r["text"], score=r["score"], metadata=r["metadata"]) 
            for r in master_results_dicts
        ]

        # 4. Synthesis
        final_answer = await self.llm_service.synthesize_council_answer(
            query=query,
            master_context=master_context_text,
            member_results=[
                {"role": res.role, "task": res.task, "answer": res.answer}
                for res in expert_results
            ]
        )
        
        return {
            "answer": final_answer,
            "context": master_context_pydantic,
            "graph_context": {}, # Graph not fully integrated in council flow yet, could add if needed
            "council_results": expert_results
        }
