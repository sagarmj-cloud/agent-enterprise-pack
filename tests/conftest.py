"""
Pytest configuration and fixtures
==================================
"""

import asyncio
import os
import pytest
from typing import AsyncGenerator, Generator

# Set test environment variables
os.environ["JWT_SECRET"] = "test-secret-key"
os.environ["CACHE_BACKEND"] = "memory"
os.environ["REDIS_URL"] = "redis://localhost:6379"
os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"
os.environ["LOCATION"] = "us-central1"
os.environ["MODEL"] = "gemini-1.5-pro"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def redis_client():
    """Redis client fixture for integration tests."""
    try:
        import redis.asyncio as redis
        client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        await client.ping()
        yield client
        await client.flushdb()
        await client.close()
    except Exception:
        pytest.skip("Redis not available")


@pytest.fixture
def mock_vertex_ai(mocker):
    """Mock Vertex AI for testing."""
    mock = mocker.patch("google.cloud.aiplatform.init")
    return mock


@pytest.fixture
def sample_message():
    """Sample message for testing."""
    return "Hello, this is a test message for the AI agent."


@pytest.fixture
def sample_conversation():
    """Sample conversation history."""
    return [
        {"role": "user", "content": "What is the weather today?"},
        {"role": "assistant", "content": "I don't have access to real-time weather data."},
        {"role": "user", "content": "Can you help me with Python?"},
        {"role": "assistant", "content": "Yes, I can help you with Python programming."},
    ]


@pytest.fixture
def jwt_secret():
    """JWT secret for testing."""
    return "test-jwt-secret-key-for-testing"


@pytest.fixture
def api_key():
    """API key for testing."""
    return "test-api-key-12345"

