"""
Entity Detector for Memory Graph

Ported from MemPalace to provide regex-based entity detection as a fast alternative to LLM-based extraction.
This detects entities using frequency patterns and regular expressions, suitable for preprocessing conversations.
"""

import re
from collections import Counter
from typing import Dict, List, Set, Tuple, Optional, Pattern
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EntityCandidate:
    """Candidate entity with supporting evidence"""
    text: str
    frequency: int
    contexts: List[str]
    positions: List[Tuple[int, int]]  # (start, end) positions
    confidence: float = 0.0


class EntityDetector:
    """Regex-based entity detection for conversation transcripts"""

    def __init__(self,
                 min_frequency: int = 2,
                 min_length: int = 2,
                 max_length: int = 50,
                 confidence_threshold: float = 0.6):
        """
        Initialize entity detector with configuration.

        Args:
            min_frequency: Minimum number of occurrences to consider as entity
            min_length: Minimum character length for entities
            max_length: Maximum character length for entities
            confidence_threshold: Minimum confidence score (0.0-1.0)
        """
        self.min_frequency = min_frequency
        self.min_length = min_length
        self.max_length = max_length
        self.confidence_threshold = confidence_threshold

        # Regex patterns for different entity types
        self.patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'url': r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?',
            'ip_address': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            'phone': r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            'timestamp': r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b',
            'time_24h': r'\b(0?[0-9]|1[0-9]|2[0-3]):[0-5][0-9]\b',
            'time_12h': r'\b(0?[1-9]|1[0-2]):[0-5][0-9]\s?(?:AM|PM|am|pm)\b',
            'hashtag': r'#\w+',
            'mention': r'@\w+',
            'file_path': r'\b[a-zA-Z]:\\[^\\\n\r]+(?=\s|$)|/[^/\s]+(?:/[^/\s]+)*\b',
            'code_block': r'```[^`]*```|`[^`]*`',
            'uuid': r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b',
        }

        # Entity type specific patterns for names and organizations
        self.name_patterns = [
            # Title patterns
            r'(?:Mr|Mrs|Ms|Dr|Prof)\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            # Simple names (capitalized words)
            r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b',
        ]

        # Organization patterns
        self.org_patterns = [
            # Common company suffixes
            r'\b(?:Inc|Corp|LLC|Ltd|GmbH|AG|SA|Co)\.\s+[A-Z][a-zA-Z\s]+\b',
            # Organization names
            r'\b(?:Google|Microsoft|Apple|Amazon|Meta|OpenAI|Anthropic)\b',
        ]

    def extract_entities(self, text: str,
                        context_window: int = 50) -> Dict[str, List[Dict]]:
        """
        Extract entities from text using regex patterns.

        Args:
            text: Input text to analyze
            context_window: Number of characters around entity for context

        Returns:
            Dictionary mapping entity type to list of entity details
        """
        entities = {}

        # Preprocess text
        cleaned_text = self._preprocess_text(text)

        # Apply all patterns
        for entity_type, pattern in self.patterns.items():
            matches = list(re.finditer(pattern, cleaned_text))
            if matches:
                entities[entity_type] = []
                for match in matches:
                    entity = self._create_entity_from_match(
                        match, entity_type, cleaned_text, context_window
                    )
                    entities[entity_type].append(entity)

        # Extract names and organizations
        entities['name'] = self._extract_names(cleaned_text, context_window)
        entities['organization'] = self._extract_organizations(cleaned_text, context_window)

        # Post-process to filter by frequency and confidence
        entities = self._filter_entities(entities)

        return entities

    def _preprocess_text(self, text: str) -> str:
        """Clean and normalize text for entity detection"""
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        # Preserve important characters for entity detection
        return text

    def _create_entity_from_match(self,
                                  match: re.Match,
                                  entity_type: str,
                                  text: str,
                                  context_window: int) -> Dict:
        """Create entity record from regex match"""
        start, end = match.span()
        entity_text = match.group()

        # Extract context
        context_start = max(0, start - context_window)
        context_end = min(len(text), end + context_window)
        context = text[context_start:context_end]

        return {
            'text': entity_text,
            'type': entity_type,
            'start': start,
            'end': end,
            'context': context,
            'confidence': 1.0  # Regex matches are 100% confident
        }

    def _extract_names(self, text: str, context_window: int) -> List[Dict]:
        """Extract name entities using multiple patterns"""
        entities = []

        for pattern in self.name_patterns:
            matches = list(re.finditer(pattern, text))
            for match in matches:
                # Filter out false positives
                entity_text = match.group()
                if self._is_valid_name(entity_text):
                    entity = self._create_entity_from_match(
                        match, 'name', text, context_window
                    )
                    entities.append(entity)

        return entities

    def _extract_organizations(self, text: str, context_window: int) -> List[Dict]:
        """Extract organization entities"""
        entities = []

        for pattern in self.org_patterns:
            matches = list(re.finditer(pattern, text))
            for match in matches:
                entity = self._create_entity_from_match(
                    match, 'organization', text, context_window
                )
                entities.append(entity)

        return entities

    def _is_valid_name(self, text: str) -> bool:
        """Check if matched text is likely a real name"""
        # Filter out single letters or too short names
        if len(text.strip()) < 3:
            return False

        # Filter out all-caps acronyms (likely not names)
        if text.isupper() and len(text.split()) == 1:
            return False

        # Filter out common false positives
        false_positives = {'the', 'and', 'for', 'with', 'from', 'this', 'that', 'but'}
        if text.lower().strip() in false_positives:
            return False

        return True

    def _filter_entities(self, entities: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """Filter entities by frequency and confidence"""
        filtered = {}

        for entity_type, entity_list in entities.items():
            if entity_type in ['name', 'organization']:
                # For names and orgs, filter by frequency
                entity_counter = Counter(entity['text'] for entity in entity_list)
                filtered_entities = []

                for entity in entity_list:
                    count = entity_counter[entity['text']]
                    if count >= self.min_frequency:
                        entity['frequency'] = count
                        filtered_entities.append(entity)

                filtered[entity_type] = filtered_entities
            else:
                # For other entity types, use confidence threshold
                filtered[entity_type] = [
                    entity for entity in entity_list
                    if entity['confidence'] >= self.confidence_threshold
                ]

        return filtered

    def find_entities_with_frequency(self, text: str) -> Dict[str, EntityCandidate]:
        """Find entities and analyze their frequency across the text"""
        # Get all entities first
        entities_dict = self.extract_entities(text)

        # Flatten all entities with their positions
        all_entities = []
        for entity_type, entities in entities_dict.items():
            for entity in entities:
                all_entities.append({
                    'text': entity['text'],
                    'start': entity['start'],
                    'end': entity['end'],
                    'type': entity_type,
                    'context': entity['context']
                })

        # Count frequencies
        entity_counter = Counter(entity['text'] for entity in all_entities)

        # Group by text
        entity_groups = {}
        for entity in all_entities:
            text = entity['text']
            if text not in entity_groups:
                entity_groups[text] = []
            entity_groups[text].append(entity)

        # Create EntityCandidates
        candidates = {}
        for text, occurrences in entity_groups.items():
            frequency = entity_counter[text]

            if frequency >= self.min_frequency and self.min_length <= len(text) <= self.max_length:
                # Calculate confidence based on frequency
                confidence = min(1.0, frequency / 10.0)  # Scale to 0-1

                candidate = EntityCandidate(
                    text=text,
                    frequency=frequency,
                    contexts=[occ['context'] for occ in occurrences],
                    positions=[(occ['start'], occ['end']) for occ in occurrences],
                    confidence=confidence
                )
                candidates[text] = candidate

        return candidates


class ConversationEntityDetector:
    """Entity detector optimized for conversation transcripts"""

    def __init__(self, **kwargs):
        self.detector = EntityDetector(**kwargs)

    def process_conversation(self, messages: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Process a conversation to extract entities from all messages.

        Args:
            messages: List of message dictionaries with 'content' and optional 'role'

        Returns:
            Combined entities from all messages
        """
        all_entities = {}

        for i, message in enumerate(messages):
            content = message.get('content', '')
            if not content.strip():
                continue

            # Extract entities from this message
            entities = self.detector.extract_entities(content)

            # Add message metadata
            for entity_type, entity_list in entities.items():
                for entity in entity_list:
                    entity['message_index'] = i
                    entity['message_role'] = message.get('role', 'user')

            # Merge with existing entities
            for entity_type, entity_list in entities.items():
                if entity_type not in all_entities:
                    all_entities[entity_type] = []
                all_entities[entity_type].extend(entity_list)

        return all_entities

    def get_top_entities(self, entities: Dict[str, List[Dict]],
                        top_n: int = 20) -> List[Dict]:
        """
        Get top N entities by frequency across all entity types.

        Args:
            entities: Dictionary of entities from process_conversation
            top_n: Number of top entities to return

        Returns:
            List of entities sorted by frequency
        """
        # Flatten all entities
        all_entities = []
        for entity_type, entity_list in entities.items():
            for entity in entity_list:
                entity['type'] = entity_type
                all_entities.append(entity)

        # Sort by frequency (highest first)
        all_entities.sort(key=lambda x: x.get('frequency', 1), reverse=True)

        return all_entities[:top_n]


# Convenience functions
def detect_entities(text: str, **kwargs) -> Dict[str, List[Dict]]:
    """Quick entity detection"""
    detector = EntityDetector(**kwargs)
    return detector.extract_entities(text)


def detect_conversation_entities(messages: List[Dict], **kwargs) -> Dict[str, List[Dict]]:
    """Quick entity detection for conversations"""
    detector = ConversationEntityDetector(**kwargs)
    return detector.process_conversation(messages)