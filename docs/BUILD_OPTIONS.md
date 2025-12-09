# Docker Image Build Options

Guide to building the Docker image for the Agent Enterprise Pack.

---

## 🎯 Three Ways to Build

### **Option 1: Cloud Build** (Recommended) ⭐

**Best for:** Everyone, especially if you don't have Docker Desktop

**Command:**
```bash
./scripts/build-image-cloud.sh
```

**Pros:**
- ✅ No local Docker required
- ✅ Faster builds (2-5 minutes)
- ✅ Uses GCP's powerful infrastructure
- ✅ Automatically pushes to Container Registry
- ✅ Consistent build environment
- ✅ Better for large images
- ✅ Can choose machine type (faster = higher cost)

**Cons:**
- ⚠️ Requires Cloud Build API enabled
- ⚠️ Small cost (~$0.01-0.05 per build)

**Requirements:**
- GCP project with billing
- Cloud Build API enabled
- `gcloud` CLI authenticated

**Time:** 2-5 minutes

---

### **Option 2: Local Docker Build**

**Best for:** When you already have Docker Desktop and want to test locally first

**Command:**
```bash
# Build
docker build -f Dockerfile.uv -t gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest .

# Configure Docker for GCR
gcloud auth configure-docker

# Push
docker push gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest
```

**Pros:**
- ✅ No GCP costs for building
- ✅ Can test image locally before pushing
- ✅ Full control over build process

**Cons:**
- ⚠️ Requires Docker Desktop installed
- ⚠️ Slower on older machines (5-10 minutes)
- ⚠️ Uses local CPU/memory
- ⚠️ Requires manual push to GCR

**Requirements:**
- Docker Desktop installed and running
- `gcloud` CLI authenticated
- Sufficient disk space (~2GB)

**Time:** 5-10 minutes

---

### **Option 3: Automated via Deployment Script**

**Best for:** When deploying to Vertex AI

**Command:**
```bash
./scripts/deploy-to-vertex-ai.sh
```

**What it does:**
- Prompts you to build image
- Lets you choose Cloud Build or Local Docker
- Automatically deploys to Vertex AI after building

**Pros:**
- ✅ All-in-one solution
- ✅ Builds and deploys in one command
- ✅ Interactive prompts guide you

**Cons:**
- ⚠️ Less control over individual steps

**Time:** 5-15 minutes (build + deploy)

---

## 📊 Comparison Table

| Feature | Cloud Build | Local Docker | Deployment Script |
|---------|-------------|--------------|-------------------|
| **Speed** | ⚡⚡⚡ Fast (2-5 min) | ⚡⚡ Medium (5-10 min) | ⚡⚡ Medium (5-15 min) |
| **Cost** | ~$0.01-0.05 | Free | ~$0.01-0.05 |
| **Docker Required** | ❌ No | ✅ Yes | Depends on choice |
| **GCP APIs Required** | Cloud Build | Container Registry | Both |
| **Best For** | Production | Development | Quick deployment |
| **Difficulty** | 🟢 Easy | 🟡 Medium | 🟢 Easy |

---

## 🚀 Quick Start Guide

### For First-Time Users (Recommended)

```bash
# 1. Enable Cloud Build API
open "https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com?project=YOUR_PROJECT_ID"

# 2. Build with Cloud Build
./scripts/build-image-cloud.sh

# 3. Deploy to Vertex AI
./scripts/deploy-to-vertex-ai.sh
```

### For Developers with Docker

```bash
# 1. Build locally
docker build -f Dockerfile.uv -t gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest .

# 2. Test locally
docker run -p 8080:8080 --env-file .env gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest

# 3. Push to GCR
gcloud auth configure-docker
docker push gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest

# 4. Deploy to Vertex AI
./scripts/deploy-to-vertex-ai.sh
```

---

## 🔧 Detailed Instructions

### Cloud Build Setup

1. **Enable Cloud Build API:**
   ```bash
   # Via Console (recommended)
   open "https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com?project=YOUR_PROJECT_ID"
   
   # Or via gcloud (if you have permissions)
   gcloud services enable cloudbuild.googleapis.com
   ```

