"""
Rate Limiter
============
Multi-algorithm, multi-backend rate limiting for AI agent endpoints.

Algorithms:
- Token Bucket - Allows bursts, steady refill
- Sliding Window - Precise rate limiting
- Fixed Window - Simple time-based windows
- Leaky Bucket - Smooths out bursts

Backends:
- In-Memory - Single instance, development
- Redis - Distributed, production
"""

import time
import asyncio
import hashlib
import logging
from typing import Optional, Dict, Any, Tuple, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


class RateLimitAlgorithm(Enum):
    """Rate limiting algorithms."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"


class RateLimitResult(Enum):
    """Rate limit check result."""
    ALLOWED = "allowed"
    DENIED = "denied"
    THROTTLED = "throttled"


@dataclass
class RateLimitResponse:
    """Response from rate limit check."""
    result: RateLimitResult
    limit: int
    remaining: int
    reset_at: float  # Unix timestamp
    retry_after: Optional[float] = None  # Seconds
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_window: int = 100
    window_seconds: int = 60
    burst_limit: Optional[int] = None  # For token bucket
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW
    key_prefix: str = "ratelimit"
    include_headers: bool = True


class RateLimitBackend(ABC):
    """Abstract backend for rate limit storage."""
    
    @abstractmethod
    async def get_and_increment(
        self,
        key: str,
        window_seconds: int,
        limit: int,
    ) -> Tuple[int, float]:
        """
        Get current count and increment.
        
        Returns:
            Tuple of (current_count, window_reset_time)
        """
        pass
    
    @abstractmethod
    async def get_tokens(self, key: str, max_tokens: int, refill_rate: float) -> Tuple[float, float]:
        """
        Get available tokens for token bucket.
        
        Returns:
            Tuple of (available_tokens, last_update_time)
        """
        pass
    
    @abstractmethod
    async def consume_tokens(self, key: str, tokens: float, max_tokens: int, refill_rate: float) -> bool:
        """Consume tokens from bucket. Returns True if successful."""
        pass


class InMemoryBackend(RateLimitBackend):
    """In-memory rate limit storage for single-instance deployments."""
    
    def __init__(self):
        self._windows: Dict[str, Dict[float, int]] = defaultdict(dict)
        self._tokens: Dict[str, Tuple[float, float]] = {}  # key -> (tokens, last_update)
        self._lock = threading.Lock()
    
    async def get_and_increment(
        self,
        key: str,
        window_seconds: int,
        limit: int,
    ) -> Tuple[int, float]:
        """Get count and increment for sliding window."""
        now = time.time()
        window_start = now - window_seconds
        
        with self._lock:
            # Clean old entries
            windows = self._windows[key]
            windows = {ts: count for ts, count in windows.items() if ts > window_start}
            
            # Count requests in window
            current_count = sum(windows.values())
            
            # Add new request
            windows[now] = windows.get(now, 0) + 1
            self._windows[key] = windows
            
            reset_at = min(windows.keys()) + window_seconds if windows else now + window_seconds
        
        return current_count + 1, reset_at
    
    async def get_tokens(self, key: str, max_tokens: int, refill_rate: float) -> Tuple[float, float]:
        """Get available tokens."""
        now = time.time()
        
        with self._lock:
            if key not in self._tokens:
                self._tokens[key] = (max_tokens, now)
                return max_tokens, now
            
            tokens, last_update = self._tokens[key]
            elapsed = now - last_update
            refilled = min(max_tokens, tokens + (elapsed * refill_rate))
            return refilled, last_update
    
    async def consume_tokens(self, key: str, tokens: float, max_tokens: int, refill_rate: float) -> bool:
        """Consume tokens from bucket."""
        now = time.time()
        
        with self._lock:
            available, last_update = await self.get_tokens(key, max_tokens, refill_rate)
            
            if available >= tokens:
                elapsed = now - last_update
                refilled = min(max_tokens, available + (elapsed * refill_rate))
                self._tokens[key] = (refilled - tokens, now)
                return True
            return False
    
    def clear(self):
        """Clear all rate limit data."""
        with self._lock:
            self._windows.clear()
            self._tokens.clear()


class RedisBackend(RateLimitBackend):
    """Redis-based rate limit storage for distributed deployments."""
    
    # Lua script for atomic sliding window increment
    SLIDING_WINDOW_SCRIPT = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    
    -- Remove old entries
    redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
    
    -- Count current entries
    local count = redis.call('ZCARD', key)
    
    -- Add new entry
    redis.call('ZADD', key, now, now .. ':' .. math.random())
    redis.call('EXPIRE', key, window + 1)
    
    -- Get oldest entry for reset time
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local reset_at = oldest[2] and (tonumber(oldest[2]) + window) or (now + window)
    
    return {count + 1, reset_at}
    """
    
    # Lua script for token bucket
    TOKEN_BUCKET_SCRIPT = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local max_tokens = tonumber(ARGV[2])
    local refill_rate = tonumber(ARGV[3])
    local requested = tonumber(ARGV[4])
    
    local bucket = redis.call('HMGET', key, 'tokens', 'last_update')
    local tokens = tonumber(bucket[1]) or max_tokens
    local last_update = tonumber(bucket[2]) or now
    
    -- Calculate refilled tokens
    local elapsed = now - last_update
    tokens = math.min(max_tokens, tokens + (elapsed * refill_rate))
    
    -- Check if we can consume
    if tokens >= requested then
        tokens = tokens - requested
        redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
        redis.call('EXPIRE', key, math.ceil(max_tokens / refill_rate) + 1)
        return {1, tokens}
    else
        return {0, tokens}
    end
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """Initialize Redis backend."""
        self.redis_url = redis_url
        self._client = None
        self._sliding_script = None
        self._token_script = None
    
    async def _get_client(self):
        """Lazy initialize Redis client."""
        if self._client is None:
            try:
                import redis.asyncio as redis
                self._client = redis.from_url(self.redis_url)
                self._sliding_script = self._client.register_script(self.SLIDING_WINDOW_SCRIPT)
                self._token_script = self._client.register_script(self.TOKEN_BUCKET_SCRIPT)
            except ImportError:
                raise RuntimeError("redis package required for Redis backend: pip install redis")
        return self._client
    
    async def get_and_increment(
        self,
        key: str,
        window_seconds: int,
        limit: int,
    ) -> Tuple[int, float]:
        """Get count and increment using sliding window."""
        client = await self._get_client()
        now = time.time()
        
        result = await self._sliding_script(
            keys=[key],
            args=[now, window_seconds, limit],
        )
        
        return int(result[0]), float(result[1])
    
    async def get_tokens(self, key: str, max_tokens: int, refill_rate: float) -> Tuple[float, float]:
        """Get available tokens."""
        client = await self._get_client()
        
        bucket = await client.hmget(key, 'tokens', 'last_update')
        now = time.time()
        
        tokens = float(bucket[0]) if bucket[0] else max_tokens
        last_update = float(bucket[1]) if bucket[1] else now
        
        elapsed = now - last_update
        refilled = min(max_tokens, tokens + (elapsed * refill_rate))
        
        return refilled, last_update
    
    async def consume_tokens(self, key: str, tokens: float, max_tokens: int, refill_rate: float) -> bool:
        """Consume tokens from bucket."""
        client = await self._get_client()
        now = time.time()
        
        result = await self._token_script(
            keys=[key],
            args=[now, max_tokens, refill_rate, tokens],
        )
        
        return bool(result[0])


