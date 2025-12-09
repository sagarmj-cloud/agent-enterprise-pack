"""
Tests for memory module
========================
"""

import pytest
from core.memory import (
    ContextWindowManager,
    AgentSessionCache,
    TruncationStrategy,
    Message,
    MessageRole,
)


class TestContextWindowManager:
    """Tests for ContextWindowManager."""

    def test_context_within_limit(self):
        manager = ContextWindowManager(max_tokens=1000, target_tokens=800)

        messages = [
            Message(role=MessageRole.USER, content="Hello"),
            Message(role=MessageRole.ASSISTANT, content="Hi there!"),
        ]

        # Add messages to the manager
        manager.add_messages(messages)

        # Get context returns list of dicts
        result = manager.get_context()
        assert len(result) == 2

    def test_context_truncation_sliding_window(self):
        # Use a very small target_tokens to ensure truncation is triggered
        # Each message is ~10 tokens (content + overhead), so 10 messages = ~100 tokens
        manager = ContextWindowManager(
            max_tokens=100,
            target_tokens=50,  # Very low target to trigger truncation
            truncation_strategy=TruncationStrategy.SLIDING_WINDOW,
            sliding_window_size=3  # Only keep last 3 messages
        )

        # Create messages with longer content to exceed token limit
        messages = [
            Message(role=MessageRole.USER, content=f"This is a longer message number {i} with more content")
            for i in range(10)
        ]

        # Add messages to manager
        manager.add_messages(messages)

        # Get context and check it was truncated to sliding window size
        result = manager.get_context()
        assert len(result) <= 3  # Should be truncated to sliding window size


@pytest.mark.asyncio
class TestAgentSessionCache:
    """Tests for AgentSessionCache."""
    
    async def test_create_session(self):
        cache = AgentSessionCache(ttl_seconds=3600, backend="memory")
        session_id = await cache.create_session("user123")
        assert session_id is not None
    
    async def test_get_session(self):
        cache = AgentSessionCache(ttl_seconds=3600, backend="memory")
        session_id = await cache.create_session("user123")
        
        session = await cache.get_session(session_id)
        assert session is not None
        assert session["user_id"] == "user123"
    
    async def test_add_message(self):
        cache = AgentSessionCache(ttl_seconds=3600, backend="memory")
        session_id = await cache.create_session("user123")
        
        await cache.add_message(session_id, {
            "role": "user",
            "content": "Hello"
        })
        
        session = await cache.get_session(session_id)
        assert len(session["messages"]) == 1
        assert session["messages"][0]["content"] == "Hello"
    
    async def test_get_messages(self):
        cache = AgentSessionCache(ttl_seconds=3600, backend="memory")
        session_id = await cache.create_session("user123")
        
        await cache.add_message(session_id, {"role": "user", "content": "Hi"})
        await cache.add_message(session_id, {"role": "assistant", "content": "Hello"})
        
        messages = await cache.get_messages(session_id)
        assert len(messages) == 2

