# Google Cloud Build Setup Guide

Complete guide for setting up Google Cloud Build as your CI/CD platform.

## 🔒 Why Cloud Build?

- ✅ **No service account keys** - More secure than GitHub Actions
- ✅ **Native GCP integration** - Seamless deployment to Cloud Run
- ✅ **Automatic IAM** - Uses Cloud Build service account
- ✅ **Secrets in Secret Manager** - Never leave GCP
- ✅ **Better audit logs** - Native Cloud Logging
- ✅ **Lower cost** - Cheaper for private repos

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites
- GCP project with billing enabled
- GitHub repository
- `gcloud` CLI installed

### Automated Setup

```bash
# 1. Make script executable
chmod +x scripts/setup-cloud-build.sh

# 2. Run setup script
./scripts/setup-cloud-build.sh

# 3. Follow prompts to:
#    - Enable APIs
#    - Grant permissions
#    - Create secrets
#    - Connect GitHub repo
#    - Create triggers

# 4. Push code to trigger first build
git push origin main
```

**That's it!** Your CI/CD is now running on Cloud Build.

---

## 📋 Manual Setup (Step-by-Step)

### Step 1: Enable APIs

```bash
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com \
    secretmanager.googleapis.com \
    aiplatform.googleapis.com
```

### Step 2: Grant Cloud Build Permissions

```bash
# Get Cloud Build service account
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
export CLOUD_BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

# Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/storage.admin"
```

### Step 3: Create Secrets

```bash
# JWT Secret
echo -n "$(openssl rand -hex 32)" | \
    gcloud secrets create jwt-secret --data-file=-

# Redis URL
echo -n "redis://your-redis-host:6379" | \
    gcloud secrets create redis-url --data-file=-

# Slack Webhook (optional)
echo -n "https://hooks.slack.com/services/YOUR/WEBHOOK" | \
    gcloud secrets create slack-webhook --data-file=-
```

### Step 4: Connect GitHub Repository

**Option A: GitHub App (Recommended)**

1. Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers/connect)
2. Click "Connect Repository"
3. Select "GitHub (Cloud Build GitHub App)"
4. Authenticate with GitHub
5. Select your repository
6. Click "Connect"

**Option B: Cloud Source Repository Mirror**

```bash
# Create mirror
gcloud source repos create agent-enterprise-pack

# Add remote
git remote add google \
    https://source.developers.google.com/p/${PROJECT_ID}/r/agent-enterprise-pack

# Push code
git push google main
```

### Step 5: Create Build Triggers

**CI Trigger (runs on every push):**

```bash
gcloud builds triggers create github \
    --name="ci-pipeline" \
    --repo-name="agent-enterprise-pack" \
    --repo-owner="YOUR_GITHUB_USERNAME" \
    --branch-pattern=".*" \
    --build-config="cloudbuild.yaml" \
    --description="CI Pipeline - Runs on every push"
```

**CD Trigger (runs on version tags):**

```bash
gcloud builds triggers create github \
    --name="cd-deploy" \
    --repo-name="agent-enterprise-pack" \
    --repo-owner="YOUR_GITHUB_USERNAME" \
    --tag-pattern="v.*" \
    --build-config="cloudbuild-deploy.yaml" \
    --description="CD Pipeline - Deploys on version tags"
```

### Step 6: Test the Setup

```bash
# Trigger CI
git commit -m "test: trigger cloud build" --allow-empty
git push origin main

# View build
gcloud builds list --limit=5

# View logs
gcloud builds log $(gcloud builds list --limit=1 --format='value(id)')
```

---

## 📊 Understanding the Build Files

### `cloudbuild.yaml` - CI Pipeline

**What it does:**
1. ✅ Installs UV
2. ✅ Installs dependencies
3. ✅ Runs linting (Ruff)
4. ✅ Runs type checking (mypy)
5. ✅ Runs tests with Redis
6. ✅ Runs security scans
7. ✅ Builds Docker image
8. ✅ Pushes to GCR
9. ✅ Tests Docker image

**Triggers on:**
- Push to any branch
- Pull requests

### `cloudbuild-deploy.yaml` - CD Pipeline

**What it does:**
1. 🚀 Deploys to Cloud Run
2. 🏥 Runs health checks
3. 📢 Sends Slack notification

**Triggers on:**
- Tags matching `v*.*.*` (e.g., `v1.0.0`)

---

## 🔍 Monitoring Builds

### View Builds in Console

```bash
# Open Cloud Build console
open "https://console.cloud.google.com/cloud-build/builds?project=${PROJECT_ID}"
```

### View Builds via CLI

```bash
# List recent builds
gcloud builds list --limit=10

# View specific build
gcloud builds describe BUILD_ID

# Stream logs
gcloud builds log BUILD_ID --stream

# View logs for latest build
gcloud builds log $(gcloud builds list --limit=1 --format='value(id)') --stream
```

### View Build History

```bash
# Builds by status
gcloud builds list --filter="status=SUCCESS" --limit=10
gcloud builds list --filter="status=FAILURE" --limit=10

# Builds by trigger
gcloud builds list --filter="buildTriggerId=TRIGGER_ID"
```

---

## 🐛 Troubleshooting

### Build Fails with Permission Error

```bash
# Check Cloud Build service account permissions
gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:${CLOUD_BUILD_SA}"

# Re-grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/run.admin"
```

### Cannot Access Secrets

```bash
# Grant Secret Manager access
gcloud secrets add-iam-policy-binding jwt-secret \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/secretmanager.secretAccessor"
```

### Build Times Out

```bash
# Increase timeout in cloudbuild.yaml
timeout: '3600s'  # 60 minutes

# Or use faster machine type
options:
  machineType: 'N1_HIGHCPU_32'
```

### Docker Push Fails

```bash
# Grant Storage Admin role
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/storage.admin"
```

---

## 🎯 Next Steps

1. ✅ **Test CI**: Push code and watch build run
2. ✅ **Test CD**: Create tag and watch deployment
3. ✅ **Set up notifications**: Configure Slack/email alerts
4. ✅ **Optimize builds**: Add caching, parallel steps
5. ✅ **Monitor costs**: Set up budget alerts

---

## 📚 Additional Resources

- [Cloud Build Documentation](https://cloud.google.com/build/docs)
- [Build Configuration Reference](https://cloud.google.com/build/docs/build-config-file-schema)
- [Cloud Build Pricing](https://cloud.google.com/build/pricing)
- [Best Practices](https://cloud.google.com/build/docs/best-practices)

