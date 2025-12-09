#!/bin/bash
# Setup Cloud Build Prerequisites
# ================================
# Sets up everything needed for Cloud Build to work

set -e

echo "🔧 Setting Up Cloud Build Prerequisites"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get project ID
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
if [ -n "$CURRENT_PROJECT" ]; then
    echo -e "${BLUE}Current project: $CURRENT_PROJECT${NC}"
    read -p "Use this project? (y/n): " USE_CURRENT
    if [ "$USE_CURRENT" = "y" ] || [ "$USE_CURRENT" = "Y" ]; then
        PROJECT_ID=$CURRENT_PROJECT
    else
        read -p "Enter your GCP Project ID: " PROJECT_ID
    fi
else
    read -p "Enter your GCP Project ID: " PROJECT_ID
fi

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Project ID is required${NC}"
    exit 1
fi

gcloud config set project $PROJECT_ID
echo ""

# Step 1: Enable Cloud Build API
echo "1️⃣ Enabling Cloud Build API..."
if gcloud services list --enabled --filter="name:cloudbuild.googleapis.com" --format="value(name)" 2>/dev/null | grep -q "cloudbuild.googleapis.com"; then
    echo -e "${GREEN}✅ Cloud Build API already enabled${NC}"
else
    echo "Enabling Cloud Build API..."
    gcloud services enable cloudbuild.googleapis.com --quiet 2>/dev/null && \
        echo -e "${GREEN}✅ Cloud Build API enabled${NC}" || {
        echo -e "${YELLOW}⚠️  Could not enable automatically${NC}"
        echo ""
        echo "Please enable it manually:"
        echo "  https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com?project=$PROJECT_ID"
        echo ""
        read -p "Press Enter after enabling the API..."
    }
fi

echo ""

# Step 2: Enable Storage API
echo "2️⃣ Enabling Cloud Storage API..."
if gcloud services list --enabled --filter="name:storage.googleapis.com" --format="value(name)" 2>/dev/null | grep -q "storage.googleapis.com"; then
    echo -e "${GREEN}✅ Cloud Storage API already enabled${NC}"
else
    echo "Enabling Cloud Storage API..."
    gcloud services enable storage.googleapis.com --quiet 2>/dev/null && \
        echo -e "${GREEN}✅ Cloud Storage API enabled${NC}" || {
        echo -e "${YELLOW}⚠️  Could not enable automatically${NC}"
        echo ""
        echo "Please enable it manually:"
        echo "  https://console.cloud.google.com/apis/library/storage.googleapis.com?project=$PROJECT_ID"
        echo ""
        read -p "Press Enter after enabling the API..."
    }
fi

echo ""

# Step 3: Create Cloud Build bucket
echo "3️⃣ Creating Cloud Build storage bucket..."
BUCKET_NAME="${PROJECT_ID}_cloudbuild"

if gsutil ls -b gs://${BUCKET_NAME} &>/dev/null; then
    echo -e "${GREEN}✅ Bucket already exists: gs://${BUCKET_NAME}${NC}"
else
    echo "Creating bucket: gs://${BUCKET_NAME}"
    gsutil mb -p ${PROJECT_ID} -l us-central1 gs://${BUCKET_NAME} 2>/dev/null && \
        echo -e "${GREEN}✅ Bucket created${NC}" || {
        echo -e "${YELLOW}⚠️  Could not create bucket automatically${NC}"
        echo ""
        echo "Please create it manually:"
        echo "  1. Go to: https://console.cloud.google.com/storage/create-bucket?project=$PROJECT_ID"
        echo "  2. Bucket name: ${BUCKET_NAME}"
        echo "  3. Location: us-central1 (or your preferred region)"
        echo "  4. Storage class: Standard"
        echo "  5. Click CREATE"
        echo ""
        read -p "Press Enter after creating the bucket..."
    }
fi

echo ""

# Step 4: Grant Cloud Build service account permissions
echo "4️⃣ Setting up Cloud Build service account..."
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

echo "Cloud Build service account: $CLOUDBUILD_SA"

# Grant necessary roles
ROLES=(
    "roles/storage.admin"
    "roles/logging.logWriter"
    "roles/artifactregistry.writer"
)

for ROLE in "${ROLES[@]}"; do
    echo "Granting $ROLE..."
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:$CLOUDBUILD_SA" \
        --role="$ROLE" \
        --quiet &>/dev/null && \
        echo -e "${GREEN}✅ Granted $ROLE${NC}" || \
        echo -e "${YELLOW}⚠️  Could not grant $ROLE (may already exist)${NC}"
done

echo ""

# Step 5: Verify setup
echo "5️⃣ Verifying setup..."
echo ""

# Check APIs
echo "Checking APIs..."
REQUIRED_APIS=(
    "cloudbuild.googleapis.com:Cloud Build API"
    "storage.googleapis.com:Cloud Storage API"
)

ALL_ENABLED=true
for api_info in "${REQUIRED_APIS[@]}"; do
    IFS=':' read -r api name <<< "$api_info"
    if gcloud services list --enabled --filter="name:$api" --format="value(name)" 2>/dev/null | grep -q "$api"; then
        echo -e "${GREEN}✅ $name${NC}"
    else
        echo -e "${RED}❌ $name${NC}"
        ALL_ENABLED=false
    fi
done

echo ""

# Check bucket
echo "Checking storage bucket..."
if gsutil ls -b gs://${BUCKET_NAME} &>/dev/null; then
    echo -e "${GREEN}✅ Bucket exists: gs://${BUCKET_NAME}${NC}"
else
    echo -e "${RED}❌ Bucket not found: gs://${BUCKET_NAME}${NC}"
    ALL_ENABLED=false
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$ALL_ENABLED" = true ]; then
    echo -e "${GREEN}✅ Setup Complete!${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Cloud Build is ready to use! 🚀"
    echo ""
    echo "Next steps:"
    echo ""
    echo "  1. Build Docker image:"
    echo "     ./scripts/build-image-cloud.sh"
    echo ""
    echo "  2. Or build and deploy:"
    echo "     ./scripts/deploy-to-vertex-ai.sh"
    echo ""
else
    echo -e "${YELLOW}⚠️  Setup Incomplete${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Some items need manual setup. Please:"
    echo ""
    echo "  1. Enable missing APIs via Console"
    echo "  2. Create missing bucket via Console"
    echo "  3. Run this script again to verify"
    echo ""
fi

echo ""

