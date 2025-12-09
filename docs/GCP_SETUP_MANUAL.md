# Manual GCP Setup Guide

Step-by-step guide to set up GCP for testing when you have API permission issues.

---

## 🎯 Goal

Enable the required GCP APIs manually through the Console, then test the agent on Vertex AI.

---

## 📋 Prerequisites

- GCP project with billing enabled
- Access to GCP Console
- At least **Viewer** role (we'll enable APIs through Console)

---

## Step 1: Enable APIs Through Console

### Required APIs

Visit these links and click **"ENABLE"** for each:

1. **Vertex AI API** (Required for agent deployment)
   - URL: https://console.cloud.google.com/apis/library/aiplatform.googleapis.com?project=agent-test-1764790376
   - Click: **ENABLE**

2. **Container Registry API** (Required for Docker images)
   - URL: https://console.cloud.google.com/apis/library/containerregistry.googleapis.com?project=agent-test-1764790376
   - Click: **ENABLE**

3. **Secret Manager API** (Required for secrets)
   - URL: https://console.cloud.google.com/apis/library/secretmanager.googleapis.com?project=agent-test-1764790376
   - Click: **ENABLE**

4. **Cloud Build API** (Optional - for CI/CD)
   - URL: https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com?project=agent-test-1764790376
   - Click: **ENABLE**

### Optional APIs (Skip if Permission Issues)

5. **Cloud Monitoring API** (Optional - for metrics)
   - URL: https://console.cloud.google.com/apis/library/monitoring.googleapis.com?project=agent-test-1764790376
   - Click: **ENABLE** (if allowed)
   - **If this fails, skip it - not required for testing**

6. **Cloud Trace API** (Optional - for tracing)
   - URL: https://console.cloud.google.com/apis/library/cloudtrace.googleapis.com?project=agent-test-1764790376
   - Click: **ENABLE** (if allowed)
   - **If this fails, skip it - not required for testing**

---

## Step 2: Create Secrets Manually

### Option A: Through Console (Easier)

1. **Go to Secret Manager:**
   - URL: https://console.cloud.google.com/security/secret-manager?project=agent-test-1764790376

2. **Create `jwt-secret`:**
   - Click: **CREATE SECRET**
   - Name: `jwt-secret`
   - Secret value: Generate with: `openssl rand -hex 32`
   - Click: **CREATE SECRET**

3. **Create `redis-url`:**
   - Click: **CREATE SECRET**
   - Name: `redis-url`
   - Secret value: `redis://localhost:6379` (for local testing)
   - Click: **CREATE SECRET**

### Option B: Through gcloud (If Console Fails)

```bash
# Generate and create jwt-secret
echo -n "$(openssl rand -hex 32)" | \
    gcloud secrets create jwt-secret \
    --project=agent-test-1764790376 \
    --data-file=-

# Create redis-url
echo -n "redis://localhost:6379" | \
    gcloud secrets create redis-url \
    --project=agent-test-1764790376 \
    --data-file=-
```

---

## Step 3: Grant Yourself Permissions

### Check Current Permissions

```bash
# See what roles you have
gcloud projects get-iam-policy agent-test-1764790376 \
    --flatten="bindings[].members" \
    --filter="bindings.members:$(gcloud config get-value account)"
```

### Request Necessary Permissions

Ask your project owner to grant you these roles:

```bash
# Minimum roles needed for testing
gcloud projects add-iam-policy-binding agent-test-1764790376 \
    --member="user:sagarmadhukar.jadhav@gmail.com" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding agent-test-1764790376 \
    --member="user:sagarmadhukar.jadhav@gmail.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding agent-test-1764790376 \
    --member="user:sagarmadhukar.jadhav@gmail.com" \
    --role="roles/secretmanager.secretAccessor"
```

**Or** if you're the owner:

```bash
# Grant yourself owner role
gcloud projects add-iam-policy-binding agent-test-1764790376 \
    --member="user:sagarmadhukar.jadhav@gmail.com" \
    --role="roles/owner"
```

---

## Step 4: Test Local Setup First

Before deploying to GCP, test locally:

```bash
# Set your project
export PROJECT_ID="agent-test-1764790376"
gcloud config set project $PROJECT_ID

# Authenticate
gcloud auth application-default login

# Start Redis
docker run -d --name redis-test -p 6379:6379 redis:7-alpine

# Install dependencies
uv sync

# Create .env
cat > .env << EOF
GOOGLE_CLOUD_PROJECT=${PROJECT_ID}
LOCATION=us-central1
MODEL=gemini-1.5-pro
JWT_SECRET=$(openssl rand -hex 32)
CACHE_BACKEND=redis
REDIS_URL=redis://localhost:6379
ENABLE_TRACING=false
ENABLE_METRICS=true
EOF

# Run tests
uv run pytest tests/ -v

# Start server
uv run python main.py
```

Test endpoints:

```bash
# Health check
curl http://localhost:8080/health

# Chat test
curl -X POST http://localhost:8080/chat \
    -H "Content-Type: application/json" \
    -H "X-API-Key: demo-api-key" \
    -d '{"message": "Hello!", "session_id": "test"}'
```

---

## Step 5: Build Docker Image

### Option A: Cloud Build (Recommended - No Local Docker Required)

```bash
# Build image in GCP
chmod +x scripts/build-image-cloud.sh
./scripts/build-image-cloud.sh
```

**Benefits:**
- ✅ No local Docker required
- ✅ Faster builds (uses GCP infrastructure)
- ✅ Automatically pushes to Container Registry
- ✅ Better for large images
- ✅ Consistent build environment

**Time:** 2-5 minutes

### Option B: Local Docker Build

```bash
# Build locally (requires Docker Desktop)
docker build -f Dockerfile.uv -t gcr.io/agent-test-1764790376/agent-enterprise-pack:latest .

# Configure Docker for GCR
gcloud auth configure-docker

# Push to Container Registry
docker push gcr.io/agent-test-1764790376/agent-enterprise-pack:latest
```

**Time:** 5-10 minutes (depending on your machine)

---

## Step 6: Deploy to Vertex AI

### Option A: Using Deployment Script

```bash
# Deploy to Vertex AI
chmod +x scripts/deploy-to-vertex-ai.sh
./scripts/deploy-to-vertex-ai.sh
```

Follow the prompts:
- Project ID: `agent-test-1764790376`
- Region: `us-central1`
- Build image: `y` (choose Cloud Build option)
- Test inference: `y`

### Option B: Manual Deployment

```bash
# Set variables
export PROJECT_ID="agent-test-1764790376"
export REGION="us-central1"
export AGENT_NAME="agent-enterprise-pack"
export IMAGE="gcr.io/${PROJECT_ID}/${AGENT_NAME}:latest"

# Build Docker image
docker build -f Dockerfile.uv -t $IMAGE .

# Configure Docker for GCR
gcloud auth configure-docker

# Push image
docker push $IMAGE

# Deploy to Vertex AI
gcloud ai agents deploy $AGENT_NAME \
    --region=$REGION \
    --display-name="Agent Enterprise Pack" \
    --container-image=$IMAGE \
    --container-port=8080 \
    --container-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},LOCATION=${REGION},MODEL=gemini-1.5-pro" \
    --container-secrets="JWT_SECRET=jwt-secret:latest,REDIS_URL=redis-url:latest" \
    --min-replicas=1 \
    --max-replicas=3 \
    --cpu=2 \
    --memory=4Gi \
    --timeout=300s
```

---

## Step 6: Test Deployed Agent

### Get Agent Endpoint

```bash
# Get the endpoint URL
ENDPOINT=$(gcloud ai agents describe agent-enterprise-pack \
    --region=us-central1 \
    --project=agent-test-1764790376 \
    --format='value(endpoint)')

echo "Agent endpoint: $ENDPOINT"
```

### Test Health Endpoint

```bash
# Test health
curl -f "$ENDPOINT/health" \
    -H "Authorization: Bearer $(gcloud auth print-access-token)"
```

### Test Chat Endpoint

```bash
# Test inference
curl -X POST "$ENDPOINT/chat" \
    -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    -H "Content-Type: application/json" \
    -d '{
        "message": "Hello! This is a test from Vertex AI.",
        "session_id": "vertex-test-123"
    }'
```

---

## Step 7: Monitor Your Deployment

### View Logs

```bash
# View recent logs
gcloud logging read \
    "resource.type=aiplatform.googleapis.com/Agent
     resource.labels.agent_id=agent-enterprise-pack" \
    --project=agent-test-1764790376 \
    --limit=50 \
    --format=json

# Tail logs in real-time
gcloud logging tail \
    "resource.type=aiplatform.googleapis.com/Agent" \
    --project=agent-test-1764790376
```

### View in Console

- **Vertex AI Console:** https://console.cloud.google.com/vertex-ai/agents?project=agent-test-1764790376
- **Logs:** https://console.cloud.google.com/logs?project=agent-test-1764790376
- **Metrics:** https://console.cloud.google.com/monitoring?project=agent-test-1764790376

---

## 🐛 Troubleshooting

### Issue: "Permission denied" when pushing to GCR

```bash
# Configure Docker authentication
gcloud auth configure-docker

# Or use artifact registry
gcloud auth configure-docker us-central1-docker.pkg.dev
```

### Issue: "Agent not found" after deployment

```bash
# List all agents
gcloud ai agents list --region=us-central1 --project=agent-test-1764790376

# Check deployment status
gcloud ai agents describe agent-enterprise-pack \
    --region=us-central1 \
    --project=agent-test-1764790376
```

### Issue: "Service account permissions" error

```bash
# Grant service account permissions
PROJECT_NUMBER=$(gcloud projects describe agent-test-1764790376 --format='value(projectNumber)')

gcloud projects add-iam-policy-binding agent-test-1764790376 \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/aiplatform.user"
```

---

## ✅ Verification Checklist

- [ ] APIs enabled (Vertex AI, Container Registry, Secret Manager)
- [ ] Secrets created (jwt-secret, redis-url)
- [ ] Permissions granted (aiplatform.user, storage.admin)
- [ ] Local testing works
- [ ] Docker image built and pushed
- [ ] Agent deployed to Vertex AI
- [ ] Health endpoint responds
- [ ] Chat endpoint works
- [ ] Logs visible in Console

---

## 📊 Expected Costs

**For testing (1-2 hours):**
- Vertex AI Agent Engine: ~$0.10
- Container Registry: ~$0.01
- Secret Manager: Free (first 6 secrets)
- **Total: < $0.50**

**For continuous testing (1 month):**
- Vertex AI (1 replica, low traffic): ~$5-10
- Container Registry: ~$1
- Secret Manager: Free
- **Total: ~$6-11/month**

---

## 🎯 Quick Commands Reference

```bash
# Set project
gcloud config set project agent-test-1764790376

# Authenticate
gcloud auth application-default login

# Deploy
./scripts/deploy-to-vertex-ai.sh

# Test
curl -f "$(gcloud ai agents describe agent-enterprise-pack --region=us-central1 --format='value(endpoint)')/health" \
    -H "Authorization: Bearer $(gcloud auth print-access-token)"

# View logs
gcloud logging tail "resource.type=aiplatform.googleapis.com/Agent"
```

---

## 📚 Next Steps

1. ✅ Complete this manual setup
2. ✅ Test on Vertex AI
3. ✅ Setup CI/CD: [`docs/CLOUD_BUILD_SETUP.md`](CLOUD_BUILD_SETUP.md)
4. ✅ Production deployment: [`docs/VERTEX_AI_DEPLOYMENT.md`](VERTEX_AI_DEPLOYMENT.md)

---

**Ready to deploy?** Follow the steps above and you'll have your agent running on GCP! 🚀

