"""
TTL Cache
=========
Session caching with time-to-live expiration.

Features:
- In-memory and Redis backends
- Automatic expiration
- LRU eviction
- Session serialization
"""

import time
import json
import asyncio
import logging
import threading
from typing import Optional, Dict, Any, TypeVar, Generic, Callable, List
from dataclasses import dataclass, field
from collections import OrderedDict
from abc import ABC, abstractmethod
import hashlib

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with metadata."""
    value: T
    created_at: float
    expires_at: float
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    size: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class CacheBackend(ABC, Generic[T]):
    """Abstract cache backend."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[T]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: T, ttl_seconds: int) -> bool:
        """Set value in cache with TTL."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass
    
    @abstractmethod
    async def clear(self) -> int:
        """Clear all entries, return count."""
        pass


class InMemoryBackend(CacheBackend[T]):
    """
    In-memory cache backend with LRU eviction.
    
    Suitable for single-instance deployments.
    """
    
    def __init__(self, max_size: int = 1000):
        """
        Initialize in-memory backend.
        
        Args:
            max_size: Maximum number of entries
        """
        self.max_size = max_size
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = threading.Lock()
        self._stats = CacheStats()
    
    async def get(self, key: str) -> Optional[T]:
        """Get value from cache."""
        with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return None
            
            entry = self._cache[key]
            
            # Check expiration
            if time.time() > entry.expires_at:
                del self._cache[key]
                self._stats.expirations += 1
                self._stats.misses += 1
                return None
            
            # Update access stats
            entry.access_count += 1
            entry.last_accessed = time.time()
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            
            self._stats.hits += 1
            return entry.value
    
    async def set(self, key: str, value: T, ttl_seconds: int) -> bool:
        """Set value in cache."""
        with self._lock:
            now = time.time()
            
            # Evict if at capacity
            while len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._stats.evictions += 1
            
            self._cache[key] = CacheEntry(
                value=value,
                created_at=now,
                expires_at=now + ttl_seconds,
            )
            self._stats.size = len(self._cache)
            return True
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats.size = len(self._cache)
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists and not expired."""
        with self._lock:
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            if time.time() > entry.expires_at:
                del self._cache[key]
                return False
            return True
    
    async def clear(self) -> int:
        """Clear all entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats.size = 0
            return count
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._lock:
            self._stats.size = len(self._cache)
            return self._stats
    
    async def cleanup_expired(self) -> int:
        """Remove expired entries."""
        with self._lock:
            now = time.time()
            expired = [k for k, v in self._cache.items() if now > v.expires_at]
            for key in expired:
                del self._cache[key]
            self._stats.expirations += len(expired)
            self._stats.size = len(self._cache)
            return len(expired)


class RedisBackend(CacheBackend[T]):
    """
    Redis cache backend for distributed deployments.
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        prefix: str = "session",
        serializer: Optional[Callable[[T], str]] = None,
        deserializer: Optional[Callable[[str], T]] = None,
    ):
        """
        Initialize Redis backend.
        
        Args:
            redis_url: Redis connection URL
            prefix: Key prefix
            serializer: Custom serialization function
            deserializer: Custom deserialization function
        """
        self.redis_url = redis_url
        self.prefix = prefix
        self._serializer = serializer or json.dumps
        self._deserializer = deserializer or json.loads
        self._client = None
        self._stats = CacheStats()
    
    async def _get_client(self):
        """Lazy initialize Redis client."""
        if self._client is None:
            try:
                import redis.asyncio as redis
                self._client = redis.from_url(self.redis_url)
            except ImportError:
                raise RuntimeError("redis package required: pip install redis")
        return self._client
    
    def _make_key(self, key: str) -> str:
        """Create prefixed key."""
        return f"{self.prefix}:{key}"
    
    async def get(self, key: str) -> Optional[T]:
        """Get value from Redis."""
        client = await self._get_client()
        full_key = self._make_key(key)
        
        try:
            value = await client.get(full_key)
            if value is None:
                self._stats.misses += 1
                return None
            
            self._stats.hits += 1
            return self._deserializer(value)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            self._stats.misses += 1
            return None
    
    async def set(self, key: str, value: T, ttl_seconds: int) -> bool:
        """Set value in Redis with TTL."""
        client = await self._get_client()
        full_key = self._make_key(key)
        
        try:
            serialized = self._serializer(value)
            await client.setex(full_key, ttl_seconds, serialized)
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from Redis."""
        client = await self._get_client()
        full_key = self._make_key(key)
        
        try:
            result = await client.delete(full_key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        client = await self._get_client()
        full_key = self._make_key(key)
        
        try:
            return await client.exists(full_key) > 0
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False
    
    async def clear(self) -> int:
        """Clear all entries with prefix."""
        client = await self._get_client()
        pattern = f"{self.prefix}:*"
        
        try:
            keys = await client.keys(pattern)
            if keys:
                await client.delete(*keys)
            return len(keys)
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            return 0
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats


class SessionCache:
    """
    High-level session cache with multiple backends.
    
    Example:
        # In-memory cache
        cache = SessionCache(ttl_seconds=3600)
        
        # Redis cache
        cache = SessionCache(
            backend="redis",
            redis_url="redis://localhost:6379",
            ttl_seconds=3600,
        )
        
        # Store session
        await cache.set("session:123", {"user": "john", "messages": []})
        
        # Retrieve session
        session = await cache.get("session:123")
    """
    
    def __init__(
        self,
        ttl_seconds: int = 3600,
        backend: str = "memory",
        redis_url: str = "redis://localhost:6379",
        max_size: int = 1000,
        prefix: str = "session",
    ):
        """
        Initialize session cache.
        
        Args:
            ttl_seconds: Default TTL for entries
            backend: Backend type ("memory" or "redis")
            redis_url: Redis URL for redis backend
            max_size: Max size for memory backend
            prefix: Key prefix for redis backend
        """
        self.default_ttl = ttl_seconds
        
        if backend == "redis":
            self._backend = RedisBackend(redis_url=redis_url, prefix=prefix)
        else:
            self._backend = InMemoryBackend(max_size=max_size)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get session from cache."""
        return await self._backend.get(key)
    
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Set session in cache."""
        ttl = ttl_seconds or self.default_ttl
        return await self._backend.set(key, value, ttl)
    
    async def delete(self, key: str) -> bool:
        """Delete session from cache."""
        return await self._backend.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if session exists."""
        return await self._backend.exists(key)
    
    async def get_or_create(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl_seconds: Optional[int] = None,
    ) -> Any:
        """
        Get session or create if not exists.
        
        Args:
            key: Session key
            factory: Function to create new session
            ttl_seconds: Optional TTL override
            
        Returns:
            Session value
        """
        value = await self.get(key)
        if value is not None:
            return value
        
        # Create new session
        value = factory()
        await self.set(key, value, ttl_seconds)
        return value
    
    async def update(
        self,
        key: str,
        updater: Callable[[Any], Any],
        ttl_seconds: Optional[int] = None,
    ) -> Optional[Any]:
        """
        Update existing session.
        
        Args:
            key: Session key
            updater: Function to update session
            ttl_seconds: Optional TTL override
            
        Returns:
            Updated value or None if not found
        """
        value = await self.get(key)
        if value is None:
            return None
        
        updated = updater(value)
        await self.set(key, updated, ttl_seconds)
        return updated
    
    async def clear(self) -> int:
        """Clear all sessions."""
        return await self._backend.clear()
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        if hasattr(self._backend, 'get_stats'):
            return self._backend.get_stats()
        return CacheStats()


