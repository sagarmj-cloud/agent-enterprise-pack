# Quick Reference - Agent Enterprise Pack

## UV Commands

```bash
# Installation
uv sync                      # Install dependencies
uv sync --all-extras         # Install with dev/test extras
uv add package-name          # Add dependency
uv add --dev pytest          # Add dev dependency
uv remove package-name       # Remove dependency

# Running
uv run python main.py        # Run application
uv run pytest                # Run tests
uv run ruff check .          # Lint code

# Updates
uv sync --upgrade            # Update all packages
```

## Make Commands

```bash
make help           # Show all commands
make install        # Install dependencies
make dev-install    # Install with dev extras
make test           # Run tests
make test-cov       # Run tests with coverage
make lint           # Check linting
make lint-fix       # Fix linting issues
make format         # Format code
make type-check     # Run mypy
make docker-build   # Build Docker image
make docker-run     # Run with docker-compose
make clean          # Clean build artifacts
make ci             # Run all CI checks
```

## Docker Commands

```bash
# Standard build
docker build -t agent-enterprise-pack:latest .

# UV-optimized build (faster)
docker build -f Dockerfile.uv -t agent-enterprise-pack:uv .

# Run container
docker run -p 8080:8080 \
  -e JWT_SECRET=secret \
  -e GOOGLE_CLOUD_PROJECT=project \
  agent-enterprise-pack:latest

# Docker Compose
docker-compose up -d         # Start services
docker-compose logs -f       # View logs
docker-compose down          # Stop services
```

## Testing

```bash
# All tests
uv run pytest

# Specific test file
uv run pytest tests/test_security.py

# With coverage
uv run pytest --cov --cov-report=html

# Specific test
uv run pytest tests/test_security.py::TestInputValidator::test_validate_clean_input

# Mark-based
uv run pytest -m unit        # Only unit tests
uv run pytest -m "not slow"  # Skip slow tests
```

## Git Workflow

```bash
# Create branch
git checkout -b feat/new-feature

# Commit (Conventional Commits)
git commit -m "feat: add new feature"
git commit -m "fix: resolve bug"
git commit -m "docs: update readme"

# Push and create PR
git push origin feat/new-feature

# Create release
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

## Environment Variables

```bash
# Required
JWT_SECRET=<32-byte-hex>
GOOGLE_CLOUD_PROJECT=your-project-id
LOCATION=us-central1
MODEL=gemini-1.5-pro

# Caching
CACHE_BACKEND=redis
REDIS_URL=redis://localhost:6379

# Optional
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
```

## API Endpoints

```bash
# Health checks
GET /health          # Liveness probe
GET /ready           # Readiness probe
GET /metrics         # Metrics endpoint

# Main endpoints
POST /chat           # Chat with agent
GET /                # Service info
```

## GCP Commands

```bash
# Deploy to Cloud Run
gcloud run deploy agent-enterprise-pack \
  --image=gcr.io/PROJECT/agent-enterprise-pack:latest \
  --region=us-central1 \
  --platform=managed

# View logs
gcloud run services logs read agent-enterprise-pack

# Describe service
gcloud run services describe agent-enterprise-pack

# Create Redis instance
gcloud redis instances create agent-cache \
  --size=1 \
  --region=us-central1 \
  --redis-version=redis_7_0
```

## Troubleshooting

```bash
# Clear UV cache
rm -rf .venv uv.lock && uv sync

# Clear Docker cache
docker system prune -a

# Check Redis connection
redis-cli -h localhost -p 6379 ping

# View container logs
docker logs <container-id>

# Interactive container shell
docker run -it agent-enterprise-pack:latest /bin/bash
```

## CI/CD Status Badges

Add to README.md:

```markdown
![CI](https://github.com/YOUR_ORG/agent-enterprise-pack/workflows/CI/badge.svg)
![CD](https://github.com/YOUR_ORG/agent-enterprise-pack/workflows/CD/badge.svg)
[![codecov](https://codecov.io/gh/YOUR_ORG/agent-enterprise-pack/branch/main/graph/badge.svg)](https://codecov.io/gh/YOUR_ORG/agent-enterprise-pack)
```

