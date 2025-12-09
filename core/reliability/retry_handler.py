"""
Retry Handler
=============
Sophisticated retry mechanisms for transient failures.

Features:
- Exponential backoff with jitter
- Configurable retry conditions
- Timeout handling
- Callback hooks
- Service-specific presets
"""

import time
import asyncio
import random
import logging
from typing import Optional, Callable, TypeVar, Any, Set, Type, Union, Tuple
from dataclasses import dataclass, field
from functools import wraps
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BackoffStrategy(Enum):
    """Backoff strategies for retry delays."""
    CONSTANT = "constant"           # Same delay each time
    LINEAR = "linear"               # Linearly increasing delay
    EXPONENTIAL = "exponential"     # Exponentially increasing delay
    FIBONACCI = "fibonacci"         # Fibonacci sequence delays


class RetryOutcome(Enum):
    """Outcome of retry operation."""
    SUCCESS = "success"
    EXHAUSTED = "exhausted"
    TIMEOUT = "timeout"
    ABORTED = "aborted"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    backoff_multiplier: float = 2.0
    jitter: bool = True
    jitter_range: Tuple[float, float] = (0.8, 1.2)
    total_timeout: Optional[float] = None
    retryable_exceptions: Set[Type[Exception]] = field(default_factory=lambda: {Exception})
    non_retryable_exceptions: Set[Type[Exception]] = field(default_factory=set)
    retry_on_result: Optional[Callable[[Any], bool]] = None


@dataclass
class RetryResult:
    """Result of retry operation."""
    outcome: RetryOutcome
    value: Any = None
    exception: Optional[Exception] = None
    attempts: int = 0
    total_time: float = 0.0
    delays: list = field(default_factory=list)


