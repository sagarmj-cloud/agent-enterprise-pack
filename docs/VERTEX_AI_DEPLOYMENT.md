# Vertex AI Agent Engine Deployment Guide

## 🤖 Why Vertex AI Agent Engine?

The Agent Enterprise Pack is built on **Google ADK (Agent Development Kit)**, which is specifically designed for **Vertex AI Agent Engine**. This is the correct deployment target, not generic Cloud Run.

### Vertex AI Agent Engine Benefits

✅ **Purpose-Built for AI Agents**
- Native Google ADK integration
- Agent-specific orchestration
- Built-in agent lifecycle management

✅ **Enterprise Features**
- Automatic scaling for agent workloads
- Built-in observability for agents
- Integration with Vertex AI services (Gemini, embeddings, etc.)
- Agent versioning and rollback

✅ **Production-Ready**
- Multi-region deployment
- High availability
- SLA guarantees
- Enterprise support

✅ **Cost-Optimized**
- Pay only for agent inference time
- Automatic scale-to-zero
- Optimized for LLM workloads

---

## 🚀 Quick Deployment

### Option 1: Automated Script

```bash
# Make script executable
chmod +x scripts/deploy-to-vertex-ai.sh

# Run deployment
./scripts/deploy-to-vertex-ai.sh

# Follow prompts for:
# - Project ID
# - Region
# - Agent name
# - Docker image tag
```

### Option 2: Manual Deployment

```bash
# Set variables
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export AGENT_NAME="agent-enterprise-pack"

# Enable APIs
gcloud services enable aiplatform.googleapis.com

# Build and push image
docker build -f Dockerfile.uv -t gcr.io/${PROJECT_ID}/${AGENT_NAME}:latest .
docker push gcr.io/${PROJECT_ID}/${AGENT_NAME}:latest

# Deploy agent
gcloud ai agents deploy ${AGENT_NAME} \
  --region=${REGION} \
  --display-name="Agent Enterprise Pack" \
  --container-image=gcr.io/${PROJECT_ID}/${AGENT_NAME}:latest \
  --container-port=8080 \
  --container-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},LOCATION=${REGION}" \
  --container-secrets="JWT_SECRET=jwt-secret:latest,REDIS_URL=redis-url:latest" \
  --min-replicas=1 \
  --max-replicas=10 \
  --cpu=2 \
  --memory=4Gi
```

---

## 📋 Prerequisites

### 1. Enable Required APIs

```bash
gcloud services enable \
    aiplatform.googleapis.com \
    containerregistry.googleapis.com \
    secretmanager.googleapis.com \
    cloudmonitoring.googleapis.com \
    cloudtrace.googleapis.com
```

### 2. Create Secrets

```bash
# JWT Secret
echo -n "$(openssl rand -hex 32)" | \
    gcloud secrets create jwt-secret --data-file=-

# Redis URL
echo -n "redis://your-redis-host:6379" | \
    gcloud secrets create redis-url --data-file=-
```

### 3. Grant Permissions

```bash
# Get project number
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

# Grant Vertex AI service account access to secrets
gcloud secrets add-iam-policy-binding jwt-secret \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding redis-url \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

---

## 🔧 Configuration Options

### Environment Variables

```yaml
container-env-vars:
  GOOGLE_CLOUD_PROJECT: your-project-id
  LOCATION: us-central1
  MODEL: gemini-1.5-pro
  CACHE_BACKEND: redis
  RATE_LIMIT_REQUESTS: 1000
  RATE_LIMIT_WINDOW: 60
```

### Secrets (from Secret Manager)

```yaml
container-secrets:
  JWT_SECRET: jwt-secret:latest
  REDIS_URL: redis-url:latest
  SLACK_WEBHOOK_URL: slack-webhook:latest  # optional
```

### Resource Configuration

```yaml
# Compute resources
cpu: 2                    # vCPUs
memory: 4Gi              # RAM

# Scaling
min-replicas: 1          # Minimum instances
max-replicas: 10         # Maximum instances

# Timeouts
timeout: 300s            # Request timeout
```

---

## 🔄 CI/CD with Vertex AI

### Cloud Build Trigger

The `cloudbuild-deploy-vertex.yaml` file deploys to Vertex AI Agent Engine:

```bash
# Create trigger for Vertex AI deployment
gcloud builds triggers create github \
    --name="deploy-vertex-ai" \
    --repo-name="agent-enterprise-pack" \
    --repo-owner="YOUR_GITHUB_USERNAME" \
    --tag-pattern="v.*" \
    --build-config="cloudbuild-deploy-vertex.yaml"
