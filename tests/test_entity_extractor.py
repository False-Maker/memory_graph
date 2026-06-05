"""Tests for Entity Extractor module."""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.core.entity_extractor import (
    Entity,
    Relationship,
    ExtractionResult,
    EntityExtractor,
)


class TestEntityDataClass:
    """Test Entity dataclass."""

    def test_entity_creation(self):
        """Test creating an Entity."""
        from datetime import datetime
        entity = Entity(
            id="test-1",
            name="Cursor",
            type="project",
            properties={"description": "AI code editor"},
            source_text="Sample text",
            confidence=0.95,
            created_at=datetime.now()
        )
        assert entity.id == "test-1"
        assert entity.name == "Cursor"
        assert entity.type == "project"
        assert entity.confidence == 0.95

    def test_entity_to_dict(self):
        """Test Entity to_dict method."""
        from datetime import datetime
        entity = Entity(
            id="test-1",
            name="Cursor",
            type="project",
            properties={"description": "AI code editor"},
            source_text="Sample text",
            confidence=0.95,
            created_at=datetime(2024, 1, 1, 12, 0, 0)
        )
        result = entity.to_dict()
        
        assert result["id"] == "test-1"
        assert result["name"] == "Cursor"
        assert result["type"] == "project"
        assert result["confidence"] == 0.95

    def test_entity_default_values(self):
        """Test Entity default values."""
        entity = Entity(
            id="test-1",
            name="Test",
            type="concept"
        )
        assert entity.properties == {}
        assert entity.source_text == ""
        assert entity.confidence == 1.0


class TestRelationshipDataClass:
    """Test Relationship dataclass."""

    def test_relationship_creation(self):
        """Test creating a Relationship."""
        rel = Relationship(
            id="rel-1",
            source_id="entity-1",
            target_id="entity-2",
            type="depends_on",
            properties={"weight": 0.8},
            confidence=0.9
        )
        assert rel.id == "rel-1"
        assert rel.source_id == "entity-1"
        assert rel.target_id == "entity-2"
        assert rel.type == "depends_on"

    def test_relationship_to_dict(self):
        """Test Relationship to_dict method."""
        rel = Relationship(
            id="rel-1",
            source_id="entity-1",
            target_id="entity-2",
            type="depends_on",
            properties={"weight": 0.8},
            confidence=0.9
        )
        result = rel.to_dict()
        
        assert result["id"] == "rel-1"
        assert result["source_id"] == "entity-1"
        assert result["target_id"] == "entity-2"
        assert result["type"] == "depends_on"


class TestExtractionResult:
    """Test ExtractionResult dataclass."""

    def test_extraction_result_creation(self):
        """Test creating an ExtractionResult."""
        entity = Entity(id="e1", name="Test", type="concept")
        rel = Relationship(id="r1", source_id="e1", target_id="e2", type="related")
        
        result = ExtractionResult(
            entities=[entity],
            relationships=[rel],
            facts=["fact 1"],
            summary="Test summary"
        )
        
        assert len(result.entities) == 1
        assert len(result.relationships) == 1
        assert result.facts == ["fact 1"]
        assert result.summary == "Test summary"

    def test_extraction_result_defaults(self):
        """Test ExtractionResult default values."""
        result = ExtractionResult()
        
        assert result.entities == []
        assert result.relationships == []
        assert result.facts == []
        assert result.summary == ""

    def test_extraction_result_to_dict(self):
        """Test ExtractionResult to_dict method."""
        entity = Entity(id="e1", name="Test", type="concept")
        result = ExtractionResult(entities=[entity])
        
        result_dict = result.to_dict()
        
        assert "entities" in result_dict
        assert "relationships" in result_dict
        assert "facts" in result_dict
        assert "summary" in result_dict


