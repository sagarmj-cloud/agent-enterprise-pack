"""
Memory Module
=============
Enterprise memory management for AI agent conversations.

Components:
- ContextWindowManager: Token-aware context management
- MemoryCompressor: LLM-based conversation summarization
- SessionCache: TTL-based session caching
"""

from .context_manager import (
    ContextWindowManager,
    ContextConfig,
    TruncationStrategy,
    Message,
    MessageRole,
    TokenCounter,
    ApproximateTokenCounter,
    TiktokenCounter,
    GeminiTokenCounter,
    create_context_manager,
)

from .memory_compressor import (
    MemoryCompressor,
    IncrementalCompressor,
    CompressionResult,
    CompressorConfig,
    CompressionLevel,
)

from .ttl_cache import (
    SessionCache,
    AgentSessionCache,
    CacheBackend,
    InMemoryBackend,
    RedisBackend,
    CacheStats,
    CacheEntry,
    create_memory_manager,
)


__all__ = [
    # Context Manager
    'ContextWindowManager',
    'ContextConfig',
    'TruncationStrategy',
    'Message',
    'MessageRole',
    'TokenCounter',
    'ApproximateTokenCounter',
    'TiktokenCounter',
    'GeminiTokenCounter',
    'create_context_manager',
    
    # Memory Compressor
    'MemoryCompressor',
    'IncrementalCompressor',
    'CompressionResult',
    'CompressorConfig',
    'CompressionLevel',
    
    # Session Cache
    'SessionCache',
    'AgentSessionCache',
    'CacheBackend',
    'InMemoryBackend',
    'RedisBackend',
    'CacheStats',
    'CacheEntry',
    'create_memory_manager',
]