```

### Deployment Workflow

1. **Push version tag:**
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0"
   git push origin v1.0.0
   ```

2. **Cloud Build automatically:**
   - Builds Docker image
   - Pushes to GCR
   - Deploys to Vertex AI Agent Engine
   - Runs health checks
   - Tests inference
   - Sends notifications

---

## 📊 Monitoring & Observability

### View Agent Status

```bash
# Describe agent
gcloud ai agents describe agent-enterprise-pack \
    --region=us-central1

# List all agents
gcloud ai agents list --region=us-central1
```

### View Logs

```bash
# Agent logs
gcloud logging read \
    'resource.type=aiplatform.googleapis.com/Agent
     resource.labels.agent_id=agent-enterprise-pack' \
    --limit=50 \
    --format=json

# Real-time logs
gcloud logging tail \
    'resource.type=aiplatform.googleapis.com/Agent'
```

### View Metrics

```bash
# Open Monitoring dashboard
open "https://console.cloud.google.com/monitoring/dashboards?project=${PROJECT_ID}"

# Query metrics via CLI
gcloud monitoring time-series list \
    --filter='metric.type="aiplatform.googleapis.com/agent/request_count"'
```

---

## 🧪 Testing the Agent

### Health Check

```bash
# Get endpoint
ENDPOINT=$(gcloud ai agents describe agent-enterprise-pack \
    --region=us-central1 \
    --format='value(endpoint)')

# Test health
curl -f "$ENDPOINT/health" \
    -H "Authorization: Bearer $(gcloud auth print-access-token)"
```

### Test Inference

```bash
# Send chat message
curl -X POST "$ENDPOINT/chat" \
    -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    -H "Content-Type: application/json" \
    -d '{
        "message": "Hello! What can you help me with?",
        "session_id": "test-session-123"
    }'
```

### Load Testing

```bash
# Install locust
uv pip install locust

# Run load test
uv run locust -f tests/load_test.py \
    --host=$ENDPOINT \
    --users=100 \
    --spawn-rate=10
```

---

## 🔐 Security Best Practices

### 1. Use IAM for Authentication

```bash
# Create service account for client applications
gcloud iam service-accounts create agent-client \
    --display-name="Agent Client"

# Grant Vertex AI User role
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:agent-client@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"
```

### 2. Enable VPC Service Controls

```bash
# Create service perimeter
gcloud access-context-manager perimeters create agent-perimeter \
    --resources=projects/$PROJECT_NUMBER \
    --restricted-services=aiplatform.googleapis.com
```

### 3. Use Private Endpoints

```bash
# Deploy with private endpoint
gcloud ai agents deploy agent-enterprise-pack \
    --region=us-central1 \
    --network=projects/${PROJECT_ID}/global/networks/default \
    --enable-private-endpoint
```

---

## 💰 Cost Optimization

### Pricing Model

- **Inference Time**: Pay per second of agent execution
- **Idle Time**: Minimal cost when scaled to zero
- **Storage**: GCR storage for Docker images

### Optimization Tips

1. **Use appropriate instance sizes**
   ```bash
   --cpu=1 --memory=2Gi  # For light workloads
   --cpu=4 --memory=8Gi  # For heavy workloads
   ```

2. **Configure auto-scaling**
   ```bash
   --min-replicas=0      # Scale to zero when idle
   --max-replicas=5      # Limit maximum cost
   ```

3. **Set request timeouts**
   ```bash
   --timeout=60s         # Prevent long-running requests
   ```

---

## 🎯 Next Steps

1. ✅ Deploy agent to Vertex AI
2. ✅ Test health and inference endpoints
3. ✅ Set up monitoring and alerting
4. ✅ Configure CI/CD for automated deployments
5. ✅ Implement load testing
6. ✅ Review and optimize costs

---

## 📚 Additional Resources

- [Vertex AI Agent Engine Documentation](https://cloud.google.com/vertex-ai/docs/agents)
- [Google ADK Documentation](https://cloud.google.com/vertex-ai/docs/adk)
- [Agent Deployment Best Practices](https://cloud.google.com/vertex-ai/docs/agents/deploy)
- [Monitoring Agents](https://cloud.google.com/vertex-ai/docs/agents/monitor)