class TestEntityExtractor:
    """Test EntityExtractor class."""

    def test_entity_types(self):
        """Test that EntityExtractor has correct entity types."""
        mock_llm = MagicMock()
        extractor = EntityExtractor(mock_llm)
        
        assert "person" in extractor.ENTITY_TYPES
        assert "project" in extractor.ENTITY_TYPES
        assert "concept" in extractor.ENTITY_TYPES

    def test_relationship_types(self):
        """Test that EntityExtractor has correct relationship types."""
        mock_llm = MagicMock()
        extractor = EntityExtractor(mock_llm)
        
        assert "depends_on" in extractor.RELATIONSHIP_TYPES
        assert "related_to" in extractor.RELATIONSHIP_TYPES
        assert "works_on" in extractor.RELATIONSHIP_TYPES

    def test_build_extraction_prompt(self):
        """Test building extraction prompt."""
        mock_llm = MagicMock()
        extractor = EntityExtractor(mock_llm)
        
        text = "This is a test text."
        prompt = extractor._build_extraction_prompt(text)
        
        assert "person" in prompt
        assert "project" in prompt
        assert text in prompt

    @pytest.mark.asyncio
    async def test_extract_success(self):
        """Test successful entity extraction."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=json.dumps({
            "entities": [
                {
                    "id": "e1",
                    "name": "Cursor",
                    "type": "project",
                    "properties": {"description": "AI code editor"},
                    "confidence": 0.95
                }
            ],
            "relationships": [
                {
                    "id": "r1",
                    "source_id": "e1",
                    "target_id": "e2",
                    "type": "uses",
                    "properties": {},
                    "confidence": 0.9
                }
            ],
            "facts": ["Cursor is an AI code editor"],
            "summary": "Test summary"
        }))
        
        extractor = EntityExtractor(mock_llm)
        result = await extractor.extract("Test text about Cursor")
        
        assert len(result.entities) == 1
        assert result.entities[0].name == "Cursor"
        assert result.entities[0].type == "project"
        assert len(result.relationships) == 1
        assert result.summary == "Test summary"

    @pytest.mark.asyncio
    async def test_extract_empty_response(self):
        """Test extraction with empty response."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="")
        
        extractor = EntityExtractor(mock_llm)
        result = await extractor.extract("Test text")
        
        assert len(result.entities) == 0
        assert len(result.relationships) == 0

    @pytest.mark.asyncio
    async def test_extract_invalid_json(self):
        """Test extraction with invalid JSON response."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value="This is not JSON")
        
        extractor = EntityExtractor(mock_llm)
        result = await extractor.extract("Test text")
        
        # Should return empty result on parsing failure
        assert len(result.entities) == 0

    @pytest.mark.asyncio
    async def test_extract_with_json_code_block(self):
        """Test extraction with JSON in code block."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value='''
```json
{
    "entities": [
        {"id": "e1", "name": "Test", "type": "concept", "properties": {}, "confidence": 0.9}
    ],
    "relationships": [],
    "facts": [],
    "summary": ""
}
```
''')
        
        extractor = EntityExtractor(mock_llm)
        result = await extractor.extract("Test text")
        
        assert len(result.entities) == 1
        assert result.entities[0].name == "Test"

    @pytest.mark.asyncio
    async def test_extract_batch(self):
        """Test batch extraction."""
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=[
            json.dumps({"entities": [{"id": "e1", "name": "Test1", "type": "concept", "properties": {}, "confidence": 0.9}], "relationships": [], "facts": [], "summary": ""}),
            json.dumps({"entities": [{"id": "e2", "name": "Test2", "type": "concept", "properties": {}, "confidence": 0.9}], "relationships": [], "facts": [], "summary": ""}),
        ])
        
        extractor = EntityExtractor(mock_llm)
        results = await extractor.extract_batch(["Text 1", "Text 2"])
        
        assert len(results) == 2
        assert results[0].entities[0].name == "Test1"
        assert results[1].entities[0].name == "Test2"

    def test_parse_json_response_plain_json(self):
        """Test parsing plain JSON response."""
        mock_llm = MagicMock()
        extractor = EntityExtractor(mock_llm)
        
        json_str = json.dumps({"test": "data"})
        result = extractor._parse_json_response(json_str)
        
        assert result == {"test": "data"}

    def test_parse_json_response_with_code_block(self):
        """Test parsing JSON in code block."""
        mock_llm = MagicMock()
        extractor = EntityExtractor(mock_llm)
        
        json_str = '```json\n{"test": "data"}\n```'
        result = extractor._parse_json_response(json_str)
        
        assert result == {"test": "data"}

    def test_parse_json_response_with_braces(self):
        """Test parsing JSON with braces in text."""
        mock_llm = MagicMock()
        extractor = EntityExtractor(mock_llm)
        
        json_str = 'Some text {"test": "data"} more text'
        result = extractor._parse_json_response(json_str)
        
        assert result == {"test": "data"}

    def test_parse_json_response_invalid(self):
        """Test parsing invalid JSON."""
        mock_llm = MagicMock()
        extractor = EntityExtractor(mock_llm)
        
        result = extractor._parse_json_response("not json at all")
        
        assert result is None
