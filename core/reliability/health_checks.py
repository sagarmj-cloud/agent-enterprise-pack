"""
Health Checks
=============
Kubernetes-ready health check system for AI agents.

Probes:
- Liveness: Is the process running?
- Readiness: Can the service handle requests?
- Startup: Has the service finished initializing?

Features:
- Pluggable health check components
- Configurable timeouts
- Aggregated health status
- FastAPI/Flask integration
"""

import time
import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    name: str
    status: HealthStatus
    message: Optional[str] = None
    latency_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_check: float = field(default_factory=time.time)


@dataclass
class HealthCheckResult:
    """Aggregated health check result."""
    status: HealthStatus
    components: Dict[str, ComponentHealth]
    timestamp: float = field(default_factory=time.time)
    version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        return {
            "status": self.status.value,
            "timestamp": self.timestamp,
            "version": self.version,
            "components": {
                name: {
                    "status": comp.status.value,
                    "message": comp.message,
                    "latency_ms": comp.latency_ms,
                    "metadata": comp.metadata,
                }
                for name, comp in self.components.items()
            },
        }


class HealthCheckComponent(ABC):
    """Abstract base class for health check components."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Component name."""
        pass
    
    @abstractmethod
    async def check(self) -> ComponentHealth:
        """Perform health check."""
        pass


class DatabaseHealthCheck(HealthCheckComponent):
    """
    Database health check component.
    
    Example:
        db_check = DatabaseHealthCheck(
            "postgres",
            connection_func=lambda: db.execute("SELECT 1"),
        )
    """
    
    def __init__(
        self,
        name: str,
        connection_func: Callable,
        timeout_seconds: float = 5.0,
    ):
        """
        Initialize database health check.
        
        Args:
            name: Component name
            connection_func: Function to test connection
            timeout_seconds: Timeout for check
        """
        self._name = name
        self._connection_func = connection_func
        self._timeout = timeout_seconds
    
    @property
    def name(self) -> str:
        return self._name
    
    async def check(self) -> ComponentHealth:
        """Check database connection."""
        start = time.time()
        try:
            if asyncio.iscoroutinefunction(self._connection_func):
                await asyncio.wait_for(self._connection_func(), timeout=self._timeout)
            else:
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, self._connection_func),
                    timeout=self._timeout,
                )
            
            latency = (time.time() - start) * 1000
            return ComponentHealth(
                name=self._name,
                status=HealthStatus.HEALTHY,
                message="Connection successful",
                latency_ms=latency,
            )
        except asyncio.TimeoutError:
            return ComponentHealth(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message=f"Connection timeout after {self._timeout}s",
            )
        except Exception as e:
            return ComponentHealth(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message=f"Connection failed: {str(e)}",
            )


class RedisHealthCheck(HealthCheckComponent):
    """Redis health check component."""
    
    def __init__(
        self,
        name: str = "redis",
        redis_client: Any = None,
        timeout_seconds: float = 2.0,
    ):
        """Initialize Redis health check."""
        self._name = name
        self._client = redis_client
        self._timeout = timeout_seconds
    
    @property
    def name(self) -> str:
        return self._name
    
    async def check(self) -> ComponentHealth:
        """Check Redis connection."""
        if not self._client:
            return ComponentHealth(
                name=self._name,
                status=HealthStatus.UNKNOWN,
                message="Redis client not configured",
            )
        
        start = time.time()
        try:
            await asyncio.wait_for(self._client.ping(), timeout=self._timeout)
            latency = (time.time() - start) * 1000
            return ComponentHealth(
                name=self._name,
                status=HealthStatus.HEALTHY,
                message="Redis responding",
                latency_ms=latency,
            )
        except Exception as e:
            return ComponentHealth(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis error: {str(e)}",
            )


class VertexAIHealthCheck(HealthCheckComponent):
    """Vertex AI service health check."""
    
    def __init__(
        self,
        name: str = "vertex-ai",
        project_id: Optional[str] = None,
        location: str = "us-central1",
        timeout_seconds: float = 10.0,
    ):
        """Initialize Vertex AI health check."""
        self._name = name
        self._project_id = project_id
        self._location = location
        self._timeout = timeout_seconds
    
    @property
    def name(self) -> str:
        return self._name
    
    async def check(self) -> ComponentHealth:
        """Check Vertex AI availability."""
        start = time.time()
        try:
            # Simple check - verify we can import and access Vertex AI
            from google.cloud import aiplatform
            
            if self._project_id:
                aiplatform.init(project=self._project_id, location=self._location)
            
            latency = (time.time() - start) * 1000
            return ComponentHealth(
                name=self._name,
                status=HealthStatus.HEALTHY,
                message="Vertex AI SDK initialized",
                latency_ms=latency,
                metadata={"location": self._location},
            )
        except Exception as e:
            return ComponentHealth(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message=f"Vertex AI error: {str(e)}",
            )


