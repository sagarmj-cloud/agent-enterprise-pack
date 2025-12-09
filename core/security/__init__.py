"""
Security Module
===============
Enterprise security components for AI agent endpoints.

Components:
- InputValidator: Input validation and sanitization
- PromptInjectionDetector: Multi-layer prompt injection detection
- RateLimiter: Multi-algorithm rate limiting
- AuthMiddleware: Multi-provider authentication
"""

from .input_validator import (
    InputValidator,
    ValidationResult,
    ValidationConfig,
    ValidationLevel,
    ThreatType,
    BatchValidator,
    PIIMasker,
    validate_input,
    sanitize,
)

from .prompt_injection import (
    PromptInjectionDetector,
    DetectionResult,
    DetectorConfig,
    DetectionSensitivity,
    AttackType,
    PatternDetectionLayer,
    HeuristicDetectionLayer,
    LLMDetectionLayer,
    detect_injection,
    analyze_injection,
)

from .rate_limiter import (
    RateLimiter,
    RateLimitResponse,
    RateLimitResult,
    RateLimitConfig,
    RateLimitAlgorithm,
    InMemoryBackend,
    RedisBackend,
    MultiTierRateLimiter,
    EndpointRateLimiter,
    create_rate_limit_middleware,
)

from .auth_middleware import (
    AuthMiddleware,
    AuthProvider,
    AuthResponse,
    AuthResult,
    AuthUser,
    JWTProvider,
    APIKeyProvider,
    GoogleIAPProvider,
    OAuth2Provider,
    SecurityMiddleware,
)


__all__ = [
    # Input Validator
    'InputValidator',
    'ValidationResult',
    'ValidationConfig',
    'ValidationLevel',
    'ThreatType',
    'BatchValidator',
    'PIIMasker',
    'validate_input',
    'sanitize',
    
    # Prompt Injection
    'PromptInjectionDetector',
    'DetectionResult',
    'DetectorConfig',
    'DetectionSensitivity',
    'AttackType',
    'PatternDetectionLayer',
    'HeuristicDetectionLayer',
    'LLMDetectionLayer',
    'detect_injection',
    'analyze_injection',
    
    # Rate Limiter
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
    
    # Auth Middleware
    'AuthMiddleware',
    'AuthProvider',
    'AuthResponse',
    'AuthResult',
    'AuthUser',
    'JWTProvider',
    'APIKeyProvider',
    'GoogleIAPProvider',
    'OAuth2Provider',
    'SecurityMiddleware',
]
