"""
Circuit Breaker
===============
Circuit breaker pattern implementation for fault tolerance.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Circuit tripped, requests fail fast
- HALF_OPEN: Testing if service recovered

Features:
- Configurable failure thresholds
- Automatic recovery testing
- Metrics and callbacks
- Registry for managing multiple circuits
"""

import time
import asyncio
import logging
from typing import Optional, Dict, Any, Callable, List, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import threading
from collections import deque

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5        # Failures before opening
    success_threshold: int = 3        # Successes to close from half-open
    timeout_seconds: float = 30.0     # Time in open state before half-open
    failure_rate_threshold: float = 0.5  # Alternative: failure rate threshold
    window_size: int = 10             # Rolling window size for failure rate
    excluded_exceptions: tuple = ()   # Exceptions that don't count as failures


@dataclass
class CircuitMetrics:
    """Circuit breaker metrics."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_changes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    time_in_open: float = 0.0
    current_state: CircuitState = CircuitState.CLOSED


class CircuitBreaker:
    """
    Circuit breaker for protecting external service calls.
    
    Example:
        circuit = CircuitBreaker(name="vertex-ai", failure_threshold=5)
        
        @circuit.protect
        async def call_vertex_ai(prompt: str):
            return await vertex_client.generate(prompt)
        
        # Or use manually
        if circuit.can_execute():
            try:
                result = await call_vertex_ai(prompt)
                circuit.record_success()
            except Exception as e:
                circuit.record_failure(e)
                raise
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 3,
        timeout_seconds: float = 30.0,
        failure_rate_threshold: Optional[float] = None,
        window_size: int = 10,
        excluded_exceptions: tuple = (),
        on_state_change: Optional[Callable[[CircuitState, CircuitState], None]] = None,
        on_failure: Optional[Callable[[Exception], None]] = None,
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Circuit name for identification
            failure_threshold: Number of failures to trip circuit
            success_threshold: Successes needed to close from half-open
            timeout_seconds: Time before testing recovery
            failure_rate_threshold: Alternative failure rate threshold
            window_size: Size of rolling window
            excluded_exceptions: Exceptions that don't count as failures
            on_state_change: Callback when state changes
            on_failure: Callback on failure
        """
        self.name = name
        self.config = CircuitConfig(
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout_seconds=timeout_seconds,
            failure_rate_threshold=failure_rate_threshold or 0.5,
            window_size=window_size,
            excluded_exceptions=excluded_exceptions,
        )
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._open_time: Optional[float] = None
        
        # Rolling window for failure rate calculation
        self._results: deque = deque(maxlen=window_size)
        
        # Callbacks
        self._on_state_change = on_state_change
        self._on_failure = on_failure
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Metrics
        self._metrics = CircuitMetrics()
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            self._check_state_transition()
            return self._state
    
    @property
    def metrics(self) -> CircuitMetrics:
        """Get current metrics."""
        with self._lock:
            self._metrics.current_state = self._state
            return self._metrics
    
    def _check_state_transition(self):
        """Check and perform state transitions."""
        if self._state == CircuitState.OPEN:
            if self._open_time and time.time() - self._open_time >= self.config.timeout_seconds:
                self._transition_to(CircuitState.HALF_OPEN)
    
    def _transition_to(self, new_state: CircuitState):
        """Transition to new state."""
        old_state = self._state
        if old_state == new_state:
            return
        
        self._state = new_state
        self._metrics.state_changes += 1
        
        if new_state == CircuitState.OPEN:
            self._open_time = time.time()
        elif new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
            if self._open_time:
                self._metrics.time_in_open += time.time() - self._open_time
            self._open_time = None
        elif new_state == CircuitState.HALF_OPEN:
            self._success_count = 0
        
        logger.info(f"Circuit '{self.name}' state change: {old_state.value} -> {new_state.value}")
        
        if self._on_state_change:
            try:
                self._on_state_change(old_state, new_state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")
    
    def can_execute(self) -> bool:
        """Check if request can be executed."""
        with self._lock:
            self._check_state_transition()
            
            if self._state == CircuitState.CLOSED:
                return True
            elif self._state == CircuitState.HALF_OPEN:
                return True  # Allow test request
            else:  # OPEN
                self._metrics.rejected_calls += 1
                return False
    
    def record_success(self):
        """Record successful call."""
        with self._lock:
            self._metrics.total_calls += 1
            self._metrics.successful_calls += 1
            self._metrics.last_success_time = time.time()
            self._results.append(True)
            
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0  # Reset on success
    
    def record_failure(self, exception: Optional[Exception] = None):
        """Record failed call."""
        # Check if exception should be excluded
        if exception and isinstance(exception, self.config.excluded_exceptions):
            return
        
        with self._lock:
            self._metrics.total_calls += 1
            self._metrics.failed_calls += 1
            self._metrics.last_failure_time = time.time()
            self._last_failure_time = time.time()
            self._results.append(False)
            
            if self._on_failure and exception:
                try:
                    self._on_failure(exception)
                except Exception as e:
                    logger.error(f"Failure callback error: {e}")
            
            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open trips back to open
                self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                
                # Check failure threshold
                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
                # Also check failure rate if configured
                elif len(self._results) >= self.config.window_size:
                    failure_rate = sum(1 for r in self._results if not r) / len(self._results)
                    if failure_rate >= self.config.failure_rate_threshold:
                        self._transition_to(CircuitState.OPEN)
    
    def reset(self):
        """Reset circuit to closed state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._open_time = None
            self._results.clear()
    
    def protect(self, func: Callable) -> Callable:
        """
        Decorator to protect a function with circuit breaker.
        
        Example:
            @circuit.protect
            async def call_api():
                ...
        """
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not self.can_execute():
                raise CircuitOpenError(f"Circuit '{self.name}' is open")
            
            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return result
            except self.config.excluded_exceptions:
                # Don't count excluded exceptions as failures
                raise
            except Exception as e:
                self.record_failure(e)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not self.can_execute():
                raise CircuitOpenError(f"Circuit '{self.name}' is open")
            
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except self.config.excluded_exceptions:
                raise
            except Exception as e:
                self.record_failure(e)
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper


