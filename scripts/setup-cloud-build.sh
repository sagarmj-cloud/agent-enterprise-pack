#!/bin/bash
# Setup Google Cloud Build for CI/CD
# ===================================

set -e

echo "🏗️  Setting up Google Cloud Build for CI/CD"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Get project ID
read -p "Enter your GCP Project ID: " PROJECT_ID
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: Project ID is required"
    exit 1
fi

echo ""
echo "📋 Using project: $PROJECT_ID"
gcloud config set project $PROJECT_ID

# Get project number
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
CLOUD_BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

echo ""
echo "1️⃣ Enabling required APIs..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    aiplatform.googleapis.com \
    cloudmonitoring.googleapis.com \
    cloudtrace.googleapis.com \
    sourcerepo.googleapis.com

echo "✅ APIs enabled"

echo ""
echo "2️⃣ Granting Cloud Build service account permissions..."

# Cloud Run Admin
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/run.admin" \
    --quiet

# Service Account User
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/iam.serviceAccountUser" \
    --quiet

# Secret Manager Accessor
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet

# Storage Admin (for GCR)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/storage.admin" \
    --quiet

# Artifact Registry Writer
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/artifactregistry.writer" \
    --quiet

# Vertex AI User
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/aiplatform.user" \
    --quiet

echo "✅ Permissions granted to Cloud Build service account"

echo ""
echo "3️⃣ Creating secrets in Secret Manager..."

# JWT Secret
if gcloud secrets describe jwt-secret &> /dev/null; then
    echo "⚠️  Secret 'jwt-secret' already exists"
else
    JWT_SECRET=$(openssl rand -hex 32)
    echo -n "$JWT_SECRET" | gcloud secrets create jwt-secret --data-file=-
    echo "✅ JWT secret created"
fi

# Redis URL (placeholder)
if gcloud secrets describe redis-url &> /dev/null; then
    echo "⚠️  Secret 'redis-url' already exists"
else
    read -p "Enter Redis URL (or press Enter to use placeholder): " REDIS_URL
    if [ -z "$REDIS_URL" ]; then
        REDIS_URL="redis://localhost:6379"
    fi
    echo -n "$REDIS_URL" | gcloud secrets create redis-url --data-file=-
    echo "✅ Redis URL secret created"
fi

# Slack Webhook (optional)
if gcloud secrets describe slack-webhook &> /dev/null; then
    echo "⚠️  Secret 'slack-webhook' already exists"
else
    read -p "Enter Slack Webhook URL (or press Enter to skip): " SLACK_WEBHOOK
    if [ -n "$SLACK_WEBHOOK" ]; then
        echo -n "$SLACK_WEBHOOK" | gcloud secrets create slack-webhook --data-file=-
        echo "✅ Slack webhook secret created"
    else
        echo "⏭️  Skipping Slack webhook"
    fi
fi

echo ""
echo "4️⃣ Connecting GitHub repository..."
echo ""
echo "Choose connection method:"
echo "  1) GitHub App (Recommended - more secure)"
echo "  2) Cloud Source Repository mirror"
read -p "Enter choice (1 or 2): " CHOICE

if [ "$CHOICE" = "1" ]; then
    echo ""
    echo "📱 Setting up GitHub App connection..."
    echo ""
    echo "Follow these steps:"
    echo "1. Go to: https://console.cloud.google.com/cloud-build/triggers/connect"
    echo "2. Select 'GitHub (Cloud Build GitHub App)'"
    echo "3. Authenticate with GitHub"
    echo "4. Select your repository"
    echo ""
    read -p "Press Enter when done..."
    
elif [ "$CHOICE" = "2" ]; then
    echo ""
    echo "🔄 Setting up Cloud Source Repository mirror..."
    read -p "Enter your GitHub repo (format: username/repo): " GITHUB_REPO
    
    gcloud source repos create agent-enterprise-pack || true
    
    echo ""
    echo "Add this as a remote to your local repo:"
    echo "git remote add google https://source.developers.google.com/p/${PROJECT_ID}/r/agent-enterprise-pack"
    echo ""
    echo "Then push: git push google main"
fi

echo ""
echo "5️⃣ Creating Cloud Build triggers..."

# CI Trigger (on push to any branch)
gcloud builds triggers create github \
    --name="ci-pipeline" \
    --repo-name="agent-enterprise-pack" \
    --repo-owner="YOUR_GITHUB_USERNAME" \
    --branch-pattern=".*" \
    --build-config="cloudbuild.yaml" \
    --description="CI Pipeline - Runs on every push" \
    2>/dev/null || echo "⚠️  CI trigger may already exist"

# CD Trigger (on tag push)
gcloud builds triggers create github \
    --name="cd-deploy" \
    --repo-name="agent-enterprise-pack" \
    --repo-owner="YOUR_GITHUB_USERNAME" \
    --tag-pattern="v.*" \
    --build-config="cloudbuild-deploy.yaml" \
    --description="CD Pipeline - Deploys on version tags" \
    2>/dev/null || echo "⚠️  CD trigger may already exist"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Cloud Build Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Next Steps:"
echo ""
echo "1. Update Cloud Build triggers with your GitHub username:"
echo "   https://console.cloud.google.com/cloud-build/triggers"
echo ""
echo "2. Push code to trigger CI:"
echo "   git push origin main"
echo ""
echo "3. Create a tag to trigger deployment:"
echo "   git tag -a v1.0.0 -m 'Release v1.0.0'"
echo "   git push origin v1.0.0"
echo ""
echo "4. View builds:"
echo "   https://console.cloud.google.com/cloud-build/builds"
echo ""
echo "🔒 Security Benefits:"
echo "   ✅ No service account keys needed"
echo "   ✅ Automatic IAM integration"
echo "   ✅ Secrets in Secret Manager"
echo "   ✅ Native GCP audit logs"
echo ""

