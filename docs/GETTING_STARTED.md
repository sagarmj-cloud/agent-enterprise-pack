# Getting Started - Agent Enterprise Pack

Complete guide to get started with testing and deploying the Agent Enterprise Pack in your Google Cloud project.

---

## 🎯 Overview

This guide will walk you through:
1. **Local Testing** - Test the agent on your machine
2. **GCP Testing** - Test in your Google Cloud project
3. **Deployment** - Deploy to Vertex AI Agent Engine
4. **CI/CD Setup** - Automate deployments

**Time Required:** 30-60 minutes

---

## 📋 Prerequisites

### Required Tools

```bash
# Check if you have required tools
gcloud --version    # Google Cloud SDK
docker --version    # Docker
python --version    # Python 3.11+
git --version       # Git
```

### Install Missing Tools

**Google Cloud SDK:**
```bash
# macOS
brew install google-cloud-sdk

# Linux
curl https://sdk.cloud.google.com | bash

# Windows
# Download from: https://cloud.google.com/sdk/docs/install
```

**Docker:**
```bash
# macOS
brew install docker

# Linux
curl -fsSL https://get.docker.com | sh

# Windows
# Download from: https://docs.docker.com/desktop/install/windows-install/
```

**UV (Optional but recommended):**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### GCP Setup

```bash
# Login to GCP
gcloud auth login
gcloud auth application-default login

# Create or select project
gcloud projects create my-agent-project  # Optional: create new project
gcloud config set project my-agent-project

# Enable billing (required)
# Visit: https://console.cloud.google.com/billing
```

---

## 🚀 Quick Start (5 Minutes)

### Option 1: Automated Setup (Recommended)

```bash
# Clone repository
git clone <repo-url>
cd agent-enterprise-pack

# Run quick test script
chmod +x scripts/quick-test.sh
./scripts/quick-test.sh
```

This script will:
- ✅ Check prerequisites
- ✅ Enable required APIs
- ✅ Create test secrets
- ✅ Start Redis
- ✅ Install dependencies
- ✅ Run tests
- ✅ Start local server
- ✅ Test all endpoints

**That's it!** Your agent is now running locally at `http://localhost:8080`

---

### Option 2: Manual Setup

```bash
# 1. Clone repository
git clone <repo-url>
cd agent-enterprise-pack

# 2. Set project
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# 3. Enable APIs
gcloud services enable \
    aiplatform.googleapis.com \
    containerregistry.googleapis.com \
    secretmanager.googleapis.com

# 4. Create secrets
echo -n "$(openssl rand -hex 32)" | \
    gcloud secrets create jwt-secret --data-file=-

echo -n "redis://localhost:6379" | \
    gcloud secrets create redis-url --data-file=-

# 5. Start Redis
docker run -d --name redis-test -p 6379:6379 redis:7-alpine

# 6. Install dependencies
uv sync  # or: pip install -r requirements.txt

# 7. Configure environment
cat > .env << EOF
GOOGLE_CLOUD_PROJECT=${PROJECT_ID}
LOCATION=us-central1
MODEL=gemini-1.5-pro
JWT_SECRET=$(openssl rand -hex 32)
CACHE_BACKEND=redis
REDIS_URL=redis://localhost:6379
EOF

# 8. Run tests
uv run pytest tests/ -v

# 9. Start server
uv run python main.py
```

---

## 🧪 Testing Your Agent

### Test with cURL

```bash
# Health check
curl http://localhost:8080/health

# Chat
curl -X POST http://localhost:8080/chat \
    -H "Content-Type: application/json" \
    -H "X-API-Key: demo-api-key" \
    -d '{
        "message": "Hello! Can you help me?",
        "session_id": "test-123"
    }'

# Metrics
curl http://localhost:8080/metrics
```

### Test with Python Script

```bash
# Interactive testing
uv run python examples/test_agent.py

# This provides:
# - Health checks
# - Security testing
# - Memory testing
# - Interactive chat mode
```

### Test with Browser

```bash
# Open in browser
open http://localhost:8080/health
open http://localhost:8080/metrics
```

---

## ☁️ Deploy to Vertex AI

### Quick Deployment

```bash
# Deploy to Vertex AI Agent Engine
chmod +x scripts/deploy-to-vertex-ai.sh
./scripts/deploy-to-vertex-ai.sh
```

Follow the prompts:
1. Enter your project ID
2. Choose region (us-central1)
3. Build and push image (y)
4. Test inference (y)

**Time:** 10-15 minutes

### Test Deployed Agent

