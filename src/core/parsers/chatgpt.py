"""
ChatGPT Conversation Parser
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from src.core.parsers.base import (
    BaseParser,
    Conversation,
    ConversationPlatform,
    Message,
    ParseError
)


class ChatGPTParser(BaseParser):
    """Parser for ChatGPT conversation export format"""
    
    def get_platform_name(self) -> ConversationPlatform:
        return ConversationPlatform.CHATGPT
    
    def can_parse(self, data: Any) -> bool:
        """Check if data is in ChatGPT format"""
        if isinstance(data, dict):
            # Check for ChatGPT-specific fields
            if "conversations" in data:
                return True
            # Check for single conversation format
            if "mapping" in data:
                return True
        elif isinstance(data, list):
            # List of conversations
            if data and isinstance(data[0], dict):
                if "mapping" in data[0] or "conversations" in data[0]:
                    return True
        return False
    
    def parse(self, data: Any) -> List[Conversation]:
        """Parse ChatGPT data into Conversation objects"""
        if not self.can_parse(data):
            raise ParseError("Invalid ChatGPT format")
        
        conversations = []
        
        # Handle single conversation
        if isinstance(data, dict) and "mapping" in data:
            conv = self._parse_single_conversation(data)
            if conv:
                conversations.append(conv)
        
        # Handle conversations list
        elif isinstance(data, dict) and "conversations" in data:
            for conv_data in data.get("conversations", []):
                conv = self._parse_single_conversation(conv_data)
                if conv:
                    conversations.append(conv)
        
        # Handle list of conversations
        elif isinstance(data, list):
            for conv_data in data:
                conv = self._parse_single_conversation(conv_data)
                if conv:
                    conversations.append(conv)
        
        if not conversations:
            raise ParseError("No valid conversations found in ChatGPT data")
        
        return conversations
    
    def _parse_single_conversation(self, data: Dict) -> Optional[Conversation]:
        """Parse a single ChatGPT conversation"""
        try:
            mapping = data.get("mapping", {})
            if not mapping:
                return None
            
            # Get conversation metadata
            title = data.get("title", "Untitled")
            
            # Parse messages from mapping
            messages = []
            for node_id, node in mapping.items():
                msg_data = node.get("message")
                if not msg_data:
                    continue
                
                # Skip system messages that are just instructions
                role = msg_data.get("role", "assistant")
                if role == "system":
                    # Check if it's a meaningful system message
                    content = msg_data.get("content", {})
                    if isinstance(content, dict):
                        parts = content.get("parts", [])
                        if parts and isinstance(parts[0], str):
                            # Treat as regular assistant message
                            role = "assistant"
                            content_text = "\n".join(parts) if parts else ""
                        else:
                            continue
                    else:
                        continue
                else:
                    # Extract content
                    content = msg_data.get("content", {})
                    if isinstance(content, dict):
                        parts = content.get("parts", [])
                        content_text = "\n".join(parts) if parts else ""
                    else:
                        content_text = str(content) if content else ""
                
                if not content_text.strip():
                    continue
                
                # Get timestamp
                timestamp = None
                if msg_data.get("create_time"):
                    try:
                        timestamp = datetime.fromtimestamp(msg_data["create_time"])
                    except (ValueError, OSError):
                        pass
                
                # Get model
                model = msg_data.get("metadata", {}).get("model_slug")
                
                message = Message(
                    role=role,
                    content=content_text.strip(),
                    timestamp=timestamp,
                    model=model,
                    metadata=msg_data.get("metadata", {})
                )
                messages.append(message)
            
            # Sort messages by timestamp if available
            messages_with_time = [m for m in messages if m.timestamp]
            messages_without_time = [m for m in messages if not m.timestamp]
            
            if messages_with_time:
                messages_with_time.sort(key=lambda m: m.timestamp)
            
            # Get conversation timestamps
            created_at = None
            updated_at = None
            if data.get("create_time"):
                try:
                    created_at = datetime.fromtimestamp(data["create_time"])
                except (ValueError, OSError):
                    pass
            if data.get("update_time"):
                try:
                    updated_at = datetime.fromtimestamp(data["update_time"])
                except (ValueError, OSError):
                    pass
            
            # Get model from first assistant message
            model = None
            for msg in messages:
                if msg.role == "assistant" and msg.model:
                    model = msg.model
                    break
            
            return Conversation(
                platform=ConversationPlatform.CHATGPT,
                title=title,
                messages=messages_with_time + messages_without_time,
                created_at=created_at,
                updated_at=updated_at,
                model=model,
                metadata={
                    "conversation_id": data.get("id"),
                    "source": "chatgpt"
                }
            )
            
        except Exception as e:
            raise ParseError(f"Failed to parse ChatGPT conversation: {str(e)}")
