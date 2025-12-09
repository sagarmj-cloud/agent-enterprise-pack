"""
Tests for reliability module
=============================
"""

import pytest
import asyncio
from core.reliability import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    RetryHandler,
    BackoffStrategy,
    HealthChecker,
    CustomHealthCheck,
    RetryOutcome,
)


@pytest.mark.asyncio
class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    async def test_circuit_breaker_closed_state(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)

        # Use the protect decorator pattern
        @cb.protect
        async def success_func():
            return "success"

        result = await success_func()
        assert result == "success"
        assert cb.state.value == "closed"

    async def test_circuit_breaker_opens_on_failures(self):
        cb = CircuitBreaker(name="test", failure_threshold=2)

        @cb.protect
        async def failing_func():
            raise Exception("Test failure")

        # First failure
        with pytest.raises(Exception):
            await failing_func()

        # Second failure - should open circuit
        with pytest.raises(Exception):
            await failing_func()

        assert cb.state.value == "open"


class TestRetryHandler:
    """Tests for RetryHandler."""

    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self):
        retry = RetryHandler(max_attempts=3)

        async def success_func():
            return "success"

        # execute returns RetryResult, not the raw value
        result = await retry.execute(success_func)
        assert result.outcome == RetryOutcome.SUCCESS
        assert result.value == "success"

    @pytest.mark.asyncio
    async def test_retry_eventual_success(self):
        # Use base_delay instead of initial_delay
        retry = RetryHandler(max_attempts=3, base_delay=0.01)

        attempt_count = 0

        async def eventually_succeeds():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception("Not yet")
            return "success"

        result = await retry.execute(eventually_succeeds)
        assert result.outcome == RetryOutcome.SUCCESS
        assert result.value == "success"
        assert attempt_count == 3

    @pytest.mark.asyncio
    async def test_retry_max_attempts_exceeded(self):
        # Use base_delay instead of initial_delay
        retry = RetryHandler(max_attempts=2, base_delay=0.01)

        async def always_fails():
            raise Exception("Always fails")

        # execute returns RetryResult with EXHAUSTED outcome, doesn't raise
        result = await retry.execute(always_fails)
        assert result.outcome == RetryOutcome.EXHAUSTED
        assert result.exception is not None


@pytest.mark.asyncio
class TestHealthChecker:
    """Tests for HealthChecker."""
    
    async def test_health_check_healthy(self):
        checker = HealthChecker(version="1.0.0")
        
        checker.add_component(CustomHealthCheck(
            name="test",
            check_func=lambda: {"status": "healthy"}
        ))
        
        result = await checker.check_health()
        assert result.status.value == "healthy"
    
    async def test_health_check_startup_not_complete(self):
        checker = HealthChecker(version="1.0.0")
        # check_startup returns False when startup is not complete
        startup_complete = await checker.check_startup()
        assert startup_complete is False
    
    async def test_health_check_startup_complete(self):
        checker = HealthChecker(version="1.0.0")
        checker.mark_startup_complete()
        result = await checker.check_readiness()
        assert result.status.value == "healthy"

