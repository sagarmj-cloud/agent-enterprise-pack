"""
Graceful Degradation
====================
Fallback mechanisms for service degradation.

Fallback Strategies:
- Static response fallback
- Cached response fallback
- Alternative service fallback
- Reduced functionality fallback

Features:
- Priority-ordered fallback chains
- Health-based routing
- Metrics and monitoring
"""

import time
import asyncio
import logging
import hashlib
from typing import Optional, Dict, Any, Callable, List, TypeVar, Generic, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import json

logger = logging.getLogger(__name__)

T = TypeVar('T')


class FallbackReason(Enum):
    """Reason for using fallback."""
    PRIMARY_FAILED = "primary_failed"
    PRIMARY_TIMEOUT = "primary_timeout"
    PRIMARY_UNAVAILABLE = "primary_unavailable"
    CIRCUIT_OPEN = "circuit_open"
    RATE_LIMITED = "rate_limited"
    EXPLICIT = "explicit"


@dataclass
class FallbackResult(Generic[T]):
    """Result from fallback execution."""
    value: T
    used_fallback: bool
    fallback_level: int  # 0 = primary, 1+ = fallback levels
    fallback_reason: Optional[FallbackReason] = None
    provider_name: str = "primary"
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class FallbackProvider(ABC, Generic[T]):
    """Abstract base class for fallback providers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass
    
    @abstractmethod
    async def execute(self, *args, **kwargs) -> T:
        """Execute and return result."""
        pass
    
    async def is_healthy(self) -> bool:
        """Check if provider is healthy."""
        return True


class StaticFallbackProvider(FallbackProvider[T]):
    """
    Provides static fallback responses.
    
    Example:
        fallback = StaticFallbackProvider(
            "static",
            value={"status": "degraded", "message": "Service temporarily unavailable"}
        )
    """
    
    def __init__(self, name: str, value: T):
        """
        Initialize with static value.
        
        Args:
            name: Provider name
            value: Static value to return
        """
        self._name = name
        self._value = value
    
    @property
    def name(self) -> str:
        return self._name
    
    async def execute(self, *args, **kwargs) -> T:
        return self._value


class CacheFallbackProvider(FallbackProvider[T]):
    """
    Provides cached response fallback.
    
    Example:
        cache_fallback = CacheFallbackProvider(
            "cache",
            cache=redis_client,
            key_builder=lambda args, kwargs: f"cache:{args[0]}",
        )
    """
    
    def __init__(
        self,
        name: str,
        cache: Any = None,
        key_builder: Optional[Callable] = None,
        default_value: Optional[T] = None,
        ttl_seconds: int = 3600,
    ):
        """
        Initialize cache fallback.
        
        Args:
            name: Provider name
            cache: Cache backend (Redis client, dict, etc.)
            key_builder: Function to build cache key from args
            default_value: Value if cache miss
            ttl_seconds: Cache TTL
        """
        self._name = name
        self._cache = cache or {}
        self._key_builder = key_builder or (lambda args, kwargs: str(hash((args, frozenset(kwargs.items())))))
        self._default_value = default_value
        self._ttl_seconds = ttl_seconds
    
    @property
    def name(self) -> str:
        return self._name
    
    async def execute(self, *args, **kwargs) -> T:
        key = self._key_builder(args, kwargs)
        
        # Try to get from cache
        if isinstance(self._cache, dict):
            entry = self._cache.get(key)
            if entry:
                value, timestamp = entry
                if time.time() - timestamp < self._ttl_seconds:
                    return value
        else:
            # Assume Redis-like interface
            try:
                value = await self._cache.get(key)
                if value:
                    return json.loads(value) if isinstance(value, str) else value
            except Exception as e:
                logger.warning(f"Cache fallback error: {e}")
        
        if self._default_value is not None:
            return self._default_value
        raise ValueError("No cached value available")
    
    def set(self, key: str, value: T):
        """Store value in cache."""
        if isinstance(self._cache, dict):
            self._cache[key] = (value, time.time())
        # For Redis, would use: await self._cache.setex(key, self._ttl_seconds, json.dumps(value))


class FunctionFallbackProvider(FallbackProvider[T]):
    """
    Wraps a function as a fallback provider.
    
    Example:
        async def simplified_response(query):
            return {"response": "I'm experiencing issues. Please try again."}
        
        fallback = FunctionFallbackProvider("simplified", simplified_response)
    """
    
    def __init__(self, name: str, func: Callable[..., T]):
        """
        Initialize with function.
        
        Args:
            name: Provider name
            func: Function to execute
        """
        self._name = name
        self._func = func
    
    @property
    def name(self) -> str:
        return self._name
    
    async def execute(self, *args, **kwargs) -> T:
        if asyncio.iscoroutinefunction(self._func):
            return await self._func(*args, **kwargs)
        return self._func(*args, **kwargs)


class LLMFallbackProvider(FallbackProvider[str]):
    """
    Fallback to a simpler/cheaper LLM model.
    
    Example:
        # Primary: GPT-4, Fallback: GPT-3.5
        fallback = LLMFallbackProvider(
            "llm-fallback",
            model="gemini-1.5-flash",  # Cheaper model
            client=vertex_client,
        )
    """
    
    def __init__(
        self,
        name: str,
        model: str,
        client: Any,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1000,
    ):
        """
        Initialize LLM fallback.
        
        Args:
            name: Provider name
            model: Model identifier
            client: LLM client
            system_prompt: System prompt override
            max_tokens: Max tokens for response
        """
        self._name = name
        self._model = model
        self._client = client
        self._system_prompt = system_prompt
        self._max_tokens = max_tokens
    
    @property
    def name(self) -> str:
        return self._name
    
    async def execute(self, prompt: str, **kwargs) -> str:
        """Execute LLM call."""
        try:
            # This is a generic interface - actual implementation depends on client
            response = await self._client.generate(
                model=self._model,
                prompt=prompt,
                system_prompt=self._system_prompt,
                max_tokens=self._max_tokens,
                **kwargs,
            )
            return response.text if hasattr(response, 'text') else str(response)
        except Exception as e:
            logger.error(f"LLM fallback error: {e}")
            raise


class DegradationManager:
    """
    Manages graceful degradation with fallback chains.
    
    Example:
        manager = DegradationManager()
        
        # Add fallback chain
        manager.add_chain(
            "vertex-ai",
            primary=vertex_ai_call,
            fallbacks=[
                CacheFallbackProvider("cache", cache),
                LLMFallbackProvider("flash", model="gemini-flash", client=client),
                StaticFallbackProvider("static", {"error": "Service unavailable"}),
            ],
        )
        
        # Execute with fallbacks
        result = await manager.execute(
            "vertex-ai",
            prompt="Hello, world!",
        )
        if result.used_fallback:
            logger.warning(f"Used fallback: {result.provider_name}")
    """
    
    def __init__(self):
        """Initialize degradation manager."""
        self._chains: Dict[str, Dict[str, Any]] = {}
        self._metrics: Dict[str, Dict[str, int]] = {}
    
    def add_chain(
        self,
        name: str,
        primary: Callable,
        fallbacks: List[FallbackProvider],
        timeout_seconds: float = 30.0,
        circuit_breaker: Optional[Any] = None,
    ):
        """
        Add a fallback chain.
        
        Args:
            name: Chain name
            primary: Primary function to execute
            fallbacks: Ordered list of fallback providers
            timeout_seconds: Timeout for primary execution
            circuit_breaker: Optional circuit breaker
        """
        self._chains[name] = {
            'primary': primary,
            'fallbacks': fallbacks,
            'timeout': timeout_seconds,
            'circuit_breaker': circuit_breaker,
        }
        self._metrics[name] = {
            'primary_success': 0,
            'primary_failure': 0,
            'fallback_used': 0,
        }
    
    async def execute(
        self,
        chain_name: str,
        *args,
        force_fallback: bool = False,
        fallback_level: Optional[int] = None,
        **kwargs,
    ) -> FallbackResult:
        """
        Execute with fallback chain.
        
        Args:
            chain_name: Name of chain to use
            *args: Arguments for primary/fallback
            force_fallback: Skip primary and use fallback
            fallback_level: Specific fallback level to use
            **kwargs: Keyword arguments
            
        Returns:
            FallbackResult with execution details
        """
        if chain_name not in self._chains:
            raise ValueError(f"Unknown chain: {chain_name}")
        
        chain = self._chains[chain_name]
        start_time = time.time()
        
        # Check circuit breaker
        if chain.get('circuit_breaker') and not force_fallback:
            cb = chain['circuit_breaker']
            if hasattr(cb, 'state') and cb.state.value == 'open':
                return await self._execute_fallbacks(
                    chain, args, kwargs, start_time,
                    reason=FallbackReason.CIRCUIT_OPEN,
                    start_level=fallback_level or 0,
                )
        
        # Force fallback
        if force_fallback:
            return await self._execute_fallbacks(
                chain, args, kwargs, start_time,
                reason=FallbackReason.EXPLICIT,
                start_level=fallback_level or 0,
            )
        
        # Try primary
        try:
            primary = chain['primary']
            timeout = chain['timeout']
            
            if asyncio.iscoroutinefunction(primary):
                result = await asyncio.wait_for(
                    primary(*args, **kwargs),
                    timeout=timeout,
                )
            else:
                result = primary(*args, **kwargs)
            
            # Success
            latency = (time.time() - start_time) * 1000
            self._metrics[chain_name]['primary_success'] += 1
            
            return FallbackResult(
                value=result,
                used_fallback=False,
                fallback_level=0,
                provider_name="primary",
                latency_ms=latency,
            )
            
        except asyncio.TimeoutError:
            self._metrics[chain_name]['primary_failure'] += 1
            return await self._execute_fallbacks(
                chain, args, kwargs, start_time,
                reason=FallbackReason.PRIMARY_TIMEOUT,
            )
        except Exception as e:
            logger.warning(f"Primary execution failed: {e}")
            self._metrics[chain_name]['primary_failure'] += 1
            return await self._execute_fallbacks(
                chain, args, kwargs, start_time,
                reason=FallbackReason.PRIMARY_FAILED,
                exception=e,
            )
    
    async def _execute_fallbacks(
        self,
        chain: Dict[str, Any],
        args: tuple,
        kwargs: dict,
        start_time: float,
        reason: FallbackReason,
        start_level: int = 0,
        exception: Optional[Exception] = None,
    ) -> FallbackResult:
        """Execute fallback chain."""
        fallbacks = chain['fallbacks'][start_level:]
        
        for i, provider in enumerate(fallbacks):
            level = start_level + i + 1
            
            # Check provider health
            if not await provider.is_healthy():
                logger.debug(f"Fallback {provider.name} unhealthy, skipping")
                continue
            
            try:
                result = await provider.execute(*args, **kwargs)
                latency = (time.time() - start_time) * 1000
                
                return FallbackResult(
                    value=result,
                    used_fallback=True,
                    fallback_level=level,
                    fallback_reason=reason,
                    provider_name=provider.name,
                    latency_ms=latency,
                    metadata={'original_error': str(exception) if exception else None},
                )
            except Exception as e:
                logger.warning(f"Fallback {provider.name} failed: {e}")
                continue
        
        # All fallbacks failed
        raise RuntimeError(f"All fallbacks exhausted. Original error: {exception}")
    
    def get_metrics(self, chain_name: Optional[str] = None) -> Dict[str, Dict[str, int]]:
        """Get degradation metrics."""
        if chain_name:
            return {chain_name: self._metrics.get(chain_name, {})}
        return self._metrics.copy()


class DegradedResponse:
    """
    Builder for degraded response messages.
    
    Example:
        response = DegradedResponse.for_agent(
            "I'm experiencing some issues right now.",
            available_functions=["search"],
            unavailable_functions=["code_execution", "web_browse"],
        )
    """
    
    @staticmethod
    def for_agent(
        message: str,
        available_functions: Optional[List[str]] = None,
        unavailable_functions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Build degraded response for agent."""
        return {
            "status": "degraded",
            "message": message,
            "available_functions": available_functions or [],
            "unavailable_functions": unavailable_functions or [],
            "timestamp": time.time(),
        }
    
    @staticmethod
    def for_api(
        error: str,
        retry_after: Optional[int] = None,
        fallback_used: bool = False,
    ) -> Dict[str, Any]:
        """Build degraded response for API."""
        response = {
            "status": "degraded",
            "error": error,
            "fallback_used": fallback_used,
        }
        if retry_after:
            response["retry_after"] = retry_after
        return response


# Export public API
__all__ = [
    'DegradationManager',
    'FallbackProvider',
    'FallbackResult',
    'FallbackReason',
    'StaticFallbackProvider',
    'CacheFallbackProvider',
    'FunctionFallbackProvider',
    'LLMFallbackProvider',
    'DegradedResponse',
]
