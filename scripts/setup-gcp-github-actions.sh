#!/bin/bash
# Setup GCP Service Account for GitHub Actions
# ============================================

set -e

echo "🚀 Setting up GCP access for GitHub Actions"
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

# Service account details
SA_NAME="github-actions-ci"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="github-actions-key.json"

echo ""
echo "1️⃣ Enabling required APIs..."
gcloud services enable \
    run.googleapis.com \
    containerregistry.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    aiplatform.googleapis.com \
    cloudmonitoring.googleapis.com \
    cloudtrace.googleapis.com

echo ""
echo "2️⃣ Creating service account: $SA_NAME"
if gcloud iam service-accounts describe $SA_EMAIL &> /dev/null; then
    echo "⚠️  Service account already exists, skipping creation"
else
    gcloud iam service-accounts create $SA_NAME \
        --display-name="GitHub Actions CI/CD"
    echo "✅ Service account created"
fi

echo ""
echo "3️⃣ Granting IAM permissions..."

# Cloud Run Admin
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/run.admin" \
    --quiet

# Storage Admin (for GCR)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.admin" \
    --quiet

# Service Account User
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/iam.serviceAccountUser" \
    --quiet

# Secret Manager Accessor
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet

# Artifact Registry Writer
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/artifactregistry.writer" \
    --quiet

echo "✅ Permissions granted"

echo ""
echo "4️⃣ Creating service account key..."
if [ -f "$KEY_FILE" ]; then
    echo "⚠️  Key file already exists: $KEY_FILE"
    read -p "Overwrite? (y/N): " OVERWRITE
    if [ "$OVERWRITE" != "y" ]; then
        echo "Skipping key creation"
        KEY_FILE=""
    fi
fi

if [ -n "$KEY_FILE" ]; then
    gcloud iam service-accounts keys create $KEY_FILE \
        --iam-account=$SA_EMAIL
    echo "✅ Key created: $KEY_FILE"
fi

echo ""
echo "5️⃣ Creating JWT secret in Secret Manager..."
if gcloud secrets describe jwt-secret &> /dev/null; then
    echo "⚠️  Secret 'jwt-secret' already exists, skipping"
else
    JWT_SECRET=$(openssl rand -hex 32)
    echo -n "$JWT_SECRET" | gcloud secrets create jwt-secret --data-file=-
    echo "✅ JWT secret created"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ GCP Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Next Steps:"
echo ""
echo "1. Add these secrets to GitHub:"
echo "   Go to: Settings → Secrets and variables → Actions"
echo ""
echo "   GCP_SA_KEY:"
if [ -f "$KEY_FILE" ]; then
    echo "   Copy the contents of: $KEY_FILE"
    echo ""
    echo "   Quick copy command:"
    echo "   cat $KEY_FILE | pbcopy  # macOS"
    echo "   cat $KEY_FILE | xclip -selection clipboard  # Linux"
fi
echo ""
echo "   GCP_PROJECT_ID:"
echo "   $PROJECT_ID"
echo ""
echo "   GCP_REGION:"
echo "   us-central1  (or your preferred region)"
echo ""
echo "2. Set up Redis (if needed):"
echo "   gcloud redis instances create agent-cache \\"
echo "     --size=1 \\"
echo "     --region=us-central1 \\"
echo "     --redis-version=redis_7_0"
echo ""
echo "3. Push code to GitHub and watch CI/CD run!"
echo ""
echo "⚠️  IMPORTANT: Keep $KEY_FILE secure and delete after adding to GitHub"
echo ""