class AgentSessionCache(SessionCache):
    """
    Specialized session cache for AI agent conversations.
    
    Stores conversation history, context, and metadata.
    
    Example:
        cache = AgentSessionCache()
        
        # Create new session
        session_id = await cache.create_session(user_id="user123")
        
        # Add message
        await cache.add_message(session_id, {
            "role": "user",
            "content": "Hello!"
        })
        
        # Get conversation
        messages = await cache.get_messages(session_id)
    """
    
    def __init__(
        self,
        ttl_seconds: int = 3600,
        backend: str = "memory",
        redis_url: str = "redis://localhost:6379",
        max_messages: int = 100,
    ):
        """
        Initialize agent session cache.
        
        Args:
            ttl_seconds: Session TTL
            backend: Backend type
            redis_url: Redis URL
            max_messages: Max messages per session
        """
        super().__init__(
            ttl_seconds=ttl_seconds,
            backend=backend,
            redis_url=redis_url,
            prefix="agent_session",
        )
        self.max_messages = max_messages
    
    async def create_session(
        self,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create new agent session."""
        session_id = self._generate_session_id(user_id)
        
        session = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": time.time(),
            "updated_at": time.time(),
            "messages": [],
            "context": {},
            "metadata": metadata or {},
        }
        
        await self.set(session_id, session)
        return session_id
    
    def _generate_session_id(self, user_id: str) -> str:
        """Generate unique session ID."""
        timestamp = str(time.time())
        data = f"{user_id}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:24]
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get full session data."""
        return await self.get(session_id)
    
    async def add_message(
        self,
        session_id: str,
        message: Dict[str, Any],
    ) -> bool:
        """Add message to session."""
        def updater(session):
            session["messages"].append(message)
            session["updated_at"] = time.time()

            # Trim if over max
            if len(session["messages"]) > self.max_messages:
                session["messages"] = session["messages"][-self.max_messages:]

            return session

        result = await self.update(session_id, updater)
        return result is not None
    
    async def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get messages from session."""
        session = await self.get(session_id)
        if session:
            return session.get("messages", [])
        return []
    
    async def set_context(
        self,
        session_id: str,
        key: str,
        value: Any,
    ) -> bool:
        """Set context value in session."""
        async def updater(session):
            session["context"][key] = value
            session["updated_at"] = time.time()
            return session
        
        result = await self.update(session_id, updater)
        return result is not None
    
    async def get_context(self, session_id: str, key: str) -> Optional[Any]:
        """Get context value from session."""
        session = await self.get(session_id)
        if session:
            return session.get("context", {}).get(key)
        return None
    
    async def clear_messages(self, session_id: str) -> bool:
        """Clear messages from session."""
        async def updater(session):
            session["messages"] = []
            session["updated_at"] = time.time()
            return session
        
        result = await self.update(session_id, updater)
        return result is not None


def create_memory_manager(
    backend: str = "memory",
    ttl_seconds: int = 3600,
    redis_url: str = "redis://localhost:6379",
) -> AgentSessionCache:
    """
    Create memory manager for agent sessions.
    
    Convenience function for quick setup.
    """
    return AgentSessionCache(
        ttl_seconds=ttl_seconds,
        backend=backend,
        redis_url=redis_url,
    )


# Export public API
__all__ = [
    'SessionCache',
    'AgentSessionCache',
    'CacheBackend',
    'InMemoryBackend',
    'RedisBackend',
    'CacheStats',
    'CacheEntry',
    'create_memory_manager',
]
