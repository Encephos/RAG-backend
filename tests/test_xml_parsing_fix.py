
import pytest
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock
from src.services.rag_service import RagService

# Sample of concatenated XML (multiple roots)
BROKEN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<compound>
    <name>Compound A</name>
</compound>
<?xml version="1.0" encoding="UTF-8"?>
<compound>
    <name>Compound B</name>
</compound>
"""

@pytest.mark.asyncio
async def test_concatenated_xml_parsing():
    # Setup temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as tmp:
        tmp.write(BROKEN_XML)
        tmp_path = tmp.name

    try:
        service = RagService()
        # Mock external calls to avoid errors
        service.embedding_service.embed_query = AsyncMock(return_value=[0.1]*384)
        service.qdrant_service.upsert = MagicMock()
        service.kg_service.add_entity_with_resolution = AsyncMock(return_value="mock_id")
        service.kg_service.add_relation = MagicMock()
        service.qdrant_service.entity_collections = {"pharmacological": "pharm_collection"} # mock

        # Run Generator
        events = []
        async for event in service.ingest_cannabis_compounds_generator(tmp_path):
            if event.get("step") == "ingesting":
                events.append(event)
            elif event.get("step") == "complete":
                events.append(event)
        
        # We expect it to parse successfully despite multiple roots
        print(events)
        assert len(events) >= 1 # At least completion
        assert "Successfully ingested 2 compounds" in events[-1]["message"]

    finally:
        os.remove(tmp_path)
