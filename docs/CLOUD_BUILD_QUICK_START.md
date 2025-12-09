# Cloud Build Quick Start

Build Docker images in GCP without local Docker.

---

## 🚀 Quick Start (3 Commands)

```bash
# 1. Enable Cloud Build API
open "https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com?project=YOUR_PROJECT_ID"

# 2. Build image in GCP
./scripts/build-image-cloud.sh

# 3. Deploy to Vertex AI
./scripts/deploy-to-vertex-ai.sh
```

**Total time:** ~10 minutes

---

## 📋 Three Ways to Build with Cloud Build

### **Method 1: Using Script** (Easiest)

```bash
./scripts/build-image-cloud.sh
```

**What it does:**
- Interactive prompts
- Checks if API is enabled
- Lets you choose Dockerfile and machine type
- Builds in GCP
- Verifies image

---

### **Method 2: Using Config File** (Direct)

```bash
# Build with default config
gcloud builds submit --config=cloudbuild-build-only.yaml

# Or with custom tag
gcloud builds submit \
    --config=cloudbuild-build-only.yaml \
    --substitutions=TAG_NAME=v1.0.0
```

**What it does:**
- Uses `cloudbuild-build-only.yaml`
- Builds with Dockerfile.uv
- Tags as `latest` and your custom tag
- Pushes to Container Registry

---

### **Method 3: One-Line Command** (Quickest)

```bash
# Simple build and push
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest
```

**What it does:**
- Uses default Dockerfile
- Builds and pushes in one command
- Tags as `latest`

**Note:** This uses the default `Dockerfile`, not `Dockerfile.uv`. For UV support, use Method 1 or 2.

---

## 🔧 Configuration Files

### **`cloudbuild-build-only.yaml`** (Simple build)

```yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-f', 'Dockerfile.uv', '-t', 'gcr.io/${PROJECT_ID}/agent-enterprise-pack:latest', '.']
images:
  - 'gcr.io/${PROJECT_ID}/agent-enterprise-pack:latest'
options:
  machineType: 'N1_HIGHCPU_8'
```

**Usage:**
```bash
gcloud builds submit --config=cloudbuild-build-only.yaml
```

---

### **`cloudbuild.yaml`** (Full CI pipeline)

Includes:
- Linting
- Type checking
- Tests
- Security scans
- Docker build
- Docker test

**Usage:**
```bash
gcloud builds submit --config=cloudbuild.yaml
```

---

### **`cloudbuild-deploy-vertex.yaml`** (Build + Deploy)

Includes:
- Docker build
- Push to GCR
- Deploy to Vertex AI

**Usage:**
```bash
gcloud builds submit --config=cloudbuild-deploy-vertex.yaml
```

---

## 💰 Pricing

### Free Tier
- **120 build-minutes per day: FREE**
- For a 3-minute build = **40 free builds/day**

### Machine Types

| Machine Type | Speed | Cost per Minute | 3-Min Build Cost |
|--------------|-------|-----------------|------------------|
| e2-highcpu-8 | Slow | $0.003 | ~$0.01 |
| n1-highcpu-8 | Fast | $0.005 | ~$0.015 |
| n1-highcpu-32 | Very Fast | $0.020 | ~$0.06 |

**Recommendation:** Use `n1-highcpu-8` (good balance of speed and cost)

---

## 🎯 Common Commands

### Build with Different Tags

```bash
# Build with version tag
gcloud builds submit \
    --config=cloudbuild-build-only.yaml \
    --substitutions=TAG_NAME=v1.0.0

# Build with git commit SHA
gcloud builds submit \
    --config=cloudbuild-build-only.yaml \
    --substitutions=TAG_NAME=$(git rev-parse --short HEAD)

# Build with date tag
gcloud builds submit \
    --config=cloudbuild-build-only.yaml \
    --substitutions=TAG_NAME=$(date +%Y%m%d-%H%M%S)
```

---

### View Build Status

```bash
# List recent builds
gcloud builds list --limit=10

# View specific build
gcloud builds describe BUILD_ID

# Stream logs for running build
gcloud builds log BUILD_ID --stream

# View in Console
open "https://console.cloud.google.com/cloud-build/builds?project=YOUR_PROJECT_ID"
```

---

### Cancel Build

```bash
# Cancel running build
gcloud builds cancel BUILD_ID
```

---

## 🐛 Troubleshooting

### Error: "API not enabled"

```bash
# Enable via Console (recommended)
open "https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com?project=YOUR_PROJECT_ID"

# Or via gcloud (if you have permissions)
gcloud services enable cloudbuild.googleapis.com
```

---

### Error: "Permission denied"

```bash
# Grant yourself Cloud Build permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:YOUR_EMAIL" \
    --role="roles/cloudbuild.builds.editor"
```

---

### Error: "Build timeout"

```bash
# Increase timeout in cloudbuild.yaml
timeout: '1800s'  # 30 minutes

# Or in command
gcloud builds submit --timeout=30m --config=cloudbuild-build-only.yaml
```

---

### Error: "Dockerfile not found"

Make sure you're running from the project root:

```bash
# Check current directory
pwd

# Should be: /path/to/agent-enterprise-pack

# List files
ls -la Dockerfile.uv
```

---

## ✅ Verification

After building, verify the image:

```bash
# List images
gcloud container images list --repository=gcr.io/YOUR_PROJECT_ID

# Describe image
gcloud container images describe gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest

# Pull and test locally
docker pull gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest
docker run -p 8080:8080 --env-file .env gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest

# Test health endpoint
curl http://localhost:8080/health
```

---

## 📚 Next Steps

After building the image:

1. **Deploy to Vertex AI:**
   ```bash
   ./scripts/deploy-to-vertex-ai.sh
   ```

2. **Setup automated builds:**
   ```bash
   ./scripts/setup-cloud-build.sh
   ```

3. **View build history:**
   ```bash
   gcloud builds list --limit=20
   ```

---

## 🎯 Best Practices

1. **Use tags:** Always tag images with versions, not just `latest`
2. **Monitor costs:** Set up budget alerts in GCP Console
3. **Use caching:** Cloud Build caches layers automatically
4. **Choose right machine:** Balance speed vs cost
5. **Review logs:** Check build logs for optimization opportunities

---

## 📖 Related Documentation

- **[Build Options](BUILD_OPTIONS.md)** - Compare all build methods
- **[GCP Setup Manual](GCP_SETUP_MANUAL.md)** - Complete GCP setup
- **[Vertex AI Deployment](VERTEX_AI_DEPLOYMENT.md)** - Deploy to Vertex AI

---

## 🆘 Need Help?

**Quick fix for most issues:**

```bash
# 1. Make sure you're in the right directory
cd /path/to/agent-enterprise-pack

# 2. Make sure API is enabled
open "https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com?project=YOUR_PROJECT_ID"

# 3. Use the script (handles everything)
./scripts/build-image-cloud.sh
```

---

**Ready to build?** Run this now:

```bash
./scripts/build-image-cloud.sh
```

🚀