class RateLimiter:
    """
    Multi-algorithm rate limiter with pluggable backends.
    
    Example:
        # In-memory for development
        limiter = RateLimiter(
            requests_per_window=100,
            window_seconds=60,
        )
        
        # Redis for production
        limiter = RateLimiter(
            backend="redis",
            redis_url="redis://localhost:6379",
            requests_per_window=1000,
            window_seconds=60,
        )
        
        # Check rate limit
        result = await limiter.check("user:123")
        if result.result == RateLimitResult.DENIED:
            raise HTTPException(429, detail="Rate limit exceeded")
    """
    
    def __init__(
        self,
        requests_per_window: int = 100,
        window_seconds: int = 60,
        burst_limit: Optional[int] = None,
        algorithm: Union[RateLimitAlgorithm, str] = RateLimitAlgorithm.SLIDING_WINDOW,
        backend: Union[str, RateLimitBackend] = "memory",
        redis_url: str = "redis://localhost:6379",
        key_prefix: str = "ratelimit",
    ):
        """Initialize rate limiter."""
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.burst_limit = burst_limit or requests_per_window
        self.key_prefix = key_prefix
        
        # Parse algorithm
        if isinstance(algorithm, str):
            algorithm = RateLimitAlgorithm(algorithm)
        self.algorithm = algorithm
        
        # Initialize backend
        if isinstance(backend, RateLimitBackend):
            self._backend = backend
        elif backend == "redis":
            self._backend = RedisBackend(redis_url)
        else:
            self._backend = InMemoryBackend()
    
    async def check(
        self,
        key: str,
        cost: int = 1,
    ) -> RateLimitResponse:
        """
        Check rate limit for key.
        
        Args:
            key: Unique identifier (user ID, IP, API key)
            cost: Number of "requests" this counts as
            
        Returns:
            RateLimitResponse with status and metadata
        """
        full_key = f"{self.key_prefix}:{key}"
        
        if self.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            return await self._check_token_bucket(full_key, cost)
        else:
            return await self._check_sliding_window(full_key, cost)
    
    async def _check_sliding_window(self, key: str, cost: int) -> RateLimitResponse:
        """Check using sliding window algorithm."""
        count, reset_at = await self._backend.get_and_increment(
            key, self.window_seconds, self.requests_per_window
        )
        
        remaining = max(0, self.requests_per_window - count)
        
        if count > self.requests_per_window:
            retry_after = reset_at - time.time()
            return RateLimitResponse(
                result=RateLimitResult.DENIED,
                limit=self.requests_per_window,
                remaining=0,
                reset_at=reset_at,
                retry_after=max(0, retry_after),
                metadata={'algorithm': 'sliding_window', 'current_count': count}
            )
        
        return RateLimitResponse(
            result=RateLimitResult.ALLOWED,
            limit=self.requests_per_window,
            remaining=remaining,
            reset_at=reset_at,
            metadata={'algorithm': 'sliding_window', 'current_count': count}
        )
    
    async def _check_token_bucket(self, key: str, cost: int) -> RateLimitResponse:
        """Check using token bucket algorithm."""
        refill_rate = self.requests_per_window / self.window_seconds
        
        success = await self._backend.consume_tokens(
            key, cost, self.burst_limit, refill_rate
        )
        
        available, _ = await self._backend.get_tokens(key, self.burst_limit, refill_rate)
        
        if success:
            return RateLimitResponse(
                result=RateLimitResult.ALLOWED,
                limit=self.burst_limit,
                remaining=int(available),
                reset_at=time.time() + self.window_seconds,
                metadata={'algorithm': 'token_bucket', 'tokens': available}
            )
        else:
            # Calculate retry time based on token refill
            tokens_needed = cost - available
            retry_after = tokens_needed / refill_rate
            
            return RateLimitResponse(
                result=RateLimitResult.DENIED,
                limit=self.burst_limit,
                remaining=int(available),
                reset_at=time.time() + retry_after,
                retry_after=retry_after,
                metadata={'algorithm': 'token_bucket', 'tokens': available}
            )
    
    async def reset(self, key: str):
        """Reset rate limit for key."""
        if isinstance(self._backend, InMemoryBackend):
            full_key = f"{self.key_prefix}:{key}"
            if full_key in self._backend._windows:
                del self._backend._windows[full_key]
            if full_key in self._backend._tokens:
                del self._backend._tokens[full_key]
        # Redis reset would require key deletion
    
    def get_headers(self, response: RateLimitResponse) -> Dict[str, str]:
        """Get rate limit headers for HTTP response."""
        return {
            'X-RateLimit-Limit': str(response.limit),
            'X-RateLimit-Remaining': str(response.remaining),
            'X-RateLimit-Reset': str(int(response.reset_at)),
            **(
                {'Retry-After': str(int(response.retry_after))}
                if response.retry_after else {}
            ),
        }


