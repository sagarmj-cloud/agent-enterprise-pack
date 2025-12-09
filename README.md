# Agent Enterprise Pack for Google ADK

A production-hardening toolkit that fills the critical gaps in [Google Agent Starter Pack](https://github.com/GoogleCloudPlatform/agent-starter-pack), providing enterprise-grade security, reliability, memory management, and observability for AI agents deployed on **Vertex AI Agent Engine**.

> **🤖 Deployment Target:** This pack is designed for [Vertex AI Agent Engine](https://cloud.google.com/vertex-ai/docs/agents), Google's purpose-built platform for AI agents, not generic Cloud Run.

## Overview

While Google Agent Starter Pack provides ~70% of production infrastructure out of the box, it lacks critical enterprise patterns:

| Gap | This Pack Provides |
|-----|-------------------|
| No circuit breakers | Full circuit breaker pattern with registry |
| No rate limiting | Multi-backend rate limiting (Redis, in-memory) |
| No prompt injection protection | 3-layer detection (pattern, heuristic, LLM) |
| No input validation | Comprehensive sanitization and validation |
| Basic health checks | Kubernetes-ready liveness/readiness probes |
| No graceful degradation | Fallback providers with static/cache/LLM options |
| No memory management | Context window management with 4 truncation strategies |
| No SLO management | Full SLO/SLI tracking with error budgets |
| No cost tracking | Token usage monitoring with budget alerts |
| Basic alerting | Multi-channel alerting (Slack, PagerDuty, email) |

## Module Summary

| Module | Lines of Code | Description |
|--------|---------------|-------------|
| **Security** | ~2,400 | Input validation, prompt injection, rate limiting, auth |
| **Reliability** | ~2,250 | Circuit breakers, retry, degradation, health checks |
| **Memory** | ~1,650 | Context management, compression, caching |
| **Observability** | ~1,750 | SLOs, cost tracking, alerting |
| **Terraform** | ~1,700 | IaC for Agent Engine, VPC-SC, monitoring |
| **Total** | ~11,000+ | Complete enterprise hardening |

## 🚀 Quick Start (2 Minutes)

### Step 1: Install Dependencies

```bash
# Using UV (recommended - 10-100x faster)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# Or using pip
pip install -r requirements.txt
```

### Step 2: Run the Quick Start Example

```bash
# Test all enterprise components
uv run python examples/quick_start.py
```

**That's it!** You'll see a demo of all 4 enterprise modules:
- 🔒 **Security** - Input validation, prompt injection detection, rate limiting
- 🔄 **Reliability** - Circuit breakers, retry logic, health checks
- 💾 **Memory** - Context window management, session caching
- 📊 **Observability** - SLO tracking, cost monitoring

📖 **Complete guide:** [`GETTING_STARTED.md`](GETTING_STARTED.md)

---

## 📚 What's Next?

### Option A: Run the Full Application

```bash
# Start the FastAPI server
uv run python main.py

# In another terminal, test the endpoints
curl http://localhost:8080/health
curl http://localhost:8080/
```

### Option B: Integrate into Your Agent

```python
from core.security import InputValidator, PromptInjectionDetector
from core.reliability import CircuitBreaker, RetryHandler
from core.memory import ContextWindowManager, AgentSessionCache
from core.observability import SLOManager, CostTracker

# Use the components in your agent code
validator = InputValidator()
circuit = CircuitBreaker(name="my-api")
context = ContextWindowManager(max_tokens=128000)
```

### Option C: Build Your Own Agent with Enterprise Pack

See the [examples/](examples/) directory for how to build and deploy your own agent using the Enterprise Pack components. The pack provides the enterprise components - you build your agent!

📖 **Deployment guide:** [`docs/VERTEX_AI_DEPLOYMENT.md`](docs/VERTEX_AI_DEPLOYMENT.md)

### Option D: Run Tests

```bash
# Run all tests
uv run pytest

# Run specific module tests
uv run pytest tests/test_security.py
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Application                          │
├─────────────────────────────────────────────────────────────────┤
│  Security Layer                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐ │
│  │   Auth      │ │Rate Limiter │ │Input Valid. │ │  Prompt    │ │
│  │ Middleware  │ │             │ │             │ │ Injection  │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  Reliability Layer                                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐ │
│  │  Circuit    │ │   Retry     │ │  Graceful   │ │  Health    │ │
│  │  Breaker    │ │  Handler    │ │ Degradation │ │  Checks    │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  Memory Layer                                                    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │
│  │  Context    │ │   Memory    │ │   Session   │                │
│  │  Manager    │ │ Compressor  │ │    Cache    │                │
│  └─────────────┘ └─────────────┘ └─────────────┘                │
├─────────────────────────────────────────────────────────────────┤
│  Observability Layer                                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │
│  │    SLO      │ │    Cost     │ │  Alerting   │                │
│  │  Manager    │ │   Tracker   │ │   Manager   │                │
│  └─────────────┘ └─────────────┘ └─────────────┘                │
├─────────────────────────────────────────────────────────────────┤
│                  Google ADK Agent                                │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Agent → Tools → Model (Gemini) → Session Service           │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │   Vertex AI Agent Engine      │
              │   (Cloud Run managed runtime) │
              └───────────────────────────────┘
```

## Module Details

### Security (`core/security/`)

- **`input_validator.py`** - Input validation, HTML/XSS sanitization, length limits
- **`prompt_injection.py`** - 3-layer detection (pattern matching, heuristics, LLM-based)
- **`rate_limiter.py`** - Token bucket, sliding window, Redis/in-memory backends
- **`auth_middleware.py`** - JWT, API Key, IAP, OAuth2 authentication

### Reliability (`core/reliability/`)

- **`circuit_breaker.py`** - Circuit breaker pattern with configurable thresholds
- **`retry_handler.py`** - Exponential backoff with jitter, Vertex AI presets
- **`graceful_degradation.py`** - Fallback providers (static, cache, LLM)
- **`health_checks.py`** - Kubernetes liveness/readiness probes

### Memory (`core/memory/`)

- **`context_manager.py`** - Token counting, 4 truncation strategies
- **`memory_compressor.py`** - LLM-based summarization and compression
- **`ttl_cache.py`** - Session caching with TTL (in-memory and Redis)

### Observability (`core/observability/`)

- **`slo_definitions.py`** - SLO/SLI management, error budgets
- **`cost_tracker.py`** - Token usage tracking, budget alerts
- **`alerting.py`** - Multi-channel (Slack, PagerDuty, email, Cloud Monitoring)

### Deployment (`deployment/`)

- **`terraform/modules/agent-engine/`** - Vertex AI Agent Engine deployment
- **`terraform/modules/vpc-sc/`** - VPC Service Controls perimeter
- **`terraform/modules/monitoring/`** - Alert policies, dashboards
- **`terraform/environments/`** - Dev and prod configurations

## Integration with Google Agent Starter Pack

```python
# In your agent starter pack application
from core.security import SecurityMiddleware, InputValidator, PromptInjectionDetector
from core.reliability import CircuitBreakerRegistry, RetryHandler, DegradationManager
from core.memory import ContextWindowManager, MemoryCompressor
from core.observability import SLOManager, CostTracker, AlertManager

# Initialize components
circuit_breaker = CircuitBreakerRegistry()
rate_limiter = RateLimiter(backend="redis", redis_url="redis://localhost")
input_validator = InputValidator()
prompt_detector = PromptInjectionDetector()

# Wrap your agent calls
@circuit_breaker.protect("vertex-ai")
@RetryHandler(preset=RetryPresets.VERTEX_AI)
async def call_agent(request):
    # Validate input
    validated = input_validator.validate(request.message)
    
    # Check for prompt injection
    if prompt_detector.detect(validated.text):
        raise SecurityException("Potential prompt injection detected")
    
    # Call your ADK agent
    response = await agent.run(validated.text)
    
    return response
```

## Development

### Setup Development Environment

```bash
# Install with dev dependencies
uv sync --all-extras

# Run tests
make test

# Run tests with coverage
make test-cov

# Lint and format
make lint
make format

# Type checking
make type-check

# Run all CI checks locally
make ci
```

### Available Make Commands

```bash
make help           # Show all available commands
make install        # Install dependencies
make dev-install    # Install with dev dependencies
make test           # Run tests
make test-cov       # Run tests with coverage
make lint           # Run linting
make format         # Format code
make docker-build   # Build Docker image
make clean          # Clean build artifacts
```

## CI/CD

### Choose Your CI/CD Platform

The project supports **two CI/CD options**:

#### **Option 1: Google Cloud Build** (Recommended for GCP) 🔒

**More Secure:**
- ✅ No service account keys needed
- ✅ Native GCP integration
- ✅ Secrets in Secret Manager
- ✅ Better audit logs
- ✅ Lower cost for private repos

**Quick Setup:**
```bash
chmod +x scripts/setup-cloud-build.sh
./scripts/setup-cloud-build.sh
```

📖 **See:** [`docs/CLOUD_BUILD_SETUP.md`](docs/CLOUD_BUILD_SETUP.md)

#### **Option 2: GitHub Actions** (Multi-cloud friendly)

**More Flexible:**
- ✅ Rich ecosystem
- ✅ Easy setup
- ✅ Multi-cloud support
- ✅ Free for public repos

📖 **See:** Setup instructions below

**Comparison:** See [`docs/CLOUD_BUILD_VS_GITHUB_ACTIONS.md`](docs/CLOUD_BUILD_VS_GITHUB_ACTIONS.md)

---

### GitHub Actions Workflows

The project includes GitHub Actions workflows with the following pipelines:

#### **CI Pipeline** (`.github/workflows/ci.yml`)
Runs on every push and PR:
- ✅ Linting (Ruff)
- ✅ Type checking (mypy)
- ✅ Tests (pytest) on Python 3.11 & 3.12
- ✅ Security scanning (safety, bandit)
- ✅ Docker build and test
- ✅ Code coverage (Codecov)

#### **PR Checks** (`.github/workflows/pr-checks.yml`)
Additional PR validation:
- ✅ PR title format (Conventional Commits)
- ✅ Changed files detection
- ✅ Quick tests on changed code
- ✅ PR size warnings

#### **CD Pipeline** (`.github/workflows/cd.yml`)
Automated deployment on tag push:
- 🚀 Build and push Docker image to GCR
- 🚀 Deploy to Cloud Run
- 🚀 Health check verification
- 🚀 Slack notifications

#### **Release** (`.github/workflows/release.yml`)
Automated releases:
- 📦 Create GitHub release
- 📦 Build Python package
- 📦 Publish to PyPI

### Setting Up CI/CD

#### Required GitHub Secrets

For full CI/CD functionality, configure these secrets in your GitHub repository:

```bash
# Google Cloud
GCP_SA_KEY          # Service account JSON key
GCP_PROJECT_ID      # Your GCP project ID
GCP_REGION          # Deployment region (e.g., us-central1)

# Redis
REDIS_URL           # Production Redis URL

# Slack (optional)
SLACK_WEBHOOK_URL   # Slack webhook for notifications

# PyPI (for releases)
PYPI_API_TOKEN      # PyPI API token for publishing
```

#### Deployment Workflow

1. **Development**: Push to `develop` branch
   - Runs CI tests
   - No deployment

2. **Pull Request**: Create PR to `main`
   - Runs full CI suite
   - PR checks and validations

3. **Release**: Push version tag
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0"
   git push origin v1.0.0
   ```
   - Builds Docker image
   - Deploys to Cloud Run
   - Creates GitHub release
   - Publishes to PyPI

### Local CI Testing

Test CI pipeline locally before pushing:

```bash
# Run all CI checks
make ci

# Test Docker build
make docker-build
make docker-test

# Security checks
make security-check
```

## Documentation

### 📖 Deployment Guides
- **[Vertex AI Deployment](docs/VERTEX_AI_DEPLOYMENT.md)** - Deploy to Vertex AI Agent Engine (recommended)
- **[Deployment Summary](docs/DEPLOYMENT_SUMMARY.md)** - Complete deployment overview
- **[Vertex AI vs Cloud Run](docs/VERTEX_AI_VS_CLOUD_RUN.md)** - Why Vertex AI Agent Engine?

### 🔄 CI/CD Setup
- **[Cloud Build Setup](docs/CLOUD_BUILD_SETUP.md)** - CI/CD with Cloud Build (more secure)
- **[Cloud Build vs GitHub Actions](docs/CLOUD_BUILD_VS_GITHUB_ACTIONS.md)** - Security comparison
- **[CI/CD Options Summary](docs/CI_CD_OPTIONS_SUMMARY.md)** - Quick decision guide

### 💻 Development
- **[Setup Guide](docs/SETUP_GUIDE.md)** - Complete development setup
- **[Quick Reference](docs/QUICK_REFERENCE.md)** - Command cheat sheet
- **[Setup Checklist](docs/SETUP_CHECKLIST.md)** - Step-by-step checklist
- **[Contributing](CONTRIBUTING.md)** - Contribution guidelines

---

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Quick Contribution Guide

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/amazing-feature`
3. Make your changes and add tests
4. Run tests: `make test`
5. Lint and format: `make lint format`
6. Commit: `git commit -m "feat: add amazing feature"`
7. Push: `git push origin feat/amazing-feature`
8. Open a Pull Request