2. **Run build script:**
   ```bash
   ./scripts/build-image-cloud.sh
   ```

3. **Choose options:**
   - Dockerfile: `Dockerfile.uv` (recommended)
   - Machine type: `n1-highcpu-8` (fast, recommended)

4. **Wait for build:**
   - Build takes 2-5 minutes
   - Progress shown in terminal
   - Can view in Console: https://console.cloud.google.com/cloud-build/builds

5. **Verify:**
   ```bash
   gcloud container images list --repository=gcr.io/YOUR_PROJECT_ID
   ```

### Local Docker Build Setup

1. **Install Docker Desktop:**
   - macOS: https://docs.docker.com/desktop/install/mac-install/
   - Windows: https://docs.docker.com/desktop/install/windows-install/
   - Linux: https://docs.docker.com/desktop/install/linux-install/

2. **Start Docker:**
   ```bash
   # macOS
   open -a Docker
   
   # Verify Docker is running
   docker info
   ```

3. **Build image:**
   ```bash
   docker build -f Dockerfile.uv -t gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest .
   ```

4. **Test locally (optional):**
   ```bash
   # Create .env file first
   docker run -p 8080:8080 --env-file .env gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest
   
   # Test in another terminal
   curl http://localhost:8080/health
   ```

5. **Push to GCR:**
   ```bash
   gcloud auth configure-docker
   docker push gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest
   ```

---

## 💰 Cost Comparison

### Cloud Build Costs

**Build costs:**
- n1-highcpu-8: ~$0.01-0.02 per build
- n1-highcpu-32: ~$0.03-0.05 per build
- e2-highcpu-8: ~$0.005-0.01 per build

**Free tier:**
- First 120 build-minutes per day: FREE
- For typical builds (2-5 min), you get ~24-60 free builds per day

**Monthly estimate (10 builds/day):**
- ~$3-5/month

### Local Docker Costs

**Build costs:**
- Free (uses your machine)

**Hidden costs:**
- Electricity
- Machine wear
- Your time waiting

---

## 🐛 Troubleshooting

### Cloud Build Issues

**Error: "Cloud Build API not enabled"**
```bash
# Enable via Console
open "https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com?project=YOUR_PROJECT_ID"
```

**Error: "Permission denied"**
```bash
# Grant yourself Cloud Build permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:YOUR_EMAIL" \
    --role="roles/cloudbuild.builds.editor"
```

**Error: "Build timeout"**
```bash
# Increase timeout in build command
gcloud builds submit --timeout=20m ...
```

### Local Docker Issues

**Error: "Cannot connect to Docker daemon"**
```bash
# Start Docker Desktop
open -a Docker

# Wait for Docker to start, then try again
docker info
```

**Error: "No space left on device"**
```bash
# Clean up Docker
docker system prune -a

# Free up disk space
```

**Error: "denied: Token exchange failed"**
```bash
# Re-authenticate Docker
gcloud auth configure-docker
```

---

## ✅ Verification

After building, verify the image:

```bash
# List images in GCR
gcloud container images list --repository=gcr.io/YOUR_PROJECT_ID

# Describe specific image
gcloud container images describe gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest

# Pull and test locally
docker pull gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest
docker run -p 8080:8080 --env-file .env gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest
```

---

## 📚 Next Steps

After building the image:

1. **Deploy to Vertex AI:**
   ```bash
   ./scripts/deploy-to-vertex-ai.sh
   ```

2. **Test locally:**
   ```bash
   docker run -p 8080:8080 --env-file .env gcr.io/YOUR_PROJECT_ID/agent-enterprise-pack:latest
   ```

3. **Setup CI/CD:**
   ```bash
   ./scripts/setup-cloud-build.sh
   ```

---

## 🎯 Recommendation

**For most users:** Use **Cloud Build** (Option 1)

**Why?**
- ✅ Fastest and easiest
- ✅ No local setup required
- ✅ Consistent builds
- ✅ Very low cost (~$0.01 per build)
- ✅ First 120 minutes/day are FREE

**Command:**
```bash
./scripts/build-image-cloud.sh
```

That's it! 🚀