class MultiTierRateLimiter:
    """
    Multi-tier rate limiter with different limits per tier.
    
    Example:
        limiter = MultiTierRateLimiter({
            'free': RateLimiter(requests_per_window=10, window_seconds=60),
            'pro': RateLimiter(requests_per_window=100, window_seconds=60),
            'enterprise': RateLimiter(requests_per_window=1000, window_seconds=60),
        })
        
        result = await limiter.check("user:123", tier="pro")
    """
    
    def __init__(self, tiers: Dict[str, RateLimiter]):
        """Initialize with tier-specific limiters."""
        self.tiers = tiers
        self._default_tier = next(iter(tiers.keys()))
    
    async def check(self, key: str, tier: Optional[str] = None, cost: int = 1) -> RateLimitResponse:
        """Check rate limit for key at specified tier."""
        tier = tier or self._default_tier
        if tier not in self.tiers:
            tier = self._default_tier
        
        return await self.tiers[tier].check(key, cost)


class EndpointRateLimiter:
    """
    Endpoint-specific rate limiting with path pattern support.
    
    Example:
        limiter = EndpointRateLimiter()
        limiter.add_rule("/api/chat", requests=50, window=60)
        limiter.add_rule("/api/expensive", requests=5, window=60)
        
        result = await limiter.check("/api/chat", user_id="123")
    """
    
    def __init__(self, default_limiter: Optional[RateLimiter] = None):
        """Initialize with optional default limiter."""
        self.rules: Dict[str, RateLimiter] = {}
        self.default_limiter = default_limiter or RateLimiter()
    
    def add_rule(
        self,
        path_pattern: str,
        requests: int,
        window: int,
        algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW,
    ):
        """Add rate limit rule for path pattern."""
        self.rules[path_pattern] = RateLimiter(
            requests_per_window=requests,
            window_seconds=window,
            algorithm=algorithm,
            key_prefix=f"endpoint:{path_pattern}",
        )
    
    async def check(self, path: str, identifier: str) -> RateLimitResponse:
        """Check rate limit for path and identifier."""
        # Find matching rule (exact match for simplicity)
        limiter = self.rules.get(path, self.default_limiter)
        return await limiter.check(identifier)


