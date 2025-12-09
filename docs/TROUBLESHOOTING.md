# Troubleshooting Guide - Agent Enterprise Pack

Common issues and solutions when testing and deploying the Agent Enterprise Pack.

---

## 🔴 Cloud Build Issues

### Error: "NOT_FOUND: Requested entity was not found"

**Full Error:**
```
Uploading tarball of [.] to [gs://PROJECT_ID_cloudbuild/source/...]
ERROR: (gcloud.builds.submit) NOT_FOUND: Requested entity was not found.
```

**Cause:** Cloud Build storage bucket doesn't exist yet. Cloud Build needs a Google Cloud Storage bucket to store build artifacts.

**Solutions:**

#### Solution 1: Run Setup Script (Easiest) ⭐

```bash
# This will set up everything Cloud Build needs
./scripts/setup-cloud-build-prerequisites.sh
```

This script will:
- ✅ Enable Cloud Build API
- ✅ Enable Cloud Storage API
- ✅ Create the required storage bucket
- ✅ Set up service account permissions
- ✅ Verify everything is working

**Time:** 2-3 minutes

#### Solution 2: Create Bucket Manually

```bash
# Replace YOUR_PROJECT_ID with your actual project ID
gsutil mb -p YOUR_PROJECT_ID -l us-central1 gs://YOUR_PROJECT_ID_cloudbuild

# Verify bucket was created
gsutil ls -b gs://YOUR_PROJECT_ID_cloudbuild
```

#### Solution 3: Via Console

1. Go to: https://console.cloud.google.com/storage/create-bucket?project=YOUR_PROJECT_ID
2. **Bucket name:** `YOUR_PROJECT_ID_cloudbuild` (replace YOUR_PROJECT_ID)
3. **Location:** `us-central1` (or your preferred region)
4. **Storage class:** `Standard`
5. Click **CREATE**

#### After Fixing

Once the bucket is created, try building again:

```bash
# Try the build script again
./scripts/build-image-cloud.sh

# Or the deployment script
./scripts/deploy-to-vertex-ai.sh
```

---

### Error: "Cloud Build API not enabled"

**Solution:**

```bash
# Enable via Console (recommended)
open "https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com?project=YOUR_PROJECT_ID"

# Or via gcloud (if you have permissions)
gcloud services enable cloudbuild.googleapis.com
```

---

### Error: "Permission denied" during Cloud Build

**Cause:** Cloud Build service account lacks necessary permissions

**Solution:**

```bash
# Get your project number
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)")

# Grant necessary permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
    --role="roles/artifactregistry.writer"
```

Or use the setup script:
```bash
./scripts/setup-cloud-build-prerequisites.sh
```

---

## 🔴 GCP API Permission Errors

### Error: "Bind permission denied for service: cloudmonitoring.googleapis.com"

**Full Error:**
```
ERROR: (gcloud.services.enable) does not have permission to access projects instance
Bind permission denied for service: cloudmonitoring.googleapis.com
Service cloudmonitoring.googleapis.com is not available to this consumer.
```

**Cause:** Your account lacks permissions to enable Cloud Monitoring API, or the project doesn't have billing enabled.

**Solutions:**

#### Solution 1: Use Local-Only Testing (Recommended for Quick Start)

```bash
# Test completely locally without GCP APIs
./scripts/quick-test-local-only.sh
```

This skips all GCP API requirements and tests locally.

#### Solution 2: Use Minimal GCP Setup

```bash
# Enable only essential APIs (skips Cloud Monitoring)
./scripts/quick-test-minimal.sh
```

This enables only the APIs needed for basic functionality.

#### Solution 3: Enable APIs Manually via Console

1. Go to: https://console.cloud.google.com/apis/library
2. Search for and enable:
   - Vertex AI API
   - Container Registry API
   - Secret Manager API
3. Skip Cloud Monitoring for now
4. Run: `./scripts/quick-test-minimal.sh`

