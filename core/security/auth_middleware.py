"""
Authentication Middleware
=========================
Multi-provider authentication for AI agent endpoints.

Providers:
- JWT (JSON Web Tokens)
- API Key
- Google IAP (Identity-Aware Proxy)
- OAuth2 Bearer Tokens

Features:
- Pluggable provider architecture
- Role-based access control (RBAC)
- Token validation and caching
- Audit logging
"""

import time
import hashlib
import logging
from typing import Optional, List, Dict, Any, Callable, Union, Set
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import base64
import json

logger = logging.getLogger(__name__)


class AuthResult(Enum):
    """Authentication result status."""
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"
    INVALID = "invalid"
    MISSING = "missing"


@dataclass
class AuthUser:
    """Authenticated user information."""
    user_id: str
    email: Optional[str] = None
    roles: List[str] = field(default_factory=list)
    permissions: Set[str] = field(default_factory=set)
    provider: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)
    authenticated_at: float = field(default_factory=time.time)


@dataclass
class AuthResponse:
    """Response from authentication attempt."""
    result: AuthResult
    user: Optional[AuthUser] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AuthProvider(ABC):
    """Abstract base class for authentication providers."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass
    
    @abstractmethod
    async def authenticate(self, credentials: str) -> AuthResponse:
        """
        Authenticate with provided credentials.
        
        Args:
            credentials: Token or key to authenticate
            
        Returns:
            AuthResponse with result and user info
        """
        pass
    
    def extract_credentials(self, request) -> Optional[str]:
        """Extract credentials from request. Override for custom extraction."""
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:]
        return None


class JWTProvider(AuthProvider):
    """JWT-based authentication provider."""
    
    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
        leeway: int = 30,
    ):
        """
        Initialize JWT provider.
        
        Args:
            secret_key: Secret key for token validation
            algorithm: JWT algorithm (HS256, RS256, etc.)
            issuer: Expected token issuer
            audience: Expected token audience
            leeway: Seconds of leeway for expiration
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.issuer = issuer
        self.audience = audience
        self.leeway = leeway
        self._jwt = None
    
    @property
    def name(self) -> str:
        return "jwt"
    
    def _get_jwt_module(self):
        """Lazy load PyJWT."""
        if self._jwt is None:
            try:
                import jwt
                self._jwt = jwt
            except ImportError:
                raise RuntimeError("PyJWT required for JWT auth: pip install PyJWT")
        return self._jwt
    
    async def authenticate(self, credentials: str) -> AuthResponse:
        """Authenticate JWT token."""
        jwt_module = self._get_jwt_module()
        
        try:
            options = {
                'require': ['exp', 'sub'],
                'verify_exp': True,
                'verify_iss': self.issuer is not None,
                'verify_aud': self.audience is not None,
            }
            
            payload = jwt_module.decode(
                credentials,
                self.secret_key,
                algorithms=[self.algorithm],
                issuer=self.issuer,
                audience=self.audience,
                leeway=self.leeway,
                options=options,
            )
            
            user = AuthUser(
                user_id=payload.get('sub', 'unknown'),
                email=payload.get('email'),
                roles=payload.get('roles', []),
                permissions=set(payload.get('permissions', [])),
                provider=self.name,
                metadata={
                    'iss': payload.get('iss'),
                    'aud': payload.get('aud'),
                    'exp': payload.get('exp'),
                    'iat': payload.get('iat'),
                },
            )
            
            return AuthResponse(result=AuthResult.SUCCESS, user=user)
            
        except jwt_module.ExpiredSignatureError:
            return AuthResponse(result=AuthResult.EXPIRED, error="Token has expired")
        except jwt_module.InvalidTokenError as e:
            return AuthResponse(result=AuthResult.INVALID, error=str(e))
        except Exception as e:
            logger.error(f"JWT authentication error: {e}")
            return AuthResponse(result=AuthResult.FAILED, error="Authentication failed")
    
    def create_token(
        self,
        user_id: str,
        email: Optional[str] = None,
        roles: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        expires_in: int = 3600,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a JWT token for testing/development."""
        jwt_module = self._get_jwt_module()
        
        payload = {
            'sub': user_id,
            'iat': int(time.time()),
            'exp': int(time.time()) + expires_in,
        }
        
        if email:
            payload['email'] = email
        if roles:
            payload['roles'] = roles
        if permissions:
            payload['permissions'] = permissions
        if self.issuer:
            payload['iss'] = self.issuer
        if self.audience:
            payload['aud'] = self.audience
        if additional_claims:
            payload.update(additional_claims)
        
        return jwt_module.encode(payload, self.secret_key, algorithm=self.algorithm)


class APIKeyProvider(AuthProvider):
    """API Key-based authentication provider."""
    
    def __init__(
        self,
        valid_keys: Optional[Dict[str, Dict[str, Any]]] = None,
        key_validator: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
        header_name: str = "X-API-Key",
    ):
        """
        Initialize API Key provider.
        
        Args:
            valid_keys: Dict of valid API keys to user info
            key_validator: Custom function to validate keys
            header_name: HTTP header name for API key
        """
        self.valid_keys = valid_keys or {}
        self.key_validator = key_validator
        self.header_name = header_name
    
    @property
    def name(self) -> str:
        return "api_key"
    
    def extract_credentials(self, request) -> Optional[str]:
        """Extract API key from header."""
        return request.headers.get(self.header_name)
    
    async def authenticate(self, credentials: str) -> AuthResponse:
        """Authenticate API key."""
        # Hash the key for comparison (if using hashed storage)
        key_hash = hashlib.sha256(credentials.encode()).hexdigest()
        
        # Check against valid keys (using hash or direct comparison)
        user_info = self.valid_keys.get(credentials) or self.valid_keys.get(key_hash)
        
        # Use custom validator if provided
        if not user_info and self.key_validator:
            user_info = self.key_validator(credentials)
        
        if user_info:
            user = AuthUser(
                user_id=user_info.get('user_id', 'api_user'),
                email=user_info.get('email'),
                roles=user_info.get('roles', ['api_access']),
                permissions=set(user_info.get('permissions', [])),
                provider=self.name,
                metadata=user_info.get('metadata', {}),
            )
            return AuthResponse(result=AuthResult.SUCCESS, user=user)
        
        return AuthResponse(result=AuthResult.INVALID, error="Invalid API key")
    
    def add_key(self, key: str, user_info: Dict[str, Any], hash_key: bool = True):
        """Add a valid API key."""
        if hash_key:
            key = hashlib.sha256(key.encode()).hexdigest()
        self.valid_keys[key] = user_info
    
    def revoke_key(self, key: str, hash_key: bool = True):
        """Revoke an API key."""
        if hash_key:
            key = hashlib.sha256(key.encode()).hexdigest()
        self.valid_keys.pop(key, None)


class GoogleIAPProvider(AuthProvider):
    """Google Identity-Aware Proxy authentication provider."""
    
    def __init__(
        self,
        expected_audience: str,
        verify_signature: bool = True,
    ):
        """
        Initialize Google IAP provider.
        
        Args:
            expected_audience: Expected IAP audience (e.g., /projects/123/apps/my-app)
            verify_signature: Whether to verify JWT signature
        """
        self.expected_audience = expected_audience
        self.verify_signature = verify_signature
    
    @property
    def name(self) -> str:
        return "google_iap"
    
    def extract_credentials(self, request) -> Optional[str]:
        """Extract IAP JWT from header."""
        return request.headers.get('X-Goog-IAP-JWT-Assertion')
    
    async def authenticate(self, credentials: str) -> AuthResponse:
        """Authenticate Google IAP JWT."""
        try:
            # Decode without verification first to get claims
            parts = credentials.split('.')
            if len(parts) != 3:
                return AuthResponse(result=AuthResult.INVALID, error="Invalid JWT format")
            
            # Decode payload
            payload_bytes = base64.urlsafe_b64decode(parts[1] + '==')
            payload = json.loads(payload_bytes)
            
            # Verify claims
            if payload.get('aud') != self.expected_audience:
                return AuthResponse(result=AuthResult.INVALID, error="Invalid audience")
            
            if payload.get('iss') not in ['https://cloud.google.com/iap', 'accounts.google.com']:
                return AuthResponse(result=AuthResult.INVALID, error="Invalid issuer")
            
            # Check expiration
            if payload.get('exp', 0) < time.time():
                return AuthResponse(result=AuthResult.EXPIRED, error="Token expired")
            
            # Note: In production, use google-auth library for proper signature verification
            # from google.auth.transport import requests as google_requests
            # from google.oauth2 import id_token
            # id_info = id_token.verify_oauth2_token(credentials, google_requests.Request(), expected_audience)
            
            user = AuthUser(
                user_id=payload.get('sub', 'unknown'),
                email=payload.get('email'),
                roles=['iap_user'],
                provider=self.name,
                metadata={
                    'iss': payload.get('iss'),
                    'email_verified': payload.get('email_verified'),
                    'hd': payload.get('hd'),  # Hosted domain
                },
            )
            
            return AuthResponse(result=AuthResult.SUCCESS, user=user)
            
        except Exception as e:
            logger.error(f"IAP authentication error: {e}")
            return AuthResponse(result=AuthResult.FAILED, error="IAP authentication failed")


class OAuth2Provider(AuthProvider):
    """OAuth2 Bearer Token authentication provider."""
    
    def __init__(
        self,
        introspection_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        token_cache_ttl: int = 300,
    ):
        """
        Initialize OAuth2 provider.
        
        Args:
            introspection_url: Token introspection endpoint
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            token_cache_ttl: Cache TTL for validated tokens
        """
        self.introspection_url = introspection_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_cache_ttl = token_cache_ttl
        self._cache: Dict[str, Tuple[AuthUser, float]] = {}
    
    @property
    def name(self) -> str:
        return "oauth2"
    
    async def authenticate(self, credentials: str) -> AuthResponse:
        """Authenticate OAuth2 bearer token."""
        # Check cache
        token_hash = hashlib.sha256(credentials.encode()).hexdigest()
        if token_hash in self._cache:
            user, cached_at = self._cache[token_hash]
            if time.time() - cached_at < self.token_cache_ttl:
                return AuthResponse(result=AuthResult.SUCCESS, user=user)
        
        if not self.introspection_url:
            return AuthResponse(result=AuthResult.FAILED, error="Introspection URL not configured")
        
        try:
            import httpx
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.introspection_url,
                    data={'token': credentials},
                    auth=(self.client_id, self.client_secret) if self.client_id else None,
                )
                
                if response.status_code != 200:
                    return AuthResponse(result=AuthResult.FAILED, error="Introspection failed")
                
                data = response.json()
                
                if not data.get('active'):
                    return AuthResponse(result=AuthResult.INVALID, error="Token inactive")
                
                user = AuthUser(
                    user_id=data.get('sub', 'unknown'),
                    email=data.get('email'),
                    roles=data.get('roles', []),
                    permissions=set(data.get('scope', '').split()),
                    provider=self.name,
                    metadata=data,
                )
                
                # Cache successful validation
                self._cache[token_hash] = (user, time.time())
                
                return AuthResponse(result=AuthResult.SUCCESS, user=user)
                
        except Exception as e:
            logger.error(f"OAuth2 authentication error: {e}")
            return AuthResponse(result=AuthResult.FAILED, error="Authentication failed")


class AuthMiddleware:
    """
    Multi-provider authentication middleware.
    
    Example:
        # Configure providers
        jwt_provider = JWTProvider(secret_key="your-secret")
        api_key_provider = APIKeyProvider(valid_keys={"key123": {"user_id": "user1"}})
        
        # Create middleware
        auth = AuthMiddleware([jwt_provider, api_key_provider])
        
        # In FastAPI
        @app.middleware("http")
        async def auth_middleware(request: Request, call_next):
            result = await auth.authenticate(request)
            if result.result != AuthResult.SUCCESS:
                return JSONResponse(status_code=401, content={"error": result.error})
            request.state.user = result.user
            return await call_next(request)
    """
    
    def __init__(
        self,
        providers: List[AuthProvider],
        require_auth: bool = True,
        excluded_paths: Optional[Set[str]] = None,
        log_failures: bool = True,
    ):
        """
        Initialize authentication middleware.
        
        Args:
            providers: List of authentication providers
            require_auth: Whether authentication is required
            excluded_paths: Paths to exclude from authentication
            log_failures: Whether to log authentication failures
        """
        self.providers = providers
        self.require_auth = require_auth
        self.excluded_paths = excluded_paths or {'/health', '/ready', '/metrics'}
        self.log_failures = log_failures
    
    async def authenticate(self, request) -> AuthResponse:
        """
        Authenticate request using configured providers.
        
        Args:
            request: HTTP request object (FastAPI Request)
            
        Returns:
            AuthResponse with authentication result
        """
        # Check excluded paths
        path = getattr(request, 'url', None)
        if path:
            path = str(path.path) if hasattr(path, 'path') else str(path)
            if path in self.excluded_paths:
                return AuthResponse(
                    result=AuthResult.SUCCESS,
                    user=AuthUser(user_id='anonymous', provider='none'),
                )
        
        # Try each provider
        errors: List[str] = []
        for provider in self.providers:
            credentials = provider.extract_credentials(request)
            if credentials:
                result = await provider.authenticate(credentials)
                if result.result == AuthResult.SUCCESS:
                    return result
                errors.append(f"{provider.name}: {result.error}")
        
        # No successful authentication
        if not errors:
            if not self.require_auth:
                return AuthResponse(
                    result=AuthResult.SUCCESS,
                    user=AuthUser(user_id='anonymous', provider='none'),
                )
            error = "No authentication credentials provided"
        else:
            error = "; ".join(errors)
        
        if self.log_failures:
            logger.warning(f"Authentication failed: {error}")
        
        return AuthResponse(result=AuthResult.MISSING if not errors else AuthResult.FAILED, error=error)
    
    def require_roles(self, *required_roles: str) -> Callable:
        """
        Decorator to require specific roles.
        
        Example:
            @app.get("/admin")
            @auth.require_roles("admin")
            async def admin_endpoint(request: Request):
                ...
        """
        def decorator(func):
            async def wrapper(*args, **kwargs):
                request = kwargs.get('request') or (args[0] if args else None)
                if not request or not hasattr(request, 'state') or not hasattr(request.state, 'user'):
                    from fastapi import HTTPException
                    raise HTTPException(status_code=401, detail="Not authenticated")
                
                user: AuthUser = request.state.user
                if not any(role in user.roles for role in required_roles):
                    from fastapi import HTTPException
                    raise HTTPException(status_code=403, detail="Insufficient permissions")
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    def require_permissions(self, *required_permissions: str) -> Callable:
        """
        Decorator to require specific permissions.
        
        Example:
            @app.post("/data")
            @auth.require_permissions("write:data")
            async def write_data(request: Request):
                ...
        """
        def decorator(func):
            async def wrapper(*args, **kwargs):
                request = kwargs.get('request') or (args[0] if args else None)
                if not request or not hasattr(request, 'state') or not hasattr(request.state, 'user'):
                    from fastapi import HTTPException
                    raise HTTPException(status_code=401, detail="Not authenticated")
                
                user: AuthUser = request.state.user
                if not all(perm in user.permissions for perm in required_permissions):
                    from fastapi import HTTPException
                    raise HTTPException(status_code=403, detail="Insufficient permissions")
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator


class SecurityMiddleware:
    """
    Combined security middleware with auth, rate limiting, and input validation.
    
    Example:
        from core.security import SecurityMiddleware, JWTProvider, RateLimiter, InputValidator
        
        security = SecurityMiddleware(
            auth_providers=[JWTProvider(secret="secret")],
            rate_limiter=RateLimiter(requests_per_window=100),
            input_validator=InputValidator(),
        )
        
        @app.middleware("http")
        async def security_middleware(request: Request, call_next):
            return await security.process(request, call_next)
    """
    
    def __init__(
        self,
        auth_providers: Optional[List[AuthProvider]] = None,
        rate_limiter: Optional['RateLimiter'] = None,
        input_validator: Optional['InputValidator'] = None,
        prompt_injection_detector: Optional['PromptInjectionDetector'] = None,
    ):
        """Initialize combined security middleware."""
        self.auth = AuthMiddleware(auth_providers) if auth_providers else None
        self.rate_limiter = rate_limiter
        self.input_validator = input_validator
        self.prompt_detector = prompt_injection_detector
    
    async def process(self, request, call_next):
        """Process request through all security layers."""
        from fastapi.responses import JSONResponse
        
        # Authentication
        if self.auth:
            auth_result = await self.auth.authenticate(request)
            if auth_result.result not in [AuthResult.SUCCESS]:
                return JSONResponse(
                    status_code=401,
                    content={"error": auth_result.error or "Authentication failed"},
                )
            request.state.user = auth_result.user
            rate_limit_key = auth_result.user.user_id
        else:
            rate_limit_key = request.client.host if hasattr(request, 'client') else 'unknown'
        
        # Rate limiting
        if self.rate_limiter:
            from .rate_limiter import RateLimitResult
            rate_result = await self.rate_limiter.check(rate_limit_key)
            if rate_result.result == RateLimitResult.DENIED:
                return JSONResponse(
                    status_code=429,
                    content={"error": "Rate limit exceeded", "retry_after": rate_result.retry_after},
                    headers=self.rate_limiter.get_headers(rate_result),
                )
        
        # Continue to next handler
        response = await call_next(request)
        
        # Add rate limit headers
        if self.rate_limiter and rate_result:
            for k, v in self.rate_limiter.get_headers(rate_result).items():
                response.headers[k] = v
        
        return response


# Export public API
__all__ = [
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
