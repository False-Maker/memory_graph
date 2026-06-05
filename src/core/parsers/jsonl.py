"""
JSONL (JSON Lines) and Generic JSON Parser
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


class JSONLParser(BaseParser):
    """Parser for JSONL (JSON Lines) and generic JSON conversation formats"""
    
    def get_platform_name(self) -> ConversationPlatform:
        return ConversationPlatform.OLLAMA  # Generic fallback
    
    def can_parse(self, data: Any) -> bool:
        """Check if data is in JSONL or generic JSON format"""
        # Handle string input (could be JSONL)
        if isinstance(data, str):
            # Check if it's JSONL format (multiple lines)
            lines = data.strip().split('\n')
            if len(lines) > 1:
                # Try to parse each line as JSON
                try:
                    for line in lines[:3]:  # Check first few lines
                        if line.strip():
                            json.loads(line)
                    return True
                except json.JSONDecodeError:
                    pass
            else:
                # Single line - try as regular JSON
                try:
                    json.loads(data)
                    return True
                except json.JSONDecodeError:
                    pass
            return False
        
        # Handle dict or list
        if isinstance(data, (dict, list)):
            return True
        
        return False
    
    def parse(self, data: Any) -> List[Conversation]:
        """Parse JSONL or JSON data into Conversation objects"""
        if not self.can_parse(data):
            raise ParseError("Invalid JSON/JSONL format")
        
        conversations = []
        
        # Handle string input (JSONL)
        if isinstance(data, str):
            lines = data.strip().split('\n')
            
            # If multiple lines, try JSONL
            if len(lines) > 1:
                for line in lines:
                    if line.strip():
                        try:
                            obj = json.loads(line)
                            conv = self._parse_single_conversation(obj)
                            if conv:
                                conversations.append(conv)
                        except json.JSONDecodeError:
                            continue
            else:
                # Single JSON
                try:
                    obj = json.loads(data)
                    conv = self._parse_single_conversation(obj)
                    if conv:
                        conversations.append(conv)
                except json.JSONDecodeError as e:
                    raise ParseError(f"Invalid JSON: {str(e)}")
        
        # Handle dict
        elif isinstance(data, dict):
            # Check if it's a list of conversations
            if "conversations" in data:
                for conv_data in data.get("conversations", []):
                    conv = self._parse_single_conversation(conv_data)
                    if conv:
                        conversations.append(conv)
            else:
                # Single conversation
                conv = self._parse_single_conversation(data)
                if conv:
                    conversations.append(conv)
        
        # Handle list
        elif isinstance(data, list):
            for item in data:
                conv = self._parse_single_conversation(item)
                if conv:
                    conversations.append(conv)
        
        if not conversations:
            raise ParseError("No valid conversations found in JSON/JSONL data")
        
        return conversations
    
    def _parse_single_conversation(self, data: Any) -> Optional[Conversation]:
        """Parse a single conversation from generic JSON"""
        if not isinstance(data, dict):
            return None
        
        try:
            messages_data = data.get("messages", [])
            
            # If no messages, try to create from content field
            if not messages_data:
                content = data.get("content", data.get("text", ""))
                if content:
                    # Create a simple single-message conversation
                    role = data.get("role", "user")
                    if role not in ["user", "assistant"]:
                        role = "user"
                    
                    message = Message(
                        role=role,
                        content=str(content),
                        timestamp=self._parse_timestamp(data.get("timestamp")),
                        model=data.get("model")
                    )
                    
                    return Conversation(
                        platform=ConversationPlatform.UNKNOWN,
                        title=data.get("title", data.get("name", "Untitled")),
                        messages=[message],
                        created_at=self._parse_timestamp(data.get("create_time", data.get("created_at"))),
                        model=data.get("model"),
                        metadata={"source": "generic_json"}
                    )
                return None
            
            # Parse messages
            messages = []
            for msg_data in messages_data:
                if not isinstance(msg_data, dict):
                    continue
                
                role = msg_data.get("role", "assistant")
                
                # Skip system
                if role == "system":
                    continue
                
                if role not in ["user", "assistant"]:
                    role = "assistant"
                
                # Extract content
                content = msg_data.get("content", msg_data.get("text", ""))
                if isinstance(content, dict):
                    content = content.get("text", str(content))
                
                if not content or not str(content).strip():
                    continue
                
                message = Message(
                    role=role,
                    content=str(content).strip(),
                    timestamp=self._parse_timestamp(msg_data.get("timestamp")),
                    model=msg_data.get("model"),
                    thinking=msg_data.get("thinking", msg_data.get("reasoning")),
                    metadata=msg_data.get("metadata", {})
                )
                messages.append(message)
            
            if not messages:
                return None
            
            # Sort by timestamp
            messages_with_time = [m for m in messages if m.timestamp]
            messages_without_time = [m for m in messages if not m.timestamp]
            
            if messages_with_time:
                messages_with_time.sort(key=lambda m: m.timestamp)
            
            return Conversation(
                platform=ConversationPlatform.UNKNOWN,
                title=data.get("title", data.get("name", "Untitled")),
                messages=messages_with_time + messages_without_time,
                created_at=self._parse_timestamp(data.get("create_time", data.get("created_at"))),
                model=data.get("model"),
                metadata={
                    "conversation_id": data.get("id", data.get("conversation_id")),
                    "source": "generic_json"
                }
            )
            
        except Exception as e:
            raise ParseError(f"Failed to parse conversation: {str(e)}")
    
    def _parse_timestamp(self, ts: Any) -> Optional[datetime]:
        """Parse various timestamp formats"""
        if ts is None:
            return None
        if isinstance(ts, datetime):
            return ts
        elif isinstance(ts, (int, float)):
            try:
                if ts > 1e10:
                    ts = ts / 1000
                return datetime.fromtimestamp(ts)
            except (ValueError, OSError):
                pass
        elif isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                pass
        return None