class RetryHandler:
    """
    Retry handler with sophisticated backoff strategies.
    
    Example:
        # Basic usage
        @RetryHandler(max_attempts=3)
        async def call_api():
            return await api_client.request()
        
        # With exponential backoff
        @RetryHandler(
            max_attempts=5,
            base_delay=1.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_multiplier=2.0,
        )
        async def call_api():
            ...
        
        # Manual usage
        handler = RetryHandler(max_attempts=3)
        result = await handler.execute(call_api)
        if result.outcome == RetryOutcome.SUCCESS:
            print(result.value)
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_strategy: Union[BackoffStrategy, str] = BackoffStrategy.EXPONENTIAL,
        backoff_multiplier: float = 2.0,
        jitter: bool = True,
        jitter_range: Tuple[float, float] = (0.8, 1.2),
        total_timeout: Optional[float] = None,
        retryable_exceptions: Optional[Set[Type[Exception]]] = None,
        non_retryable_exceptions: Optional[Set[Type[Exception]]] = None,
        retry_on_result: Optional[Callable[[Any], bool]] = None,
        on_retry: Optional[Callable[[int, Exception, float], None]] = None,
        on_success: Optional[Callable[[Any, int], None]] = None,
        on_failure: Optional[Callable[[Exception, int], None]] = None,
    ):
        """
        Initialize retry handler.
        
        Args:
            max_attempts: Maximum number of attempts
            base_delay: Initial delay between retries
            max_delay: Maximum delay cap
            backoff_strategy: How delays increase
            backoff_multiplier: Multiplier for exponential/linear backoff
            jitter: Add randomness to delays
            jitter_range: Range for jitter multiplier
            total_timeout: Overall timeout for all attempts
            retryable_exceptions: Exceptions that trigger retry
            non_retryable_exceptions: Exceptions that never retry
            retry_on_result: Function to check if result should retry
            on_retry: Callback before each retry
            on_success: Callback on success
            on_failure: Callback on final failure
        """
        if isinstance(backoff_strategy, str):
            backoff_strategy = BackoffStrategy(backoff_strategy)
        
        self.config = RetryConfig(
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
            backoff_strategy=backoff_strategy,
            backoff_multiplier=backoff_multiplier,
            jitter=jitter,
            jitter_range=jitter_range,
            total_timeout=total_timeout,
            retryable_exceptions=retryable_exceptions or {Exception},
            non_retryable_exceptions=non_retryable_exceptions or set(),
            retry_on_result=retry_on_result,
        )
        
        self._on_retry = on_retry
        self._on_success = on_success
        self._on_failure = on_failure
        
        # Fibonacci sequence cache
        self._fib_cache = [0, 1]
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        strategy = self.config.backoff_strategy
        base = self.config.base_delay
        multiplier = self.config.backoff_multiplier
        
        if strategy == BackoffStrategy.CONSTANT:
            delay = base
        elif strategy == BackoffStrategy.LINEAR:
            delay = base * attempt
        elif strategy == BackoffStrategy.EXPONENTIAL:
            delay = base * (multiplier ** (attempt - 1))
        elif strategy == BackoffStrategy.FIBONACCI:
            # Extend fibonacci cache if needed
            while len(self._fib_cache) <= attempt:
                self._fib_cache.append(self._fib_cache[-1] + self._fib_cache[-2])
            delay = base * self._fib_cache[attempt]
        else:
            delay = base
        
        # Apply max delay cap
        delay = min(delay, self.config.max_delay)
        
        # Apply jitter
        if self.config.jitter:
            jitter_min, jitter_max = self.config.jitter_range
            delay *= random.uniform(jitter_min, jitter_max)
        
        return delay
    
    def _should_retry(self, exception: Exception) -> bool:
        """Determine if exception should trigger retry."""
        # Check non-retryable first
        if any(isinstance(exception, exc_type) for exc_type in self.config.non_retryable_exceptions):
            return False
        
        # Check retryable
        return any(isinstance(exception, exc_type) for exc_type in self.config.retryable_exceptions)
    
    async def execute(self, func: Callable[..., T], *args, **kwargs) -> RetryResult:
        """
        Execute function with retry logic.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            RetryResult with outcome and value
        """
        start_time = time.time()
        delays: list = []
        last_exception: Optional[Exception] = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            # Check total timeout
            if self.config.total_timeout:
                elapsed = time.time() - start_time
                if elapsed >= self.config.total_timeout:
                    return RetryResult(
                        outcome=RetryOutcome.TIMEOUT,
                        exception=last_exception,
                        attempts=attempt - 1,
                        total_time=elapsed,
                        delays=delays,
                    )
            
            try:
                # Execute function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Check result-based retry
                if self.config.retry_on_result and self.config.retry_on_result(result):
                    if attempt < self.config.max_attempts:
                        delay = self._calculate_delay(attempt)
                        delays.append(delay)
                        logger.debug(f"Retry {attempt}/{self.config.max_attempts} due to result check, delay={delay:.2f}s")
                        await asyncio.sleep(delay)
                        continue
                
                # Success
                total_time = time.time() - start_time
                if self._on_success:
                    try:
                        self._on_success(result, attempt)
                    except Exception as e:
                        logger.error(f"Success callback error: {e}")
                
                return RetryResult(
                    outcome=RetryOutcome.SUCCESS,
                    value=result,
                    attempts=attempt,
                    total_time=total_time,
                    delays=delays,
                )
                
            except Exception as e:
                last_exception = e
                
                # Check if should retry
                if not self._should_retry(e):
                    total_time = time.time() - start_time
                    return RetryResult(
                        outcome=RetryOutcome.ABORTED,
                        exception=e,
                        attempts=attempt,
                        total_time=total_time,
                        delays=delays,
                    )
                
                # Calculate delay for next attempt
                if attempt < self.config.max_attempts:
                    delay = self._calculate_delay(attempt)
                    delays.append(delay)
                    
                    logger.warning(
                        f"Retry {attempt}/{self.config.max_attempts} after {type(e).__name__}: {str(e)[:100]}, "
                        f"delay={delay:.2f}s"
                    )
                    
                    if self._on_retry:
                        try:
                            self._on_retry(attempt, e, delay)
                        except Exception as callback_error:
                            logger.error(f"Retry callback error: {callback_error}")
                    
                    await asyncio.sleep(delay)
        
        # Exhausted retries
        total_time = time.time() - start_time
        if self._on_failure:
            try:
                self._on_failure(last_exception, self.config.max_attempts)
            except Exception as e:
                logger.error(f"Failure callback error: {e}")
        
        return RetryResult(
            outcome=RetryOutcome.EXHAUSTED,
            exception=last_exception,
            attempts=self.config.max_attempts,
            total_time=total_time,
            delays=delays,
        )
    
    def __call__(self, func: Callable) -> Callable:
        """
        Decorator for retry handling.
        
        Example:
            @RetryHandler(max_attempts=3)
            async def my_function():
                ...
        """
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await self.execute(func, *args, **kwargs)
            if result.outcome == RetryOutcome.SUCCESS:
                return result.value
            raise result.exception or RuntimeError("Retry failed without exception")
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(self.execute(func, *args, **kwargs))
            if result.outcome == RetryOutcome.SUCCESS:
                return result.value
            raise result.exception or RuntimeError("Retry failed without exception")
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper


class RetryPresets:
    """Preset configurations for common services."""
    
    @staticmethod
    def vertex_ai() -> RetryHandler:
        """
        Preset for Vertex AI API calls.
        
        Handles: ResourceExhausted (429), Internal (500), Unavailable (503)
        """
        return RetryHandler(
            max_attempts=5,
            base_delay=1.0,
            max_delay=60.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_multiplier=2.0,
            jitter=True,
            total_timeout=300.0,  # 5 minutes total
        )
    
    @staticmethod
    def http_api() -> RetryHandler:
        """Preset for generic HTTP API calls."""
        return RetryHandler(
            max_attempts=3,
            base_delay=0.5,
            max_delay=10.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_multiplier=2.0,
            jitter=True,
        )
    
    @staticmethod
    def database() -> RetryHandler:
        """Preset for database operations."""
        return RetryHandler(
            max_attempts=3,
            base_delay=0.1,
            max_delay=2.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_multiplier=2.0,
            jitter=True,
            total_timeout=10.0,
        )
    
    @staticmethod
    def message_queue() -> RetryHandler:
        """Preset for message queue operations."""
        return RetryHandler(
            max_attempts=5,
            base_delay=1.0,
            max_delay=30.0,
            backoff_strategy=BackoffStrategy.FIBONACCI,
            jitter=True,
        )
    
    @staticmethod
    def idempotent_operation() -> RetryHandler:
        """Preset for idempotent operations (more aggressive retry)."""
        return RetryHandler(
            max_attempts=10,
            base_delay=0.5,
            max_delay=30.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_multiplier=1.5,
            jitter=True,
            total_timeout=120.0,
        )


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
    **kwargs,
) -> Callable:
    """
    Convenience decorator for retry handling.
    
    Example:
        @with_retry(max_attempts=5)
        async def call_api():
            ...
    """
    handler = RetryHandler(
        max_attempts=max_attempts,
        base_delay=base_delay,
        backoff_strategy=backoff_strategy,
        **kwargs,
    )
    return handler


def retry_on_exception(
    *exception_types: Type[Exception],
    max_attempts: int = 3,
    **kwargs,
) -> Callable:
    """
    Retry only on specific exception types.
    
    Example:
        @retry_on_exception(ConnectionError, TimeoutError, max_attempts=5)
        async def call_api():
            ...
    """
    handler = RetryHandler(
        max_attempts=max_attempts,
        retryable_exceptions=set(exception_types),
        **kwargs,
    )
    return handler


# Export public API
__all__ = [
    'RetryHandler',
    'RetryResult',
    'RetryOutcome',
    'RetryConfig',
    'BackoffStrategy',
    'RetryPresets',
    'with_retry',
    'retry_on_exception',
]
