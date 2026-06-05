"""
Chat Normalizer for Memory Graph

Ported from MemPalace to support 5 conversation formats:
- Claude JSON (claude.com)
- ChatGPT (chat.openai.com)
- Claude Code JSONL
- Codex (github.com/codex)
- Slack (slack.com)

This module normalizes all formats to a standard transcript format.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Iterator
from pydantic import BaseModel, Field


class TranscriptMessage(BaseModel):
    """Standardized message format"""
    role: str = Field(..., description="user, assistant, system, or tool")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(None, description="Message timestamp")
    message_id: Optional[str] = Field(None, description="Unique message ID")
    parent_id: Optional[str] = Field(None, description="Parent message ID")
    metadata: Dict = Field(default_factory=dict, description="Additional metadata")


class TranscriptSession(BaseModel):
    """Normalized conversation session"""
    session_id: str
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    messages: List[TranscriptMessage]
    metadata: Dict = Field(default_factory=dict)


class FormatDetector:
    """Detect conversation file format based on structure"""

    @staticmethod
    def detect_format(file_path: Path) -> str:
        """Detect format by examining file structure"""
        with open(file_path, 'r', encoding='utf-8') as f:
            sample = f.read(1000)  # Read first 1KB

        if 'messages' in sample and 'model' in sample and 'role' in sample:
            # Could be Claude JSON or ChatGPT
            if 'usage' in sample and 'prompt_tokens' in sample:
                return 'chatgpt'
            return 'claude'

        if re.search(r'^{"role":\s*"user".*?"content":', sample, re.MULTILINE):
            return 'claude_code'

        if 'messages' in sample and 'blocks' in sample and (
            'sender_name' in sample
            or 'user_profile' in sample
            or 'username' in sample
        ):
            return 'slack'

        if 'repo' in sample and 'language' in sample:
            return 'codex'

        raise ValueError(f"Cannot detect format for {file_path}")


class ClaudeJSONNormalizer:
    """Normalize claude.com JSON format"""

    @staticmethod
    def normalize(file_path: Path) -> TranscriptSession:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        session_id = data.get('conversation_id', str(file_path.stat().st_mtime))
        title = data.get('title', f'Claude Chat {session_id}')

        messages = []
        if 'messages' in data:
            for msg in data['messages']:
                messages.append(TranscriptMessage(
                    role=msg.get('role', 'user'),
                    content=msg.get('content', ''),
                    timestamp=msg.get('timestamp'),
                    message_id=msg.get('message_id'),
                    parent_id=msg.get('parent_message_id'),
                    metadata={
                        'model': msg.get('model', 'claude-3'),
                        'attachments': msg.get('attachments', []),
                    }
                ))

        return TranscriptSession(
            session_id=session_id,
            title=title,
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at'),
            messages=messages,
            metadata={
                'source': 'claude.com',
                'format_version': data.get('version', '1.0'),
            }
        )


class ChatGPTNormalizer:
    """Normalize chat.openai.com JSON format"""

    @staticmethod
    def normalize(file_path: Path) -> TranscriptSession:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        title = data.get('title', f'ChatGPT Conversation {file_path.stem}')

        messages = []
        if 'mapping' in data:
            mapping = data['mapping']
            # Build conversation tree
            message_tree = {}
            for msg_id, msg_data in mapping.items():
                if msg_data and 'message' in msg_data:
                    msg = msg_data['message']
                    if 'author' not in msg or 'role' not in msg:
                        continue

                    # Extract timestamp
                    timestamp = None
                    if 'create_time' in msg:
                        timestamp = datetime.fromisoformat(msg['create_time'])

                    message_tree[msg_id] = TranscriptMessage(
                        role=msg['role'],
                        content=msg.get('content', {}).get('parts', [''])[0],
                        timestamp=timestamp,
                        message_id=msg_id,
                        parent_id=msg.get('parent'),
                        metadata={
                            'author': msg.get('author', {}).get('name', 'Unknown'),
                            'model': msg.get('metadata', {}).get('model_slug', 'gpt-3.5-turbo'),
                        }
                    )

            # Sort messages by timestamp
            messages = sorted(message_tree.values(), key=lambda m: m.timestamp or datetime.min)

        return TranscriptSession(
            session_id=str(file_path.stat().st_mtime),
            title=title,
            created_at=data.get('create_time'),
            updated_at=data.get('update_time'),
            messages=messages,
            metadata={
                'source': 'chat.openai.com',
                'format_version': data.get('format', 'unknown'),
            }
        )


class ClaudeCodeNormalizer:
    """Normalize Claude Code JSONL format"""

    @staticmethod
    def normalize(file_path: Path) -> TranscriptSession:
        messages = []

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue

                data = json.loads(line)
                role = data.get('role', 'user')
                content = data.get('content', '')

                # Extract message ID and parent ID
                message_id = data.get('messageId')
                parent_id = data.get('parentId')

                messages.append(TranscriptMessage(
                    role=role,
                    content=content,
                    message_id=message_id,
                    parent_id=parent_id,
                    metadata={
                        'model': data.get('model', 'claude-3'),
                        'timestamp': data.get('timestamp'),
                        'session_id': data.get('sessionId'),
                    }
                ))

        return TranscriptSession(
            session_id=file_path.stem,
            title=f"Claude Code Session {file_path.stem}",
            messages=messages,
            metadata={
                'source': 'claude-code',
                'format_version': '1.0',
                'lines_count': len(messages),
            }
        )


class SlackNormalizer:
    """Normalize Slack export format"""

    @staticmethod
    def normalize(file_path: Path) -> TranscriptSession:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        title = f"Slack Conversation {file_path.stem}"
        messages = []

        for msg in data.get('messages', []):
            if msg.get('type') != 'message':
                continue

            # Extract timestamp
            timestamp = None
            if 'ts' in msg:
                timestamp = datetime.fromtimestamp(float(msg['ts']))

            # Extract user info
            user_name = msg.get('user_profile', {}).get('real_name') or msg.get('username', 'Unknown')

            messages.append(TranscriptMessage(
                role='assistant' if msg.get('bot_id') else 'user',
                content=msg.get('text', ''),
                timestamp=timestamp,
                message_id=msg.get('ts'),
                parent_id=msg.get('thread_ts') or None,
                metadata={
                    'username': user_name,
                    'channel': msg.get('channel', 'general'),
                    'thread_id': msg.get('thread_ts'),
                    'is_bot': bool(msg.get('bot_id')),
                }
            ))

        return TranscriptSession(
            session_id=file_path.stem,
            title=title,
            messages=messages,
            metadata={
                'source': 'slack.com',
                'format_version': data.get('slackExportVersion', 'unknown'),
            }
        )


class CodexNormalizer:
    """Normalize GitHub Codex JSON format"""

    @staticmethod
    def normalize(file_path: Path) -> TranscriptSession:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        title = f"Codex Session {file_path.stem}"
        messages = []

        # Process conversation history
        for conv in data.get('conversations', []):
            role = conv.get('role', 'user')
            content = conv.get('content', '')

            # Extract timestamp if available
            timestamp = None
            if 'timestamp' in conv:
                try:
                    timestamp = datetime.fromisoformat(conv['timestamp'])
                except ValueError:
                    pass

            messages.append(TranscriptMessage(
                role=role,
                content=content,
                timestamp=timestamp,
                message_id=conv.get('id'),
                metadata={
                    'language': conv.get('language'),
                    'repo': conv.get('repo'),
                    'file_path': conv.get('file_path'),
                    'line': conv.get('line'),
                }
            ))

        return TranscriptSession(
            session_id=str(file_path.stat().st_mtime),
            title=title,
            messages=messages,
            metadata={
                'source': 'github.com/codex',
                'format_version': data.get('version', '1.0'),
                'repository': data.get('repo'),
            }
        )


class ChatNormalizer:
    """Main normalizer that routes to appropriate format handler"""

    NORMALIZERS = {
        'claude': ClaudeJSONNormalizer,
        'chatgpt': ChatGPTNormalizer,
        'claude_code': ClaudeCodeNormalizer,
        'slack': SlackNormalizer,
        'codex': CodexNormalizer,
    }

    @classmethod
    def normalize(cls, file_path: Union[str, Path]) -> TranscriptSession:
        """Normalize a conversation file to standard transcript format"""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Detect format
        format_name = FormatDetector.detect_format(file_path)

        # Route to appropriate normalizer
        if format_name not in cls.NORMALIZERS:
            raise ValueError(f"Unsupported format: {format_name}")

        normalizer = cls.NORMALIZERS[format_name]
        return normalizer.normalize(file_path)

    @classmethod
    def normalize_directory(cls, directory: Union[str, Path], pattern: str = "*.json") -> Iterator[TranscriptSession]:
        """Normalize all conversation files in a directory"""
        directory = Path(directory)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        for file_path in directory.glob(pattern):
            try:
                yield cls.normalize(file_path)
            except Exception as e:
                print(f"Failed to normalize {file_path}: {e}")
                continue


# Convenience functions for direct import
def normalize_chat_file(file_path: Union[str, Path]) -> TranscriptSession:
    """Quick normalization function"""
    return ChatNormalizer.normalize(file_path)


def normalize_chat_directory(directory: Union[str, Path], pattern: str = "*.json") -> List[TranscriptSession]:
    """Quick directory normalization function"""
    return list(ChatNormalizer.normalize_directory(directory, pattern))