class CircuitOpenError(Exception):
    """Raised when circuit is open and request is rejected."""
    pass


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.
    
    Example:
        registry = CircuitBreakerRegistry()
        
        # Get or create circuit
        vertex_circuit = registry.get_or_create(
            "vertex-ai",
            failure_threshold=5,
            timeout_seconds=60,
        )
        
        # Use with decorator
        @registry.protect("vertex-ai")
        async def call_vertex_ai():
            ...
        
        # Get all metrics
        metrics = registry.get_all_metrics()
    """
    
    def __init__(self, default_config: Optional[CircuitConfig] = None):
        """Initialize registry with optional default config."""
        self.default_config = default_config or CircuitConfig()
        self._circuits: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
    
    def get_or_create(
        self,
        name: str,
        failure_threshold: Optional[int] = None,
        success_threshold: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        **kwargs,
    ) -> CircuitBreaker:
        """Get existing circuit or create new one."""
        with self._lock:
            if name not in self._circuits:
                self._circuits[name] = CircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold or self.default_config.failure_threshold,
                    success_threshold=success_threshold or self.default_config.success_threshold,
                    timeout_seconds=timeout_seconds or self.default_config.timeout_seconds,
                    **kwargs,
                )
            return self._circuits[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit by name."""
        return self._circuits.get(name)
    
    def protect(self, name: str, **circuit_kwargs) -> Callable:
        """
        Decorator to protect function with named circuit.
        
        Example:
            @registry.protect("external-api")
            async def call_external_api():
                ...
        """
        def decorator(func: Callable) -> Callable:
            circuit = self.get_or_create(name, **circuit_kwargs)
            return circuit.protect(func)
        return decorator
    
    def get_all_metrics(self) -> Dict[str, CircuitMetrics]:
        """Get metrics for all circuits."""
        return {name: circuit.metrics for name, circuit in self._circuits.items()}
    
    def get_open_circuits(self) -> List[str]:
        """Get names of all open circuits."""
        return [name for name, circuit in self._circuits.items() if circuit.state == CircuitState.OPEN]
    
    def reset_all(self):
        """Reset all circuits to closed state."""
        for circuit in self._circuits.values():
            circuit.reset()
    
    def remove(self, name: str):
        """Remove circuit from registry."""
        with self._lock:
            self._circuits.pop(name, None)


# Presets for common services
class CircuitPresets:
    """Preset configurations for common services."""
    
    @staticmethod
    def vertex_ai() -> Dict[str, Any]:
        """Preset for Vertex AI calls."""
        return {
            'failure_threshold': 5,
            'success_threshold': 3,
            'timeout_seconds': 60,
            'excluded_exceptions': (ValueError, TypeError),
        }
    
    @staticmethod
    def external_api() -> Dict[str, Any]:
        """Preset for external API calls."""
        return {
            'failure_threshold': 3,
            'success_threshold': 2,
            'timeout_seconds': 30,
        }
    
    @staticmethod
    def database() -> Dict[str, Any]:
        """Preset for database calls."""
        return {
            'failure_threshold': 5,
            'success_threshold': 3,
            'timeout_seconds': 10,
        }


# Export public API
__all__ = [
    'CircuitBreaker',
    'CircuitState',
    'CircuitConfig',
    'CircuitMetrics',
    'CircuitOpenError',
    'CircuitBreakerRegistry',
    'CircuitPresets',
]