```bash
# Get endpoint
ENDPOINT=$(gcloud ai agents describe agent-enterprise-pack \
    --region=us-central1 \
    --format='value(endpoint)')

# Test health
curl -f "$ENDPOINT/health" \
    -H "Authorization: Bearer $(gcloud auth print-access-token)"

# Test chat
curl -X POST "$ENDPOINT/chat" \
    -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    -H "Content-Type: application/json" \
    -d '{"message": "Hello from Vertex AI!", "session_id": "vertex-test"}'
```

---

## 🔄 Setup CI/CD

### Option 1: Cloud Build (More Secure)

```bash
# Setup Cloud Build
chmod +x scripts/setup-cloud-build.sh
./scripts/setup-cloud-build.sh

# Deploy by pushing a tag
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

**Benefits:**
- ✅ No service account keys
- ✅ More secure
- ✅ Lower cost (~$3/month)

### Option 2: GitHub Actions

```bash
# Setup GitHub Actions
chmod +x scripts/setup-gcp-github-actions.sh
./scripts/setup-gcp-github-actions.sh

# Add secrets to GitHub, then push
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

**Benefits:**
- ✅ Rich ecosystem
- ✅ Easy setup
- ✅ Multi-cloud support

---

## 📊 Next Steps

### 1. Explore Features

Test the enterprise features:
- **Security:** Input validation, prompt injection detection, rate limiting
- **Reliability:** Circuit breakers, retry logic, graceful degradation
- **Memory:** Context management, conversation caching
- **Observability:** SLO tracking, cost monitoring, alerting

### 2. Customize Configuration

Edit `.env` file:
```bash
# Adjust rate limits
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_WINDOW=60

# Change model
MODEL=gemini-1.5-flash  # Faster, cheaper

# Enable monitoring
ENABLE_TRACING=true
ENABLE_METRICS=true
```

### 3. Add Your Agent Logic

Customize the agent in `main.py`:
```python
# Add your custom tools, prompts, and logic
```

### 4. Production Deployment

Follow production best practices:
- Use Memorystore for Redis
- Configure monitoring and alerting
- Set up multi-region deployment
- Enable VPC Service Controls
- Configure auto-scaling

---

## 📚 Documentation

### Essential Guides
- **[Testing Guide](TESTING_GUIDE.md)** - Comprehensive testing
- **[Vertex AI Deployment](VERTEX_AI_DEPLOYMENT.md)** - Production deployment
- **[Cloud Build Setup](CLOUD_BUILD_SETUP.md)** - CI/CD setup

### Reference
- **[Quick Reference](QUICK_REFERENCE.md)** - Command cheat sheet
- **[Setup Checklist](SETUP_CHECKLIST.md)** - Step-by-step checklist

### Comparisons
- **[Vertex AI vs Cloud Run](VERTEX_AI_VS_CLOUD_RUN.md)** - Why Vertex AI?
- **[Cloud Build vs GitHub Actions](CLOUD_BUILD_VS_GITHUB_ACTIONS.md)** - CI/CD comparison

---

## 🐛 Troubleshooting

### Server won't start

```bash
# Check if port is in use
lsof -i :8080

# Kill existing process
kill $(lsof -t -i:8080)

# Check logs
tail -f logs/agent.log
```

### Redis connection error

```bash
# Check Redis is running
docker ps | grep redis

# Restart Redis
docker restart redis-test

# Test connection
redis-cli ping
```

### API permission errors

```bash
# Grant yourself permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:$(gcloud config get-value account)" \
    --role="roles/owner"
```

### Tests failing

```bash
# Install test dependencies
uv sync --all-extras

# Run specific test
uv run pytest tests/test_security.py -v

# Run with more output
uv run pytest tests/ -vv --tb=short
```

---

## 💡 Tips

- **Start local first:** Test locally before deploying to GCP
- **Use test project:** Create a separate GCP project for testing
- **Monitor costs:** Set up budget alerts in GCP Console
- **Iterate quickly:** Use local testing for rapid development
- **Automate early:** Set up CI/CD once manual testing works

---

## ✅ Success Checklist

- [ ] Prerequisites installed (gcloud, docker, python)
- [ ] GCP project created and configured
- [ ] APIs enabled
- [ ] Secrets created
- [ ] Redis running
- [ ] Dependencies installed
- [ ] Local tests passing
- [ ] Server starts successfully
- [ ] Endpoints responding
- [ ] Deployed to Vertex AI (optional)
- [ ] CI/CD configured (optional)

---

## 🎉 You're Ready!

Congratulations! You now have:
- ✅ Agent running locally
- ✅ All tests passing
- ✅ Ready to deploy to Vertex AI
- ✅ CI/CD ready to configure

**Next:** Deploy to production with [`docs/VERTEX_AI_DEPLOYMENT.md`](VERTEX_AI_DEPLOYMENT.md)

Happy building! 🚀

