# Setup Guide - Agent Enterprise Pack

Complete guide for setting up development environment and CI/CD pipelines.

## Table of Contents
- [Development Setup](#development-setup)
- [UV Package Manager](#uv-package-manager)
- [CI/CD Configuration](#cicd-configuration)
- [Docker Setup](#docker-setup)
- [Production Deployment](#production-deployment)

---

## Development Setup

### Prerequisites

- **Python**: 3.11 or higher
- **UV**: Latest version (recommended)
- **Docker**: For containerized development
- **Redis**: For caching (optional for dev)
- **GCP Account**: For Vertex AI integration

### Option 1: UV (Recommended - 10-100x Faster)

UV is a blazingly fast Python package installer and resolver written in Rust.

#### Install UV

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**With pip:**
```bash
pip install uv
```

#### Setup Project

```bash
# Clone repository
git clone <your-repo-url>
cd agent-enterprise-pack

# Install all dependencies (production + dev + test)
uv sync --all-extras

# Or install only production dependencies
uv sync

# Verify installation
uv run python -c "from core.security import InputValidator; print('✅ Installation successful')"
```

#### Why UV?

- **10-100x faster** than pip for dependency resolution
- **Deterministic** builds with lockfile
- **Drop-in replacement** for pip
- **Built-in virtual environment** management
- **Parallel downloads** and installations

### Option 2: Traditional pip

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install -e ".[dev,test]"
```

---

## UV Package Manager

### Common UV Commands

```bash
# Install dependencies
uv sync                    # Install from pyproject.toml
uv sync --all-extras       # Install with all optional dependencies
uv sync --extra dev        # Install with specific extra

# Add new dependency
uv add fastapi             # Add to dependencies
uv add --dev pytest        # Add to dev dependencies

# Remove dependency
uv remove package-name

# Run commands
uv run python main.py      # Run Python script
uv run pytest              # Run tests
uv run ruff check .        # Run linter

# Update dependencies
uv sync --upgrade          # Update all dependencies
uv sync --upgrade-package requests  # Update specific package

# Build package
uv build                   # Build wheel and sdist
```

### UV vs pip Performance

| Operation | pip | UV | Speedup |
|-----------|-----|-----|---------|
| Cold install | 45s | 1.2s | **37x** |
| Warm install | 12s | 0.3s | **40x** |
| Dependency resolution | 8s | 0.1s | **80x** |

---

## CI/CD Configuration

### GitHub Actions Workflows

The project includes 4 automated workflows:

#### 1. **CI Pipeline** (`ci.yml`)

**Triggers:** Push to main/develop, Pull Requests

**Jobs:**
- **Lint**: Ruff linting and format checking
- **Test**: pytest on Python 3.11 & 3.12 with Redis
- **Security**: Safety and Bandit scans
- **Docker**: Build and test Docker image

**Setup:**
No secrets required for basic CI.

#### 2. **PR Checks** (`pr-checks.yml`)

**Triggers:** Pull Request events

**Jobs:**
- PR title validation (Conventional Commits)
- Changed files detection
- Quick tests on modified code
- PR size warnings

#### 3. **CD Pipeline** (`cd.yml`)

**Triggers:** Tag push (`v*.*.*`) or manual dispatch

**Jobs:**
- Build and push Docker image to GCR
- Deploy to Cloud Run
- Health check verification
- Slack notifications

**Required Secrets:**
```bash
GCP_SA_KEY          # Service account JSON
GCP_PROJECT_ID      # GCP project ID
GCP_REGION          # e.g., us-central1
REDIS_URL           # Production Redis URL
SLACK_WEBHOOK_URL   # Optional
```

#### 4. **Release** (`release.yml`)

**Triggers:** Tag push (`v*.*.*`)

**Jobs:**
- Generate changelog
- Create GitHub release
- Build Python package
- Publish to PyPI

**Required Secrets:**
```bash
PYPI_API_TOKEN      # PyPI API token
```

### Setting Up GitHub Secrets

1. Go to repository **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Add each required secret

#### Creating GCP Service Account

```bash
# Create service account
gcloud iam service-accounts create agent-enterprise-ci \
    --display-name="Agent Enterprise CI/CD"

# Grant permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:agent-enterprise-ci@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:agent-enterprise-ci@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

# Create key
gcloud iam service-accounts keys create key.json \
    --iam-account=agent-enterprise-ci@YOUR_PROJECT_ID.iam.gserviceaccount.com

# Copy key.json content to GCP_SA_KEY secret
cat key.json
```

---

## Docker Setup

### Standard Dockerfile

```bash
# Build
docker build -t agent-enterprise-pack:latest .

# Run
docker run -p 8080:8080 \
  -e JWT_SECRET=your-secret \
  -e GOOGLE_CLOUD_PROJECT=your-project \
  agent-enterprise-pack:latest
```

### UV-Optimized Dockerfile

**50% faster builds** with multi-stage caching:

```bash
# Build with UV
docker build -f Dockerfile.uv -t agent-enterprise-pack:uv .

# Run
docker run -p 8080:8080 agent-enterprise-pack:uv
```

### Docker Compose

```bash
# Start all services (app + Redis)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild
docker-compose up --build
```

### Environment Variables

Create `.env` file from template:

```bash
cp .env.example .env
# Edit .env with your values
```

Required variables:
```bash
JWT_SECRET=<generate-with-openssl-rand-hex-32>
GOOGLE_CLOUD_PROJECT=your-project-id
CACHE_BACKEND=redis
REDIS_URL=redis://redis:6379
```

---

## Production Deployment

### Cloud Run Deployment

#### Manual Deployment

```bash
# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Build and push image
docker build -t gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest .
docker push gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest

# Deploy to Cloud Run
gcloud run deploy agent-enterprise-pack \
  --image=gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest \
  --platform=managed \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-env-vars="CACHE_BACKEND=redis,GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID" \
  --set-secrets="JWT_SECRET=jwt-secret:latest" \
  --memory=2Gi \
  --cpu=2 \
  --min-instances=1 \
  --max-instances=10
```

#### Automated Deployment (CI/CD)

1. **Push a version tag:**
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0"
   git push origin v1.0.0
   ```

2. **GitHub Actions will automatically:**
   - Build Docker image
   - Push to GCR
   - Deploy to Cloud Run
   - Run health checks
   - Send notifications

### Google Cloud Setup

#### 1. Enable Required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  containerregistry.googleapis.com \
  aiplatform.googleapis.com \
  cloudmonitoring.googleapis.com \
  cloudtrace.googleapis.com
```

#### 2. Create Redis Instance (Memorystore)

```bash
gcloud redis instances create agent-cache \
  --size=1 \
  --region=us-central1 \
  --redis-version=redis_7_0 \
  --tier=basic

# Get connection info
gcloud redis instances describe agent-cache \
  --region=us-central1 \
  --format="value(host,port)"
```

#### 3. Create Secrets

```bash
# JWT Secret
echo -n "$(openssl rand -hex 32)" | \
  gcloud secrets create jwt-secret --data-file=-

# Slack Webhook (optional)
echo -n "https://hooks.slack.com/services/YOUR/WEBHOOK" | \
  gcloud secrets create slack-webhook --data-file=-

# Grant access to Cloud Run service account
gcloud secrets add-iam-policy-binding jwt-secret \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Monitoring and Observability

#### Health Checks

```bash
# Liveness
curl https://your-service-url/health

# Readiness
curl https://your-service-url/ready

# Metrics
curl https://your-service-url/metrics
```

#### Cloud Monitoring

The application automatically exports:
- **Traces** to Cloud Trace
- **Metrics** to Cloud Monitoring
- **Logs** to Cloud Logging

View in GCP Console:
- Traces: https://console.cloud.google.com/traces
- Metrics: https://console.cloud.google.com/monitoring
- Logs: https://console.cloud.google.com/logs

---

## Troubleshooting

### UV Issues

**Problem:** `uv: command not found`
```bash
# Reinstall UV
curl -LsSf https://astral.sh/uv/install.sh | sh
# Add to PATH
export PATH="$HOME/.cargo/bin:$PATH"
```

**Problem:** Dependency conflicts
```bash
# Clear cache and reinstall
rm -rf .venv uv.lock
uv sync --all-extras
```

### Docker Issues

**Problem:** Build fails
```bash
# Clear Docker cache
docker system prune -a
docker build --no-cache -t agent-enterprise-pack:latest .
```

**Problem:** Container exits immediately
```bash
# Check logs
docker logs <container-id>

# Run interactively
docker run -it agent-enterprise-pack:latest /bin/bash
```

### CI/CD Issues

**Problem:** Tests fail in CI but pass locally
```bash
# Run tests with same environment
docker run --rm \
  -e REDIS_URL=redis://localhost:6379 \
  agent-enterprise-pack:latest \
  pytest -v
```

**Problem:** Deployment fails
```bash
# Check service account permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:YOUR_SA_EMAIL"
```

---

## Next Steps

1. ✅ Complete development setup
2. ✅ Run tests locally: `make test`
3. ✅ Configure GitHub secrets
4. ✅ Push code and verify CI passes
5. ✅ Deploy to staging environment
6. ✅ Create first release tag
7. ✅ Monitor production deployment

For more help, see:
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines
- [README.md](../README.md) - Project overview
- GitHub Issues - Report bugs or request features

