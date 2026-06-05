"""
Entity Extractor Module
Extract entities and relationships from text using LLM
"""
import json
import uuid
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field

from src.core.llm_manager import LLMManager


# ============================================
# Data Models
# ============================================

@dataclass
class Entity:
    """Entity"""
    id: str
    name: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    source_text: str = ""
    confidence: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "properties": self.properties,
            "source_text": self.source_text,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class Relationship:
    """Relationship"""
    id: str
    source_id: str
    target_id: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.type,
            "properties": self.properties,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class ExtractionResult:
    """Extraction Result"""
    entities: List[Entity] = field(default_factory=list)
    relationships: List[Relationship] = field(default_factory=list)
    facts: List[str] = field(default_factory=list)
    summary: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "relationships": [r.to_dict() for r in self.relationships],
            "facts": self.facts,
            "summary": self.summary
        }


# ============================================
# Entity Extractor
# ============================================

class EntityExtractor:
    """
    Entity Extractor
    Extract entities and relationships from text using LLM
    """
    
    ENTITY_TYPES = [
        "person", "project", "concept", "tool", "organization", 
        "document", "event", "location", "technology"
    ]
    
    RELATIONSHIP_TYPES = [
        "works_on", "depends_on", "similar_to", "related_to", 
        "created_by", "mentioned_in", "part_of", "uses", "knows", "owns"
    ]
    
    def __init__(self, llm_manager: LLMManager):
        self.llm = llm_manager
    
    def _build_extraction_prompt(self, text: str) -> str:
        """Build extraction prompt"""
        return f"""You are an expert at extracting structured information from text.
Your task is to analyze the given text and extract entities (nodes) and relationships (edges).

## Entity Types (choose from):
{', '.join(self.ENTITY_TYPES)}

## Relationship Types (choose from):
{', '.join(self.RELATIONSHIP_TYPES)}

## Instructions:
1. Extract all important entities mentioned in the text
2. Identify relationships between entities
3. Generate a brief summary of the text
4. Extract key facts as a list

## Output Format (JSON):
{{
    "entities": [
        {{
            "id": "unique_id_1",
            "name": "entity name",
            "type": "entity type from the list above",
            "properties": {{"key": "value"}},
            "confidence": 0.95
        }}
    ],
    "relationships": [
        {{
            "id": "unique_rel_1",
            "source_id": "unique_id_1",
            "target_id": "unique_id_2",
            "type": "relationship type from the list above",
            "properties": {{}},
            "confidence": 0.9
        }}
    ],
    "facts": ["fact 1", "fact 2"],
    "summary": "A brief summary of the text content"
}}

## Text to analyze:
{text}

Please provide the extracted information in JSON format. If no entities or relationships are found, return empty arrays."""

    async def extract(self, text: str) -> ExtractionResult:
        """Extract entities and relationships from text"""
        prompt = self._build_extraction_prompt(text)
        
        try:
            response = await self.llm.generate(
                prompt,
                temperature=0.1,
                max_tokens=4096
            )
            
            result = self._parse_json_response(response)
            
            if result:
                entities = [
                    Entity(
                        id=e.get("id", str(uuid.uuid4())),
                        name=e.get("name", ""),
                        type=e.get("type", "concept"),
                        properties=e.get("properties", {}),
                        source_text=text[:500],
                        confidence=e.get("confidence", 0.8)
                    )
                    for e in result.get("entities", [])
                ]
                
                relationships = [
                    Relationship(
                        id=r.get("id", str(uuid.uuid4())),
                        source_id=r.get("source_id", ""),
                        target_id=r.get("target_id", ""),
                        type=r.get("type", "related_to"),
                        properties=r.get("properties", {}),
                        confidence=r.get("confidence", 0.8)
                    )
                    for r in result.get("relationships", [])
                ]
                
                facts = result.get("facts", [])
                summary = result.get("summary", "")
                
                return ExtractionResult(
                    entities=entities,
                    relationships=relationships,
                    facts=facts,
                    summary=summary
                )
        except Exception as e:
            print(f"Entity extraction error: {e}")
        
        return ExtractionResult()
    
    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse JSON response from LLM"""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        brace_match = re.search(r'\{.*\}', response, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass
        
        return None
    
    async def extract_batch(self, texts: List[str]) -> List[ExtractionResult]:
        """Batch extract entities and relationships"""
        results = []
        for text in texts:
            result = await self.extract(text)
            results.append(result)
        return results