class CustomHealthCheck(HealthCheckComponent):
    """
    Custom health check from a function.
    
    Example:
        custom_check = CustomHealthCheck(
            "custom",
            check_func=lambda: {"status": "ok", "version": "1.0"},
        )
    """
    
    def __init__(
        self,
        name: str,
        check_func: Callable[[], Union[bool, Dict[str, Any]]],
        timeout_seconds: float = 5.0,
    ):
        """
        Initialize custom health check.
        
        Args:
            name: Component name
            check_func: Function returning bool or dict with health info
            timeout_seconds: Timeout for check
        """
        self._name = name
        self._check_func = check_func
        self._timeout = timeout_seconds
    
    @property
    def name(self) -> str:
        return self._name
    
    async def check(self) -> ComponentHealth:
        """Run custom health check."""
        start = time.time()
        try:
            if asyncio.iscoroutinefunction(self._check_func):
                result = await asyncio.wait_for(self._check_func(), timeout=self._timeout)
            else:
                result = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, self._check_func),
                    timeout=self._timeout,
                )
            
            latency = (time.time() - start) * 1000
            
            if isinstance(result, bool):
                return ComponentHealth(
                    name=self._name,
                    status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                    latency_ms=latency,
                )
            elif isinstance(result, dict):
                status = result.get('status', 'healthy')
                if isinstance(status, str):
                    status = HealthStatus(status) if status in [s.value for s in HealthStatus] else HealthStatus.HEALTHY
                return ComponentHealth(
                    name=self._name,
                    status=status,
                    message=result.get('message'),
                    latency_ms=latency,
                    metadata={k: v for k, v in result.items() if k not in ['status', 'message']},
                )
            else:
                return ComponentHealth(
                    name=self._name,
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency,
                )
        except Exception as e:
            return ComponentHealth(
                name=self._name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )


class HealthChecker:
    """
    Main health checker with multiple components.
    
    Example:
        checker = HealthChecker(version="1.0.0")
        checker.add_component(DatabaseHealthCheck("db", db.ping))
        checker.add_component(RedisHealthCheck("cache", redis_client))
        
        # Check health
        result = await checker.check_health()
        
        # FastAPI integration
        app.include_router(checker.create_fastapi_routes())
    """
    
    def __init__(
        self,
        version: Optional[str] = None,
        fail_on_degraded: bool = False,
    ):
        """
        Initialize health checker.
        
        Args:
            version: Application version
            fail_on_degraded: Whether degraded status counts as unhealthy
        """
        self.version = version
        self.fail_on_degraded = fail_on_degraded
        self._components: Dict[str, HealthCheckComponent] = {}
        self._startup_complete = False
        self._startup_time: Optional[float] = None
    
    def add_component(self, component: HealthCheckComponent):
        """Add a health check component."""
        self._components[component.name] = component
    
    def mark_startup_complete(self):
        """Mark startup as complete."""
        self._startup_complete = True
        self._startup_time = time.time()
    
    async def check_health(self, include_details: bool = True) -> HealthCheckResult:
        """
        Run all health checks.
        
        Args:
            include_details: Include detailed component info
            
        Returns:
            HealthCheckResult with aggregated status
        """
        components: Dict[str, ComponentHealth] = {}
        
        # Run all checks concurrently
        if self._components:
            tasks = [comp.check() for comp in self._components.values()]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for comp, result in zip(self._components.values(), results):
                if isinstance(result, Exception):
                    components[comp.name] = ComponentHealth(
                        name=comp.name,
                        status=HealthStatus.UNHEALTHY,
                        message=str(result),
                    )
                else:
                    components[comp.name] = result
        
        # Aggregate status
        statuses = [c.status for c in components.values()]
        if not statuses:
            overall = HealthStatus.HEALTHY
        elif HealthStatus.UNHEALTHY in statuses:
            overall = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED if not self.fail_on_degraded else HealthStatus.UNHEALTHY
        else:
            overall = HealthStatus.HEALTHY
        
        return HealthCheckResult(
            status=overall,
            components=components if include_details else {},
            version=self.version,
        )
    
    async def check_liveness(self) -> bool:
        """
        Liveness check - is the process alive?
        
        Kubernetes uses this to know when to restart a container.
        Should be fast and not depend on external services.
        """
        return True
    
    async def check_readiness(self) -> HealthCheckResult:
        """
        Readiness check - can the service handle requests?
        
        Kubernetes uses this to know when to route traffic.
        """
        return await self.check_health()
    
    async def check_startup(self) -> bool:
        """
        Startup check - has initialization completed?
        
        Kubernetes uses this during startup.
        """
        return self._startup_complete
    
    def create_fastapi_routes(self, prefix: str = ""):
        """
        Create FastAPI routes for health endpoints.
        
        Example:
            from fastapi import FastAPI
            
            app = FastAPI()
            checker = HealthChecker()
            app.include_router(checker.create_fastapi_routes())
        """
        from fastapi import APIRouter, Response
        
        router = APIRouter(prefix=prefix)
        
        @router.get("/health")
        async def health():
            result = await self.check_health()
            status_code = 200 if result.status == HealthStatus.HEALTHY else 503
            return Response(
                content=str(result.to_dict()),
                media_type="application/json",
                status_code=status_code,
            )
        
        @router.get("/live")
        @router.get("/livez")
        async def liveness():
            alive = await self.check_liveness()
            return Response(
                content='{"status": "alive"}' if alive else '{"status": "dead"}',
                media_type="application/json",
                status_code=200 if alive else 503,
            )
        
        @router.get("/ready")
        @router.get("/readyz")
        async def readiness():
            result = await self.check_readiness()
            status_code = 200 if result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED] else 503
            return Response(
                content=str(result.to_dict()),
                media_type="application/json",
                status_code=status_code,
            )
        
        @router.get("/startup")
        @router.get("/startupz")
        async def startup():
            ready = await self.check_startup()
            return Response(
                content='{"status": "ready"}' if ready else '{"status": "starting"}',
                media_type="application/json",
                status_code=200 if ready else 503,
            )
        
        return router


def create_health_routes(checker: HealthChecker, prefix: str = ""):
    """Convenience function to create health routes."""
    return checker.create_fastapi_routes(prefix)


# Export public API
__all__ = [
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
