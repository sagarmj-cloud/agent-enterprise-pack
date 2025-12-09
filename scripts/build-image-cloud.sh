#!/bin/bash
# Build Docker Image using Cloud Build
# =====================================
# Builds the Docker image in GCP instead of locally

set -e

echo "🏗️  Building Docker Image with Cloud Build"
echo "=========================================="
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

# Get image tag
read -p "Enter image tag [latest]: " TAG
TAG=${TAG:-latest}

IMAGE_NAME="agent-enterprise-pack"
IMAGE="gcr.io/${PROJECT_ID}/${IMAGE_NAME}:${TAG}"

echo ""
echo -e "${BLUE}Configuration:${NC}"
echo "  Project: $PROJECT_ID"
echo "  Image: $IMAGE"
echo ""

# Check if Cloud Build API is enabled
echo "1️⃣ Checking Cloud Build API..."
if gcloud services list --enabled --filter="name:cloudbuild.googleapis.com" --format="value(name)" 2>/dev/null | grep -q "cloudbuild.googleapis.com"; then
    echo -e "${GREEN}✅ Cloud Build API enabled${NC}"
else
    echo -e "${YELLOW}⚠️  Cloud Build API not enabled${NC}"
    echo ""
    echo "Please enable it manually:"
    echo "  https://console.cloud.google.com/apis/library/cloudbuild.googleapis.com?project=$PROJECT_ID"
    echo ""
    read -p "Press Enter after enabling the API, or Ctrl+C to exit..."
fi

echo ""

# Create Cloud Build bucket if it doesn't exist
echo "Setting up Cloud Build storage..."
BUCKET_NAME="${PROJECT_ID}_cloudbuild"
if ! gsutil ls -b gs://${BUCKET_NAME} &>/dev/null; then
    echo "Creating Cloud Build bucket: gs://${BUCKET_NAME}"
    gsutil mb -p ${PROJECT_ID} gs://${BUCKET_NAME} 2>/dev/null || {
        echo -e "${YELLOW}⚠️  Could not create bucket automatically${NC}"
        echo ""
        echo "Please create it manually:"
        echo "  https://console.cloud.google.com/storage/create-bucket?project=$PROJECT_ID"
        echo ""
        echo "Bucket name: ${BUCKET_NAME}"
        echo ""
        read -p "Press Enter after creating the bucket, or Ctrl+C to exit..."
    }
else
    echo -e "${GREEN}✅ Cloud Build bucket exists${NC}"
fi

echo ""

# Choose Dockerfile
echo "2️⃣ Choose Dockerfile:"
echo "  1. Dockerfile.uv (recommended - uses UV package manager)"
echo "  2. Dockerfile (standard)"
echo ""
read -p "Enter choice (1-2) [1]: " DOCKERFILE_CHOICE
DOCKERFILE_CHOICE=${DOCKERFILE_CHOICE:-1}

if [ "$DOCKERFILE_CHOICE" = "1" ]; then
    DOCKERFILE="Dockerfile.uv"
else
    DOCKERFILE="Dockerfile"
fi

echo ""
echo -e "${BLUE}Using: $DOCKERFILE${NC}"
echo ""

# Choose machine type
echo "3️⃣ Choose build machine type:"
echo "  1. n1-highcpu-8 (fast, recommended)"
echo "  2. n1-highcpu-32 (very fast, higher cost)"
echo "  3. e2-highcpu-8 (slower, lower cost)"
echo ""
read -p "Enter choice (1-3) [1]: " MACHINE_CHOICE
MACHINE_CHOICE=${MACHINE_CHOICE:-1}

case $MACHINE_CHOICE in
    1)
        MACHINE_TYPE="n1-highcpu-8"
        ;;
    2)
        MACHINE_TYPE="n1-highcpu-32"
        ;;
    3)
        MACHINE_TYPE="e2-highcpu-8"
        ;;
    *)
        MACHINE_TYPE="n1-highcpu-8"
        ;;
esac

echo ""
echo -e "${BLUE}Using: $MACHINE_TYPE${NC}"
echo ""

# Build with Cloud Build
echo "4️⃣ Building image in GCP..."
echo ""
echo -e "${YELLOW}This will take 2-5 minutes depending on machine type...${NC}"
echo ""

# Create cloudbuild.yaml for the build
MACHINE_TYPE_UPPER=$(echo $MACHINE_TYPE | tr '[:lower:]' '[:upper:]' | tr '-' '_')

cat > /tmp/cloudbuild-temp.yaml << EOF
steps:
  - name: 'gcr.io/cloud-builders/docker'
    id: 'docker-build'
    args:
      - 'build'
      - '-f'
      - '$DOCKERFILE'
      - '-t'
      - '$IMAGE'
      - '.'

images:
  - '$IMAGE'

options:
  machineType: '$MACHINE_TYPE_UPPER'
  diskSizeGb: 50
  logging: CLOUD_LOGGING_ONLY

timeout: '900s'
EOF

echo "Using build configuration:"
cat /tmp/cloudbuild-temp.yaml
echo ""

# Submit build
gcloud builds submit \
    --config=/tmp/cloudbuild-temp.yaml \
    --project=$PROJECT_ID \
    . || {
        echo ""
        echo -e "${RED}❌ Build failed${NC}"
        echo ""
        echo "Common issues:"
        echo "  1. Cloud Build API not enabled"
        echo "  2. Insufficient permissions"
        echo "  3. Dockerfile syntax errors"
        echo ""
        echo "View build logs:"
        echo "  https://console.cloud.google.com/cloud-build/builds?project=$PROJECT_ID"
        rm -f /tmp/cloudbuild-temp.yaml
        exit 1
    }

# Clean up
rm -f /tmp/cloudbuild-temp.yaml

echo ""
echo -e "${GREEN}✅ Image built successfully!${NC}"
echo ""

# Verify image
echo "5️⃣ Verifying image..."
if gcloud container images describe $IMAGE &>/dev/null; then
    echo -e "${GREEN}✅ Image verified in Container Registry${NC}"
    
    # Get image details
    IMAGE_SIZE=$(gcloud container images describe $IMAGE --format='value(image_summary.fully_qualified_digest)' 2>/dev/null || echo "unknown")
    echo ""
    echo "Image details:"
    echo "  Name: $IMAGE"
    echo "  Digest: $IMAGE_SIZE"
else
    echo -e "${YELLOW}⚠️  Could not verify image${NC}"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Build Complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📦 Image: $IMAGE"
echo ""
echo "🔗 View in Console:"
echo "  https://console.cloud.google.com/gcr/images/${PROJECT_ID}/global/${IMAGE_NAME}?project=${PROJECT_ID}"
echo ""
echo "📚 Next Steps:"
echo ""
echo "  1. Deploy to Vertex AI:"
echo "     ./scripts/deploy-to-vertex-ai.sh"
echo ""
echo "  2. Test locally with this image:"
echo "     docker pull $IMAGE"
echo "     docker run -p 8080:8080 --env-file .env $IMAGE"
echo ""
echo "  3. View build history:"
echo "     gcloud builds list --limit=10"
echo ""
echo "💰 Build Cost: ~\$0.01-0.05 (depending on machine type and build time)"
echo ""