#### Solution 4: Check Billing

```bash
# Verify billing is enabled
gcloud billing projects describe YOUR_PROJECT_ID

# If not enabled, link billing account
gcloud billing accounts list
gcloud billing projects link YOUR_PROJECT_ID \
    --billing-account=YOUR_BILLING_ACCOUNT_ID
```

#### Solution 5: Use Different Account

```bash
# Switch to account with owner permissions
gcloud auth login --account=owner@example.com
gcloud config set account owner@example.com

# Try again
./scripts/quick-test.sh
```

---

## 🔴 Redis Connection Errors

### Error: "Connection refused" or "Cannot connect to Redis"

**Solutions:**

```bash
# Check if Redis is running
docker ps | grep redis

# Start Redis
docker run -d --name redis-test -p 6379:6379 redis:7-alpine

# Test connection
redis-cli ping  # Should return "PONG"

# Restart Redis
docker restart redis-test

# Check logs
docker logs redis-test
```

---

## 🔴 Server Won't Start

### Error: "Address already in use" or "Port 8080 is already allocated"

**Solutions:**

```bash
# Find process using port 8080
lsof -i :8080

# Kill the process
kill $(lsof -t -i:8080)

# Or use different port
export PORT=8081
python main.py
```

### Error: "Module not found" or "Import error"

**Solutions:**

```bash
# Reinstall dependencies
uv sync --all-extras

# Or with pip
pip install -r requirements.txt --force-reinstall

# Check Python version (need 3.11+)
python --version
```

---

## 🔴 Authentication Errors

### Error: "Application Default Credentials not found"

**Solutions:**

```bash
# Login with application default credentials
gcloud auth application-default login

# Or set credentials explicitly
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# For local testing, use local-only mode
./scripts/quick-test-local-only.sh
```

### Error: "Permission denied" when accessing secrets

**Solutions:**

```bash
# Grant Secret Manager access
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:YOUR_EMAIL" \
    --role="roles/secretmanager.secretAccessor"

# Or use local secrets (in .env file)
# Edit .env and set secrets directly
```

---

## 🔴 Test Failures

### Tests fail with "No module named 'pytest'"

**Solutions:**

```bash
# Install test dependencies
uv sync --all-extras

# Or install pytest directly
pip install pytest pytest-asyncio pytest-cov
```

### Tests fail with GCP errors

**Solutions:**

```bash
# Run tests in local mode (skip GCP tests)
pytest tests/ -v -m "not gcp"

# Or mock GCP services
export MOCK_LLM=true
pytest tests/ -v
```

---

## 🔴 Docker Issues

### Error: "Cannot connect to Docker daemon"

**Solutions:**

```bash
# Start Docker Desktop (macOS/Windows)
open -a Docker

# Or start Docker service (Linux)
sudo systemctl start docker

# Check Docker is running
docker ps
```

### Error: "Image build failed"

**Solutions:**

```bash
# Clean Docker cache
docker system prune -a

# Rebuild without cache
docker build --no-cache -f Dockerfile.uv -t agent-test .

# Check Dockerfile syntax
docker build -f Dockerfile.uv -t agent-test . --progress=plain
```

---

## 🔴 Vertex AI Deployment Errors

### Error: "Service account does not have permission"

**Solutions:**

```bash
# Grant necessary permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:YOUR_SERVICE_ACCOUNT" \
    --role="roles/aiplatform.user"

# Or use your user account
gcloud auth application-default login
```

### Error: "Agent not found" or "404 Not Found"

**Solutions:**

```bash
# List all agents
gcloud ai agents list --region=us-central1

# Check agent status
gcloud ai agents describe AGENT_NAME --region=us-central1

# Redeploy
./scripts/deploy-to-vertex-ai.sh
```

---

## 🔴 Performance Issues

### Server is slow or unresponsive

**Solutions:**

