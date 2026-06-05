"""
Conversation Parsers Module
"""
from src.core.parsers.base import (
    BaseParser,
    Conversation,
    ConversationPlatform,
    Message,
    ParseError
)

# Import all parsers
from src.core.parsers.chatgpt import ChatGPTParser
from src.core.parsers.claude import ClaudeParser
from src.core.parsers.deepseek import DeepSeekParser
from src.core.parsers.jsonl import JSONLParser
from src.core.parsers.detector import ConversationDetector, get_detector

__all__ = [
    "BaseParser",
    "Conversation",
    "ConversationPlatform",
    "Message",
    "ParseError",
    "ChatGPTParser",
    "ClaudeParser",
    "DeepSeekParser",
    "JSONLParser",
    "ConversationDetector",
    "get_detector",
]
