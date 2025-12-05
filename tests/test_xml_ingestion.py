
import pytest
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.rag_service import RagService

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<compounds>
    <compound>
        <name>Tetrahydrocannabinol</name>
        <description>The principal psychoactive constituent of cannabis.</description>
        <chemical_formula>C21H30O2</chemical_formula>
        <taxonomy>
            <direct_parent>Cannabinoids</direct_parent>
            <kingdom>Organic compounds</kingdom>
        </taxonomy>
    </compound>
    <compound>
        <name>Cannabidiol</name>
        <description>A phytocannabinoid discovered in 1940.</description>
        <chemical_formula>C21H30O2</chemical_formula>
        <taxonomy>
            <direct_parent>Cannabinoids</direct_parent>
            <kingdom>Organic compounds</kingdom>
        </taxonomy>
    </compound>
</compounds>
"""

@pytest.mark.asyncio
async def test_ingest_cannabis_compounds_generator():
    # Setup temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as tmp:
        tmp.write(SAMPLE_XML)
        tmp_path = tmp.name

    try:
        # Mock dependencies in RagService
        service = RagService()
        service.embedding_service.embed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
        service.qdrant_service.upsert = MagicMock()
        service.kg_service.add_entity_with_resolution = AsyncMock(return_value="mock_id")
        service.kg_service.add_relation = MagicMock()
        
        # Mock Qdrant Entity Collections Map
        service.qdrant_service.entity_collections = {"pharmacological": "pharm_entities"}
        
        # Run Generator
        events = []
        async for event in service.ingest_cannabis_compounds_generator(tmp_path):
            events.append(event)
            
        # Verify Flow
        assert len(events) > 0
        assert events[0]["step"] == "start"
        assert events[-1]["step"] == "complete"
        
        # Verify Qdrant Upserts (2 compounds * 2 collections = 4 calls)
        assert service.qdrant_service.upsert.call_count == 4
        
        # Verify KG Upserts (2 compounds * 2 graphs = 4 cycles of entity/relation creation)
        # Each compound triggers: 2 entity creations (Compound + Parent) + 1 relation
        # Total per compound per graph: 2 entities + 1 relation
        # Total per compound (2 graphs): 4 entities + 2 relations
        # Total for 2 compounds: 8 entities + 4 relations
        
        # Note: add_entity is called 2 times per compound per graph = 8 times total
        assert service.kg_service.add_entity_with_resolution.call_count == 8 
        assert service.kg_service.add_relation.call_count == 4

    finally:
        os.remove(tmp_path)