# FastAPI middleware helper
def create_rate_limit_middleware(limiter: RateLimiter, key_func: Optional[Callable] = None):
    """
    Create FastAPI middleware for rate limiting.
    
    Example:
        from fastapi import FastAPI, Request
        
        app = FastAPI()
        limiter = RateLimiter()
        
        @app.middleware("http")
        async def rate_limit_middleware(request: Request, call_next):
            key = request.client.host
            result = await limiter.check(key)
            if result.result == RateLimitResult.DENIED:
                return JSONResponse(
                    status_code=429,
                    content={"error": "Rate limit exceeded"},
                    headers=limiter.get_headers(result)
                )
            response = await call_next(request)
            for k, v in limiter.get_headers(result).items():
                response.headers[k] = v
            return response
    """
    async def middleware(request, call_next):
        if key_func:
            key = key_func(request)
        else:
            key = request.client.host if hasattr(request, 'client') else 'unknown'
        
        result = await limiter.check(key)
        
        if result.result == RateLimitResult.DENIED:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": result.retry_after,
                },
                headers=limiter.get_headers(result),
            )
        
        response = await call_next(request)
        
        for k, v in limiter.get_headers(result).items():
            response.headers[k] = v
        
        return response
    
    return middleware


# Export public API
__all__ = [
    'RateLimiter',
    'RateLimitResponse',
    'RateLimitResult',
    'RateLimitConfig',
    'RateLimitAlgorithm',
    'InMemoryBackend',
    'RedisBackend',
    'MultiTierRateLimiter',
    'EndpointRateLimiter',
    'create_rate_limit_middleware',
]
