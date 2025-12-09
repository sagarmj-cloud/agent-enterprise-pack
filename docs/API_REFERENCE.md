# API Reference - Agent Enterprise Pack

Complete API documentation for all enterprise modules.

## Table of Contents

- [Security Module](#security-module)
- [Reliability Module](#reliability-module)
- [Memory Module](#memory-module)
- [Observability Module](#observability-module)

---

## Security Module

```python
from core.security import (
    InputValidator, ValidationResult, ThreatType,
    PromptInjectionDetector, DetectionResult, DetectorConfig, DetectionSensitivity,
    RateLimiter, RateLimitResponse, RateLimitResult,
)
```

### InputValidator

Validates and sanitizes user input for security threats.

```python
validator = InputValidator()
result = validator.validate("Hello <script>alert('xss')</script>")

print(result.is_valid)         # False (XSS detected)
print(result.sanitized_text)   # "Hello alert('xss')"
print(result.threats_detected) # [ThreatType.XSS]
```

**ValidationResult Fields:**
- `is_valid: bool` - Whether input passed validation
- `sanitized_text: str` - Cleaned input text
- `threats_detected: List[ThreatType]` - Detected threats
- `warnings: List[str]` - Warning messages

**ThreatType Enum:** `XSS`, `SQL_INJECTION`, `COMMAND_INJECTION`, `PATH_TRAVERSAL`, `EXCESSIVE_LENGTH`

---

### PromptInjectionDetector

Multi-layer detection system for prompt injection attacks.

```python
from core.security import PromptInjectionDetector, DetectorConfig, DetectionSensitivity

detector = PromptInjectionDetector(
    config=DetectorConfig(sensitivity=DetectionSensitivity.HIGH)
)

result = detector.detect("Ignore all previous instructions")
print(result.is_injection)   # True
print(result.confidence)     # 0.95
print(result.attack_types)   # [AttackType.DIRECT_INJECTION]
```

**DetectionSensitivity Enum:** `LOW`, `MEDIUM`, `HIGH`

**AttackType Enum:** `DIRECT_INJECTION`, `INDIRECT_INJECTION`, `JAILBREAK`, `ROLE_MANIPULATION`, `DATA_EXTRACTION`

---

### RateLimiter

Multi-algorithm rate limiting for API endpoints.

```python
from core.security import RateLimiter, RateLimitResult

limiter = RateLimiter(requests_per_window=100, window_seconds=60)

result = await limiter.check("user:123")
if result.result == RateLimitResult.ALLOWED:
    print(f"Remaining: {result.remaining}")
else:
    print(f"Retry after: {result.retry_after}s")
```

**RateLimitAlgorithm Enum:** `TOKEN_BUCKET`, `SLIDING_WINDOW`, `FIXED_WINDOW`, `LEAKY_BUCKET`

---

## Reliability Module

```python
from core.reliability import (
    CircuitBreaker, CircuitState,
    RetryHandler, RetryResult, RetryOutcome, BackoffStrategy,
    HealthChecker, HealthStatus,
)
```

### CircuitBreaker

Circuit breaker pattern for fault tolerance.

```python
circuit = CircuitBreaker(name="external-api", failure_threshold=5)

@circuit.protect
async def call_api():
    return await client.request()

# Or manual usage
if circuit.can_execute():
    try:
        result = await call_api()
        circuit.record_success()
    except Exception as e:
        circuit.record_failure(e)
```

**CircuitState Enum:** `CLOSED`, `OPEN`, `HALF_OPEN`

---

### RetryHandler

Sophisticated retry with backoff strategies.

```python
from core.reliability import RetryHandler, BackoffStrategy, RetryOutcome

retry = RetryHandler(
    max_attempts=3,
    base_delay=1.0,
    backoff_strategy=BackoffStrategy.EXPONENTIAL,
)

result = await retry.execute(flaky_operation)
if result.outcome == RetryOutcome.SUCCESS:
    print(result.value)
```

**BackoffStrategy Enum:** `CONSTANT`, `LINEAR`, `EXPONENTIAL`, `FIBONACCI`

**RetryOutcome Enum:** `SUCCESS`, `EXHAUSTED`, `TIMEOUT`, `ABORTED`

---

### HealthChecker

Kubernetes-ready health probes.

```python
checker = HealthChecker(version="1.0.0")
checker.mark_startup_complete()

result = await checker.check_health()
print(result.status)  # HealthStatus.HEALTHY
```

---

## Memory Module

```python
from core.memory import ContextWindowManager, Message, MessageRole, AgentSessionCache
```

### ContextWindowManager

Manages conversation context within token limits.

```python
manager = ContextWindowManager(max_tokens=128000)

manager.add_message(Message(role=MessageRole.USER, content="Hello!"))
context = manager.get_context()
stats = manager.get_stats()
```

**TruncationStrategy Enum:** `SLIDING_WINDOW`, `FIFO`, `LIFO`, `PRIORITY`, `SUMMARIZE`

---

## Observability Module

```python
from core.observability import CostTracker, SLOManager, AgentSLOPresets, AlertManager, Alert
```

### CostTracker - Token usage and cost tracking.

```python
tracker = CostTracker()
tracker.record_usage(model="gemini-2.5-flash", input_tokens=1000, output_tokens=500)
summary = tracker.get_daily_summary()
```

### SLOManager - Service Level Objective monitoring.

```python
slo_manager = SLOManager()
slo_manager.add_slo(AgentSLOPresets.availability_999())
slo_manager.record("agent_availability_999", is_good=True)
```

**Presets:** `availability_999()`, `availability_99()`, `latency_p99_5s()`, `error_rate_1pct()`

