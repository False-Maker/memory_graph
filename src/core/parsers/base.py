"""
Conversation Parsers - Base Classes and Interfaces
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ConversationPlatform(Enum):
    """Supported conversation platform types"""
    CHATGPT = "chatgpt"
    CLAUDE = "claude"
    CLAUDE_CODE = "claude_code"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"
    OLLAMA = "ollama"
    SLACK = "slack"
    CODEX = "codex"
    UNKNOWN = "unknown"


@dataclass
class Message:
    """Single message in a conversation"""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: Optional[datetime] = None
    model: Optional[str] = None
    thinking: Optional[str] = None  # For Claude/DeepSeek reasoning
    tool_calls: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Conversation:
    """Parsed conversation structure"""
    platform: ConversationPlatform
    title: Optional[str] = None
    messages: List[Message] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_memory_content(self) -> str:
        """Convert conversation to memory content format"""
        lines = []
        lines.append(f"# {self.title or 'Conversation'}")
        if self.model:
            lines.append(f"**Model**: {self.model}")
        if self.created_at:
            lines.append(f"**Date**: {self.created_at.isoformat()}")
        lines.append("")
        
        for msg in self.messages:
            role_label = msg.role.upper()
            if msg.role == "assistant":
                lines.append(f"## 🤖 {role_label}")
            elif msg.role == "user":
                lines.append(f"## 👤 {role_label}")
            else:
                lines.append(f"## {role_label}")
            
            if msg.thinking:
                lines.append(f"**Thinking:**\n```\n{msg.thinking}\n```")
            
            lines.append(msg.content)
            lines.append("")
        
        return "\n".join(lines)
    
    def to_plain_text(self) -> str:
        """Convert conversation to plain text format"""
        lines = []
        
        for msg in self.messages:
            role_label = msg.role.upper()
            lines.append(f"[{role_label}] {msg.content}")
            if msg.thinking:
                lines.append(f"  [Thinking]: {msg.thinking}")
            lines.append("")
        
        return "\n".join(lines)


class BaseParser(ABC):
    """Base class for conversation parsers"""
    
    @abstractmethod
    def can_parse(self, data: Any) -> bool:
        """
        Check if this parser can handle the given data
        
        Args:
            data: Raw data to check (dict, list, string, or file content)
            
        Returns:
            True if this parser can handle the data
        """
        pass
    
    @abstractmethod
    def parse(self, data: Any) -> List[Conversation]:
        """
        Parse the data into Conversation objects
        
        Args:
            data: Raw data to parse
            
        Returns:
            List of parsed conversations
        """
        pass
    
    @abstractmethod
    def get_platform_name(self) -> ConversationPlatform:
        """Get the platform name this parser handles"""
        pass
    
    def validate(self, data: Any) -> bool:
        """
        Validate the data structure before parsing
        
        Args:
            data: Data to validate
            
        Returns:
            True if data is valid for this parser
        """
        return self.can_parse(data)


class ParseError(Exception):
    """Exception raised when parsing fails"""
    pass
