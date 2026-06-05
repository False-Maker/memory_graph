"""Tests for Parser modules."""

import json
from pathlib import Path
import pytest
from datetime import datetime
from src.core.parsers.base import (
    Message,
    Conversation,
    ConversationPlatform,
    BaseParser,
    ParseError,
)
from src.core.parsers.detector import ConversationDetector


class TestMessage:
    """Test Message dataclass."""

    def test_message_creation(self):
        """Test creating a Message."""
        msg = Message(
            role="user",
            content="Hello world",
            timestamp=datetime.now(),
            model="gpt-4"
        )
        assert msg.role == "user"
        assert msg.content == "Hello world"
        assert msg.model == "gpt-4"

    def test_message_defaults(self):
        """Test Message default values."""
        msg = Message(role="user", content="Test")
        assert msg.timestamp is None
        assert msg.model is None
        assert msg.thinking is None
        assert msg.tool_calls is None
        assert msg.metadata == {}


class TestConversation:
    """Test Conversation dataclass."""

    def test_conversation_creation(self):
        """Test creating a Conversation."""
        conv = Conversation(
            platform=ConversationPlatform.CHATGPT,
            title="Test Conversation",
            messages=[
                Message(role="user", content="Hello"),
                Message(role="assistant", content="Hi there!")
            ]
        )
        assert conv.platform == ConversationPlatform.CHATGPT
        assert conv.title == "Test Conversation"
        assert len(conv.messages) == 2

    def test_conversation_defaults(self):
        """Test Conversation default values."""
        conv = Conversation(platform=ConversationPlatform.CHATGPT)
        assert conv.title is None
        assert conv.messages == []
        assert conv.created_at is None
        assert conv.metadata == {}

    def test_to_memory_content(self):
        """Test converting to memory content format."""
        conv = Conversation(
            platform=ConversationPlatform.CHATGPT,
            title="Test",
            model="gpt-4",
            messages=[
                Message(role="user", content="Hello"),
                Message(role="assistant", content="Hi!")
            ]
        )
        content = conv.to_memory_content()
        
        assert "# Test" in content
        assert "**Model**: gpt-4" in content
        assert "👤 USER" in content
        assert "🤖 ASSISTANT" in content
        assert "Hello" in content
        assert "Hi!" in content

    def test_to_plain_text(self):
        """Test converting to plain text format."""
        conv = Conversation(
            platform=ConversationPlatform.CHATGPT,
            messages=[
                Message(role="user", content="Hello"),
                Message(role="assistant", content="Hi!")
            ]
        )
        text = conv.to_plain_text()
        
        assert "[USER] Hello" in text
        assert "[ASSISTANT] Hi!" in text


class TestConversationPlatform:
    """Test ConversationPlatform enum."""

    def test_platform_values(self):
        """Test platform enum values."""
        assert ConversationPlatform.CHATGPT.value == "chatgpt"
        assert ConversationPlatform.CLAUDE.value == "claude"
        assert ConversationPlatform.CLAUDE_CODE.value == "claude_code"
        assert ConversationPlatform.DEEPSEEK.value == "deepseek"
        assert ConversationPlatform.GEMINI.value == "gemini"
        assert ConversationPlatform.OLLAMA.value == "ollama"
        assert ConversationPlatform.SLACK.value == "slack"
        assert ConversationPlatform.CODEX.value == "codex"
        assert ConversationPlatform.UNKNOWN.value == "unknown"


class TestParseError:
    """Test ParseError exception."""

    def test_parse_error(self):
        """Test raising ParseError."""
        with pytest.raises(ParseError):
            raise ParseError("Test error")

    def test_parse_error_with_code(self):
        """Test ParseError with error code."""
        error = ParseError("Test error")
        assert str(error) == "Test error"


class TestConversationDetectorExtendedFormats:
    """Exercise the MemPalace-compatible fallback parsing path."""

    @pytest.mark.parametrize(
        ("fixture_name", "expected_platform"),
        [
            ("chatgpt_export.json", ConversationPlatform.CHATGPT),
            ("chatgpt_export_collection.json", ConversationPlatform.CHATGPT),
            ("claude_export.json", ConversationPlatform.CLAUDE),
            ("claude_chat_variant.json", ConversationPlatform.CLAUDE),
            ("claude_code_session.jsonl", ConversationPlatform.CLAUDE_CODE),
            ("claude_code_session_variant.jsonl", ConversationPlatform.CLAUDE_CODE),
            ("slack_export.json", ConversationPlatform.SLACK),
            ("slack_thread_variant.json", ConversationPlatform.SLACK),
            ("codex_export.json", ConversationPlatform.CODEX),
            ("codex_export_variant.json", ConversationPlatform.CODEX),
        ],
    )
    def test_detect_platform_identifies_phase1_sample_exports(
        self,
        phase1_import_fixture_dir,
        fixture_name,
        expected_platform,
    ):
        detector = ConversationDetector()
        file_path = Path(phase1_import_fixture_dir) / fixture_name

        platform = detector.detect_platform(file_path.read_text(encoding="utf-8"))

        assert platform == expected_platform

    @pytest.mark.parametrize(
        ("fixture_name", "expected_platform", "expected_title", "expected_message_count"),
        [
            ("chatgpt_export.json", ConversationPlatform.CHATGPT, "ChatGPT Sample Export", 2),
            ("chatgpt_export_collection.json", ConversationPlatform.CHATGPT, "ChatGPT Collection Variant", 2),
            ("claude_export.json", ConversationPlatform.CLAUDE, "Claude Sample Export", 2),
            ("claude_chat_variant.json", ConversationPlatform.CLAUDE, "Claude Chat Variant", 2),
            ("claude_code_session.jsonl", ConversationPlatform.CLAUDE_CODE, "Claude Code Session claude_code_session", 2),
            ("claude_code_session_variant.jsonl", ConversationPlatform.CLAUDE_CODE, "Claude Code Session claude_code_session_variant", 2),
            ("slack_export.json", ConversationPlatform.SLACK, "Slack Conversation slack_export", 2),
            ("slack_thread_variant.json", ConversationPlatform.SLACK, "Slack Conversation slack_thread_variant", 2),
            ("codex_export.json", ConversationPlatform.CODEX, "Codex Session codex_export", 2),
            ("codex_export_variant.json", ConversationPlatform.CODEX, "Codex Session codex_export_variant", 2),
        ],
    )
    def test_parse_file_supports_phase1_sample_exports(
        self,
        phase1_import_fixture_dir,
        fixture_name,
        expected_platform,
        expected_title,
        expected_message_count,
    ):
        detector = ConversationDetector()
        file_path = Path(phase1_import_fixture_dir) / fixture_name

        conversations, platform = detector.parse_file(
            file_path.read_bytes(),
            filename=file_path.name,
        )

        assert platform == expected_platform.value
        assert len(conversations) == 1
        assert conversations[0].platform == expected_platform
        assert conversations[0].title == expected_title
        assert len(conversations[0].messages) == expected_message_count