```bash
# Check resource usage
docker stats

# Increase memory/CPU in Docker settings

# Check logs for errors
tail -f server.log

# Restart server
kill $(cat .server.pid)
python main.py
```

### High latency on API calls

**Solutions:**

```bash
# Use faster model
# Edit .env: MODEL=gemini-1.5-flash

# Enable caching
# Edit .env: CACHE_BACKEND=redis

# Check Redis is working
redis-cli ping
```

---

## 🔴 Cost Issues

### Unexpected GCP charges

**Solutions:**

```bash
# Check current costs
gcloud billing accounts list
# Visit: https://console.cloud.google.com/billing

# Set budget alerts
# Visit: https://console.cloud.google.com/billing/budgets

# Use cheaper model
# Edit .env: MODEL=gemini-1.5-flash

# Reduce replicas
# In deployment: --min-replicas=0 --max-replicas=1
```

---

## 🛠️ General Debugging

### Enable Debug Logging

```bash
# Edit .env
LOG_LEVEL=DEBUG

# Restart server
kill $(cat .server.pid)
python main.py

# View detailed logs
tail -f server.log
```

### Check System Status

```bash
# Check all services
docker ps                    # Redis
lsof -i :8080               # Server
gcloud config list          # GCP config
python --version            # Python version
uv --version                # UV version

# Check environment
cat .env
env | grep GOOGLE
```

### Clean Restart

```bash
# Stop everything
kill $(cat .server.pid) 2>/dev/null
docker stop redis-test 2>/dev/null
docker rm redis-test 2>/dev/null

# Clean up
rm -f .server.pid server.log

# Start fresh
./scripts/quick-test-local-only.sh
```

---

## 📚 Getting Help

### Check Documentation

- **[Testing Guide](TESTING_GUIDE.md)** - Comprehensive testing
- **[Getting Started](GETTING_STARTED.md)** - Setup guide
- **[Vertex AI Deployment](VERTEX_AI_DEPLOYMENT.md)** - Deployment guide

### Check Logs

```bash
# Server logs
tail -f server.log

# Docker logs
docker logs redis-test

# GCP logs
gcloud logging read 'resource.type=aiplatform.googleapis.com/Agent' --limit=50
```

### Common Commands

```bash
# Health check
curl http://localhost:8080/health

# Check Redis
redis-cli ping

# Check GCP project
gcloud config get-value project

# Check authentication
gcloud auth list

# Check enabled APIs
gcloud services list --enabled
```

---

## ✅ Quick Fixes Summary

| Issue | Quick Fix |
|-------|-----------|
| API permission errors | Use `./scripts/quick-test-local-only.sh` |
| Redis not running | `docker run -d --name redis-test -p 6379:6379 redis:7-alpine` |
| Port already in use | `kill $(lsof -t -i:8080)` |
| Module not found | `uv sync --all-extras` |
| Auth errors | `gcloud auth application-default login` |
| Tests failing | `pytest tests/ -v -m "not gcp"` |
| Docker not running | `open -a Docker` (macOS) |
| Server slow | Check `docker stats` and logs |

---

## 💡 Prevention Tips

1. **Start local first** - Test locally before deploying to GCP
2. **Use test project** - Create separate project for testing
3. **Monitor costs** - Set up budget alerts
4. **Check logs** - Always check logs when issues occur
5. **Clean restarts** - Stop all services before restarting

---

## 🆘 Still Having Issues?

1. Check logs: `tail -f server.log`
2. Try local-only mode: `./scripts/quick-test-local-only.sh`
3. Clean restart: Stop all services and start fresh
4. Check documentation: Review relevant guides
5. Verify prerequisites: Ensure all tools are installed

---

**Most Common Solution:** Use local-only testing to bypass GCP permission issues:

```bash
./scripts/quick-test-local-only.sh
```

This works without any GCP permissions and tests all core functionality locally! 🚀

