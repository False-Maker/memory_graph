"""
DeepSeek Conversation Parser
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


class DeepSeekParser(BaseParser):
    """Parser for DeepSeek conversation export format"""
    
    def get_platform_name(self) -> ConversationPlatform:
        return ConversationPlatform.DEEPSEEK
    
    def can_parse(self, data: Any) -> bool:
        """Check if data is in DeepSeek format"""
        if isinstance(data, dict):
            # Check for DeepSeek-specific fields
            # DeepSeek uses "conversation_id" or "id" with messages
            if "messages" in data and isinstance(data.get("messages"), list):
                # Check if it has DeepSeek-specific metadata
                if "conversation_id" in data or "id" in data:
                    return True
                # Check messages for DeepSeek-style content
                msgs = data.get("messages", [])
                if msgs and isinstance(msgs[0], dict):
                    msg = msgs[0]
                    # DeepSeek might have "thought" or "reasoning" field
                    if "thought" in msg or "reasoning" in msg:
                        return True
            # Check for conversations list
            if "conversations" in data:
                return True
        return False
    
    def parse(self, data: Any) -> List[Conversation]:
        """Parse DeepSeek data into Conversation objects"""
        if not self.can_parse(data):
            raise ParseError("Invalid DeepSeek format")
        
        conversations = []
        
        # Handle single conversation
        if isinstance(data, dict) and "messages" in data:
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
            raise ParseError("No valid conversations found in DeepSeek data")
        
        return conversations
    
    def _parse_single_conversation(self, data: Dict) -> Optional[Conversation]:
        """Parse a single DeepSeek conversation"""
        try:
            messages_data = data.get("messages", [])
            
            if not messages_data:
                return None
            
            # Get conversation metadata
            title = data.get("title", data.get("name", "Untitled"))
            conv_id = data.get("conversation_id", data.get("id"))
            
            # Parse messages
            messages = []
            for msg_data in messages_data:
                role = msg_data.get("role", "assistant")
                
                # Normalize role
                if role == "system":
                    continue  # Skip system messages
                if role not in ["user", "assistant"]:
                    role = "assistant"
                
                # Extract content
                content = msg_data.get("content", "")
                if isinstance(content, dict):
                    content = content.get("text", str(content))
                
                if not content or not str(content).strip():
                    continue
                
                # Get timestamp
                timestamp = None
                ts_value = msg_data.get("timestamp") or msg_data.get("create_time")
                if ts_value:
                    timestamp = self._parse_timestamp(ts_value)
                
                # Extract thinking/reasoning if present
                thinking = msg_data.get("thought", msg_data.get("reasoning"))
                
                # Get model
                model = msg_data.get("model") or data.get("model")
                
                message = Message(
                    role=role,
                    content=str(content).strip(),
                    timestamp=timestamp,
                    model=model,
                    thinking=thinking,
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
                created_at = self._parse_timestamp(data["create_time"])
            if data.get("update_time"):
                updated_at = self._parse_timestamp(data["update_time"])
            
            # Get model
            model = data.get("model")
            if not model:
                for msg in messages:
                    if msg.model:
                        model = msg.model
                        break
            
            return Conversation(
                platform=ConversationPlatform.DEEPSEEK,
                title=title,
                messages=messages_with_time + messages_without_time,
                created_at=created_at,
                updated_at=updated_at,
                model=model,
                metadata={
                    "conversation_id": conv_id,
                    "source": "deepseek"
                }
            )
            
        except Exception as e:
            raise ParseError(f"Failed to parse DeepSeek conversation: {str(e)}")
    
    def _parse_timestamp(self, ts: Any) -> Optional[datetime]:
        """Parse various timestamp formats"""
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
