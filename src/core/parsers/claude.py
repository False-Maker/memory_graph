"""
Claude Conversation Parser
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


class ClaudeParser(BaseParser):
    """Parser for Claude conversation export format"""
    
    def get_platform_name(self) -> ConversationPlatform:
        return ConversationPlatform.CLAUDE
    
    def can_parse(self, data: Any) -> bool:
        """Check if data is in Claude format"""
        if isinstance(data, dict):
            # Check for Claude-specific fields
            if "conversations" in data:
                # Verify it has Claude-like structure
                convs = data.get("conversations", [])
                if convs and isinstance(convs[0], dict):
                    # Check for Claude-specific message structure
                    first_conv = convs[0]
                    if "messages" in first_conv or "chat" in first_conv:
                        return True
            # Single conversation with chat-style messages
            if "chat" in data and isinstance(data.get("chat"), list):
                chat = data.get("chat", [])
                if chat and isinstance(chat[0], dict):
                    msg = chat[0]
                    if "sender" in msg or "text" in msg or "content" in msg:
                        return True
            # Single conversation with messages
            if "messages" in data and isinstance(data.get("messages"), list):
                msgs = data.get("messages", [])
                if msgs and isinstance(msgs[0], dict):
                    msg = msgs[0]
                    if "sender" in msg or ("role" in msg and msg.get("role") in ["human", "assistant"]):
                        return True
        elif isinstance(data, list):
            # List of conversations
            if data and isinstance(data[0], dict):
                first = data[0]
                if "messages" in first or "chat" in first:
                    return True
        return False
    
    def parse(self, data: Any) -> List[Conversation]:
        """Parse Claude data into Conversation objects"""
        if not self.can_parse(data):
            raise ParseError("Invalid Claude format")
        
        conversations = []
        
        # Handle single conversation
        if isinstance(data, dict) and ("messages" in data or "chat" in data):
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
            raise ParseError("No valid conversations found in Claude data")
        
        return conversations
    
    def _parse_single_conversation(self, data: Dict) -> Optional[Conversation]:
        """Parse a single Claude conversation"""
        try:
            # Get messages - could be in "messages" or "chat" field
            messages_data = data.get("messages", []) or data.get("chat", [])
            
            if not messages_data:
                return None
            
            # Get conversation metadata
            title = data.get("name", data.get("title", "Untitled"))
            
            # Parse messages
            messages = []
            for msg_data in messages_data:
                # Determine role - Claude uses "human"/"assistant" or "user"/"assistant"
                sender = msg_data.get("sender", "")
                role = self._normalize_role(sender)
                
                # Skip system messages
                if role == "system":
                    continue
                
                # Extract content
                content = msg_data.get("text", msg_data.get("content", ""))
                if isinstance(content, dict):
                    content = content.get("text", str(content))
                
                if not content or not str(content).strip():
                    continue
                
                # Get timestamp
                timestamp = None
                ts_value = msg_data.get("timestamp")
                if ts_value:
                    timestamp = self._parse_timestamp(ts_value)
                
                # Extract thinking (reasoning) if present
                thinking = msg_data.get("thinking", msg_data.get("reasoning"))
                
                # Get model
                model = msg_data.get("model") or data.get("model")
                
                # Extract tool calls if present
                tool_calls = msg_data.get("tool_calls", msg_data.get("tools"))
                
                message = Message(
                    role=role,
                    content=str(content).strip(),
                    timestamp=timestamp,
                    model=model,
                    thinking=thinking,
                    tool_calls=tool_calls,
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
            
            if data.get("chat_before"):
                created_at = self._parse_timestamp(data["chat_before"])
            elif data.get("created_at"):
                created_at = self._parse_timestamp(data["created_at"])
            
            if data.get("chat_after"):
                updated_at = self._parse_timestamp(data["chat_after"])
            elif data.get("updated_at"):
                updated_at = self._parse_timestamp(data["updated_at"])
            
            # Get model from data or first message
            model = data.get("model")
            if not model:
                for msg in messages:
                    if msg.model:
                        model = msg.model
                        break
            
            # Get UUID
            uuid = data.get("uuid", data.get("id"))
            
            return Conversation(
                platform=ConversationPlatform.CLAUDE,
                title=title,
                messages=messages_with_time + messages_without_time,
                created_at=created_at,
                updated_at=updated_at,
                model=model,
                metadata={
                    "conversation_id": uuid,
                    "source": "claude"
                }
            )
            
        except Exception as e:
            raise ParseError(f"Failed to parse Claude conversation: {str(e)}")
    
    def _normalize_role(self, sender: str) -> str:
        """Normalize role names to standard format"""
        sender_lower = sender.lower() if sender else ""
        if sender_lower in ["human", "user"]:
            return "user"
        elif sender_lower == "assistant":
            return "assistant"
        elif sender_lower == "system":
            return "system"
        return sender_lower if sender_lower else "assistant"
    
    def _parse_timestamp(self, ts: Any) -> Optional[datetime]:
        """Parse various timestamp formats"""
        if isinstance(ts, datetime):
            return ts
        elif isinstance(ts, (int, float)):
            # Unix timestamp - could be seconds or milliseconds
            try:
                # Try seconds first
                if ts > 1e10:  # Milliseconds
                    ts = ts / 1000
                return datetime.fromtimestamp(ts)
            except (ValueError, OSError):
                pass
        elif isinstance(ts, str):
            # ISO format string
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                pass
            # Try parsing as unix timestamp string
            try:
                ts_float = float(ts)
                if ts_float > 1e10:
                    ts_float = ts_float / 1000
                return datetime.fromtimestamp(ts_float)
            except (ValueError, OSError):
                pass
        return None
