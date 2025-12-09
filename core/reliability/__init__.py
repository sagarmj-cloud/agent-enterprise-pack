"""
Reliability Module
==================
Enterprise reliability patterns for AI agent endpoints.

Components:
- CircuitBreaker: Circuit breaker pattern for fault tolerance
- RetryHandler: Sophisticated retry with backoff strategies
- DegradationManager: Graceful degradation with fallbacks
- HealthChecker: Kubernetes-ready health probes
"""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitConfig,
    CircuitMetrics,
    CircuitOpenError,
    CircuitBreakerRegistry,
    CircuitPresets,
)

from .retry_handler import (
    RetryHandler,
    RetryResult,
    RetryOutcome,
    RetryConfig,
    BackoffStrategy,
    RetryPresets,
    with_retry,
    retry_on_exception,
)

from .graceful_degradation import (
    DegradationManager,
    FallbackProvider,
    FallbackResult,
    FallbackReason,
    StaticFallbackProvider,
    CacheFallbackProvider,
    FunctionFallbackProvider,
    LLMFallbackProvider,
    DegradedResponse,
)

from .health_checks import (
    HealthChecker,
    HealthCheckResult,
    HealthStatus,
    ComponentHealth,
    HealthCheckComponent,
    DatabaseHealthCheck,
    RedisHealthCheck,
    VertexAIHealthCheck,
    CustomHealthCheck,
    create_health_routes,
)


__all__ = [
    # Circuit Breaker
    'CircuitBreaker',
    'CircuitState',
    'CircuitConfig',
    'CircuitMetrics',
    'CircuitOpenError',
    'CircuitBreakerRegistry',
    'CircuitPresets',
    
    # Retry Handler
    'RetryHandler',
    'RetryResult',
    'RetryOutcome',
    'RetryConfig',
    'BackoffStrategy',
    'RetryPresets',
    'with_retry',
    'retry_on_exception',
    
    # Graceful Degradation
    'DegradationManager',
    'FallbackProvider',
    'FallbackResult',
    'FallbackReason',
    'StaticFallbackProvider',
    'CacheFallbackProvider',
    'FunctionFallbackProvider',
    'LLMFallbackProvider',
    'DegradedResponse',
    
    # Health Checks
    'HealthChecker',
    'HealthCheckResult',
    'HealthStatus',
    'ComponentHealth',
    'HealthCheckComponent',
    'DatabaseHealthCheck',
    'RedisHealthCheck',
    'VertexAIHealthCheck',
    'CustomHealthCheck',
    'create_health_routes',
]
