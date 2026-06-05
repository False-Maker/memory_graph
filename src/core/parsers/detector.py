"""
Conversation Format Detector

Automatically detects the format of conversation data and selects the appropriate parser.
"""
import io
import json
from pathlib import Path
import tempfile
from typing import Any, List, Optional, Tuple
import zipfile

from src.core.chat_normalizer import ChatNormalizer
from src.core.parsers.base import (
    BaseParser,
    Conversation,
    ConversationPlatform,
    Message,
    ParseError,
)
from src.core.parsers.chatgpt import ChatGPTParser
from src.core.parsers.claude import ClaudeParser
from src.core.parsers.deepseek import DeepSeekParser
from src.core.parsers.jsonl import JSONLParser


class ConversationDetector:
    """
    Automatically detects conversation format and parses using the appropriate parser.
    """
    
    def __init__(self):
        """Initialize with all available parsers"""
        self.parsers: List[BaseParser] = [
            ChatGPTParser(),
            ClaudeParser(),
            DeepSeekParser(),
        ]
        self.generic_parser = JSONLParser()

    def detect_and_parse(self, data: Any) -> Tuple[List[Conversation], str]:
        """
        Detect the format and parse the conversation data.
        
        Args:
            data: Raw data (dict, list, string, or bytes)
            
        Returns:
            Tuple of (parsed conversations, detected platform name)
        """
        # First, try to preprocess the data
        processed_data, format_type = self._preprocess(data)
        
        # Try each parser in order of specificity
        for parser in self.parsers:
            try:
                if parser.can_parse(processed_data):
                    conversations = parser.parse(processed_data)
                    platform_name = parser.get_platform_name().value
                    return conversations, platform_name
            except ParseError:
                continue

        # Fall back to the Phase 1 MemPalace-compatible normalizer for
        # file exports our legacy parsers do not model explicitly.
        extended_result = self._try_extended_parse(data)
        if extended_result is not None:
            return extended_result

        # Last resort: try JSONL parser with raw data
        try:
            conversations = self.generic_parser.parse(processed_data)
            return conversations, "unknown"
        except ParseError as e:
            raise ParseError(f"Failed to parse conversation data: {str(e)}")
    
    def _preprocess(self, data: Any) -> Tuple[Any, str]:
        """
        Preprocess the input data to handle different formats.
        
        Returns:
            Tuple of (processed data, detected format type)
        """
        # Handle bytes (could be ZIP file or raw JSON)
        if isinstance(data, bytes):
            # Try to detect if it's a ZIP file (ChatGPT export)
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    # Look for conversations.json in the zip
                    if "conversations.json" in zf.namelist():
                        with zf.open("conversations.json") as f:
                            content = f.read().decode("utf-8")
                            return json.loads(content), "chatgpt_zip"
                    # Try other common files
                    for name in zf.namelist():
                        if name.endswith(".json"):
                            with zf.open(name) as f:
                                content = f.read().decode("utf-8")
                                return json.loads(content), "zip_json"
            except zipfile.BadZipFile:
                # Not a zip file, try as raw bytes
                try:
                    return json.loads(data.decode("utf-8")), "json_bytes"
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Return as string
                    return data.decode("utf-8", errors="ignore"), "bytes_string"
        
        # Handle string input
        if isinstance(data, str):
            # Try to parse as JSON
            try:
                return json.loads(data), "json_string"
            except json.JSONDecodeError:
                # Return as-is (could be plain text or JSONL)
                return data, "string"
        
        # Handle dict or list
        if isinstance(data, (dict, list)):
            return data, "python_object"
        
        raise ParseError(f"Unsupported data type: {type(data)}")
    
    def detect_platform(self, data: Any) -> ConversationPlatform:
        """
        Just detect the platform without parsing.
        
        Args:
            data: Raw data
            
        Returns:
            Detected platform
        """
        try:
            processed_data, _ = self._preprocess(data)

            extended_format = self._detect_extended_format(data)
            if extended_format is not None:
                return self._platform_from_extended_format(extended_format)

            for parser in self.parsers:
                if parser.can_parse(processed_data):
                    return parser.get_platform_name()

            return ConversationPlatform.UNKNOWN
        except Exception:
            return ConversationPlatform.UNKNOWN
    
    def parse_file(self, file_content: bytes, filename: Optional[str] = None) -> Tuple[List[Conversation], str]:
        """
        Parse a conversation file based on its content or filename.
        
        Args:
            file_content: Raw file content
            filename: Optional filename for format hints
            
        Returns:
            Tuple of (parsed conversations, detected platform name)
        """
        # Try by filename first
        if filename:
            platform = self._detect_by_filename(filename)
            if platform != ConversationPlatform.UNKNOWN:
                # Try to parse with the specific parser
                for parser in self.parsers:
                    if parser.get_platform_name() == platform:
                        try:
                            data, _ = self._preprocess(file_content)
                            if parser.can_parse(data):
                                return parser.parse(data), platform.value
                        except ParseError:
                            pass

        extended_result = self._try_extended_parse(file_content, filename)
        if extended_result is not None:
            return extended_result

        # Fall back to auto-detection
        return self.detect_and_parse(file_content)

    def _detect_extended_format(self, data: Any) -> Optional[str]:
        """Detect formats handled by the MemPalace-compatible normalizer."""
        if isinstance(data, bytes):
            sample = data.decode("utf-8", errors="ignore")
        elif isinstance(data, str):
            sample = data
        elif isinstance(data, (dict, list)):
            sample = json.dumps(data, ensure_ascii=False)
        else:
            return None

        compact = sample.strip()
        if not compact:
            return None

        if '"messages"' in compact and '"blocks"' in compact and (
            '"sender_name"' in compact
            or '"user_profile"' in compact
            or '"username"' in compact
        ):
            return "slack"

        if '"conversations"' in compact and '"repo"' in compact and '"language"' in compact:
            return "codex"

        lines = [line.strip() for line in compact.splitlines() if line.strip()]
        if len(lines) > 1:
            for line in lines[:5]:
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    return None

                if (
                    isinstance(payload, dict)
                    and "role" in payload
                    and "content" in payload
                    and any(key in payload for key in ("messageId", "parentId", "sessionId"))
                ):
                    return "claude_code"

        return None

    def _try_extended_parse(
        self,
        data: Any,
        filename: Optional[str] = None,
    ) -> Optional[Tuple[List[Conversation], str]]:
        """Parse supported fallback formats via the Phase 1 normalizer."""
        format_name = self._detect_extended_format(data)
        if format_name is None:
            return None

        if isinstance(data, bytes):
            file_bytes = data
        elif isinstance(data, str):
            file_bytes = data.encode("utf-8")
        else:
            file_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")

        suffix = ".jsonl" if format_name == "claude_code" else ".json"
        temp_filename = filename or f"extended-import{suffix}"
        if not Path(temp_filename).suffix:
            temp_filename = f"{temp_filename}{suffix}"

        try:
            with tempfile.TemporaryDirectory(prefix="memory-graph-import-") as temp_dir:
                temp_path = Path(temp_dir) / Path(temp_filename).name
                temp_path.write_bytes(file_bytes)
                session = ChatNormalizer.normalize(temp_path)
                conversation = self._session_to_conversation(session, format_name)
                return [conversation], format_name
        except Exception as exc:
            raise ParseError(f"Failed to parse conversation data: {str(exc)}") from exc

    def _platform_from_extended_format(self, format_name: str) -> ConversationPlatform:
        platform_map = {
            "claude_code": ConversationPlatform.CLAUDE_CODE,
            "slack": ConversationPlatform.SLACK,
            "codex": ConversationPlatform.CODEX,
        }
        return platform_map.get(format_name, ConversationPlatform.UNKNOWN)

    def _session_to_conversation(self, session: Any, format_name: str) -> Conversation:
        messages = [
            Message(
                role=str(message.role or "assistant"),
                content=str(message.content or "").strip(),
                timestamp=message.timestamp,
                model=message.metadata.get("model"),
                metadata=dict(message.metadata),
            )
            for message in session.messages
            if str(message.content or "").strip()
        ]
        if not messages:
            raise ParseError("No valid messages found in normalized conversation")

        model = next((message.model for message in messages if message.model), None)
        return Conversation(
            platform=self._platform_from_extended_format(format_name),
            title=session.title,
            messages=messages,
            created_at=session.created_at,
            updated_at=session.updated_at,
            model=model,
            metadata={
                "conversation_id": session.session_id,
                "source": format_name,
                **dict(session.metadata),
            },
        )

    def _detect_by_filename(self, filename: str) -> ConversationPlatform:
        """Detect platform by filename"""
        filename_lower = filename.lower()
        
        if "chatgpt" in filename_lower or "openai" in filename_lower:
            return ConversationPlatform.CHATGPT
        elif "claude" in filename_lower:
            return ConversationPlatform.CLAUDE
        elif "deepseek" in filename_lower:
            return ConversationPlatform.DEEPSEEK
        elif "gemini" in filename_lower:
            return ConversationPlatform.GEMINI
        elif "ollama" in filename_lower:
            return ConversationPlatform.OLLAMA
        
        return ConversationPlatform.UNKNOWN


# Singleton instance
_detector: Optional[ConversationDetector] = None


def get_detector() -> ConversationDetector:
    """Get the singleton detector instance"""
    global _detector
    if _detector is None:
        _detector = ConversationDetector()
    return _detector
