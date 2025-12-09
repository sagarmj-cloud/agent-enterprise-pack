"""
Agent Enterprise Pack - Main Entry Point
=========================================
Demonstrates integration of all enterprise components.
"""

import asyncio
import logging
import os
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# Import enterprise pack components
from core.security import (
    SecurityMiddleware,
    InputValidator,
    PromptInjectionDetector,
    RateLimiter,
    JWTProvider,
    APIKeyProvider,
)
from core.reliability import (
    CircuitBreakerRegistry,
    RetryHandler,
    RetryPresets,
    DegradationManager,
    HealthChecker,
    CustomHealthCheck,
)
from core.memory import (
    ContextWindowManager,
    AgentSessionCache,
    TruncationStrategy,
)
from core.observability import (
    SLOManager,
    CostTracker,
    AlertManager,
    SlackChannel,
    AgentSLOPresets,
    Alert,
    AlertSeverity,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

class Config:
    """Application configuration."""
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8080"))
    
    # Security
    JWT_SECRET: str = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
    
    # Caching
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    CACHE_BACKEND: str = os.getenv("CACHE_BACKEND", "memory")
    
    # Alerting
    SLACK_WEBHOOK: Optional[str] = os.getenv("SLACK_WEBHOOK_URL")
    
    # Agent
    PROJECT_ID: str = os.getenv("GOOGLE_CLOUD_PROJECT", "your-project")
    LOCATION: str = os.getenv("LOCATION", "us-central1")
    MODEL: str = os.getenv("MODEL", "gemini-1.5-pro")


config = Config()


# =============================================================================
# Initialize Components
# =============================================================================

# Security
input_validator = InputValidator()
prompt_detector = PromptInjectionDetector()
rate_limiter = RateLimiter(
    requests_per_window=config.RATE_LIMIT_REQUESTS,
    window_seconds=config.RATE_LIMIT_WINDOW,
    backend=config.CACHE_BACKEND,
    redis_url=config.REDIS_URL,
)

# Auth providers
jwt_provider = JWTProvider(secret_key=config.JWT_SECRET)
api_key_provider = APIKeyProvider(
    valid_keys={
        "demo-api-key": {"user_id": "demo-user", "roles": ["user"]},
    }
)

# Reliability
circuit_registry = CircuitBreakerRegistry()
retry_handler = RetryPresets.vertex_ai()
health_checker = HealthChecker(version="1.0.0")

# Add custom health check
health_checker.add_component(CustomHealthCheck(
    name="agent_ready",
    check_func=lambda: {"status": "healthy", "model": config.MODEL},
))

# Memory
session_cache = AgentSessionCache(
    ttl_seconds=3600,
    backend=config.CACHE_BACKEND,
    redis_url=config.REDIS_URL,
)
context_manager = ContextWindowManager(
    max_tokens=1000000,
    target_tokens=800000,
    truncation_strategy=TruncationStrategy.SLIDING_WINDOW,
)

# Observability
slo_manager = SLOManager()
slo_manager.add_slo(AgentSLOPresets.availability_999())
slo_manager.add_slo(AgentSLOPresets.latency_p99(5000))

cost_tracker = CostTracker()

alert_manager = AlertManager()
if config.SLACK_WEBHOOK:
    alert_manager.add_channel(SlackChannel(webhook_url=config.SLACK_WEBHOOK))


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="Agent Enterprise Pack Demo",
    description="Enterprise-grade AI agent with security, reliability, and observability",
    version="1.0.0",
)

# Include health check routes
app.include_router(health_checker.create_fastapi_routes())


@app.middleware("http")
async def enterprise_middleware(request: Request, call_next):
    """Combined enterprise middleware."""
    import time
    start_time = time.time()
    
    # Skip middleware for health endpoints
    if request.url.path in ["/health", "/ready", "/live", "/livez", "/readyz"]:
        return await call_next(request)
    
    # Rate limiting
    client_id = request.client.host if request.client else "unknown"
    rate_result = await rate_limiter.check(client_id)
    
    from core.security.rate_limiter import RateLimitResult
    if rate_result.result == RateLimitResult.DENIED:
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded", "retry_after": rate_result.retry_after},
            headers=rate_limiter.get_headers(rate_result),
        )
    
    # Process request
    response = await call_next(request)
    
    # Track latency for SLO
    latency_ms = (time.time() - start_time) * 1000
    slo_manager.record("agent_latency_p99", value=latency_ms)
    slo_manager.record("agent_availability_999", is_good=response.status_code < 500)
    
    # Add rate limit headers
    for k, v in rate_limiter.get_headers(rate_result).items():
        response.headers[k] = v
    
    return response


@app.post("/chat")
async def chat(request: Request):
    """Chat endpoint with full enterprise stack."""
    try:
        body = await request.json()
        message = body.get("message", "")
        session_id = body.get("session_id")
        user_id = body.get("user_id", "anonymous")
        
        # Input validation
        validation_result = input_validator.validate(message)
        if not validation_result.is_valid:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid input", "details": validation_result.warnings},
            )
        
        # Prompt injection detection
        injection_result = prompt_detector.detect(validation_result.sanitized_text)
        if injection_result.is_injection:
            logger.warning(f"Prompt injection detected: {injection_result.explanation}")
            return JSONResponse(
                status_code=400,
                content={"error": "Potentially harmful input detected"},
            )
        
        # Get or create session
        if session_id:
            session = await session_cache.get_session(session_id)
            if not session:
                session_id = await session_cache.create_session(user_id)
        else:
            session_id = await session_cache.create_session(user_id)
        
        # Add message to session
        await session_cache.add_message(session_id, {
            "role": "user",
            "content": validation_result.sanitized_text,
        })
        
        # Simulate agent response (replace with actual ADK agent call)
        # In production, wrap this with circuit breaker and retry
        agent_response = f"I received your message: {validation_result.sanitized_text[:100]}..."
        
        # Track token usage
        input_tokens = len(message) // 4  # Approximate
        output_tokens = len(agent_response) // 4
        cost_tracker.record_usage(
            model=config.MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            session_id=session_id,
            user_id=user_id,
        )
        
        # Add response to session
        await session_cache.add_message(session_id, {
            "role": "assistant",
            "content": agent_response,
        })
        
        return {
            "response": agent_response,
            "session_id": session_id,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        }
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        
        # Record error for SLO
        slo_manager.record("agent_availability_999", is_good=False)
        
        # Send alert for critical errors
        await alert_manager.send_alert(Alert(
            name="chat_error",
            severity=AlertSeverity.ERROR,
            summary="Chat endpoint error",
            description=str(e),
            source="agent",
        ))
        
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/metrics")
async def metrics():
    """Get agent metrics."""
    return {
        "slo_status": {
            name: {
                "current_value": status.current_value,
                "target": status.target,
                "compliance": status.compliance.value,
                "error_budget_remaining": status.error_budget_remaining,
            }
            for name, status in slo_manager.get_all_statuses().items()
        },
        "cost_summary": cost_tracker.get_daily_summary().__dict__,
        "session_cache_stats": session_cache.get_stats().__dict__,
        "rate_limiter_stats": {
            "algorithm": rate_limiter.algorithm.value,
            "requests_per_window": rate_limiter.requests_per_window,
        },
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Agent Enterprise Pack",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "chat": "/chat",
            "health": "/health",
            "ready": "/ready",
            "metrics": "/metrics",
        },
    }


# =============================================================================
# Run
# =============================================================================

def main():
    """Run the application."""
    health_checker.mark_startup_complete()
    uvicorn.run(
        app,
        host=config.HOST,
        port=config.PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
