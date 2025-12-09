#!/bin/bash
# Deploy Agent to Vertex AI Agent Engine
# =======================================

set -e

echo "🤖 Deploying Agent Enterprise Pack to Vertex AI Agent Engine"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed"
    exit 1
fi

# Get project ID
read -p "Enter your GCP Project ID: " PROJECT_ID
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: Project ID is required"
    exit 1
fi

gcloud config set project $PROJECT_ID

# Get configuration
read -p "Enter deployment region [us-central1]: " REGION
REGION=${REGION:-us-central1}

read -p "Enter agent name [agent-enterprise-pack]: " AGENT_NAME
AGENT_NAME=${AGENT_NAME:-agent-enterprise-pack}

read -p "Enter Docker image tag [latest]: " TAG
TAG=${TAG:-latest}

IMAGE="gcr.io/${PROJECT_ID}/${AGENT_NAME}:${TAG}"

echo ""
echo "📋 Configuration:"
echo "  Project: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Agent: $AGENT_NAME"
echo "  Image: $IMAGE"
echo ""

# Step 1: Enable APIs
echo "1️⃣ Enabling Vertex AI APIs..."
gcloud services enable \
    aiplatform.googleapis.com \
    containerregistry.googleapis.com \
    secretmanager.googleapis.com \
    --quiet

echo "✅ APIs enabled"

# Step 2: Build and push Docker image (if needed)
echo ""
read -p "Build and push Docker image? (y/N): " BUILD_IMAGE
if [ "$BUILD_IMAGE" = "y" ]; then
    echo ""
    echo "Choose build method:"
    echo "  1. Cloud Build (recommended - builds in GCP)"
    echo "  2. Local Docker (builds on your machine)"
    echo ""
    read -p "Enter choice (1-2) [1]: " BUILD_METHOD
    BUILD_METHOD=${BUILD_METHOD:-1}

    if [ "$BUILD_METHOD" = "1" ]; then
        echo "2️⃣ Building Docker image with Cloud Build..."

        # Enable Cloud Build API
        echo "Enabling Cloud Build API..."
        gcloud services enable cloudbuild.googleapis.com --quiet 2>/dev/null || \
            echo "⚠️  Could not enable Cloud Build API (may need manual enabling)"

        # Create Cloud Build bucket if it doesn't exist
        echo "Setting up Cloud Build storage..."
        BUCKET_NAME="${PROJECT_ID}_cloudbuild"
        if ! gsutil ls -b gs://${BUCKET_NAME} &>/dev/null; then
            echo "Creating Cloud Build bucket..."
            gsutil mb -p ${PROJECT_ID} gs://${BUCKET_NAME} 2>/dev/null || \
                echo "⚠️  Could not create bucket (may already exist or need manual creation)"
        fi

        # Create temporary cloudbuild.yaml for custom Dockerfile
        cat > /tmp/cloudbuild-temp.yaml << EOF
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-f', 'Dockerfile.uv', '-t', '$IMAGE', '.']
images: ['$IMAGE']
options:
  machineType: 'N1_HIGHCPU_8'
  diskSizeGb: 50
timeout: 600s
EOF

        # Build with Cloud Build
        echo "Building image in GCP (this may take 2-3 minutes)..."
        gcloud builds submit \
            --config=/tmp/cloudbuild-temp.yaml \
            --timeout=10m \
            . || {
                echo "❌ Build failed"
                rm -f /tmp/cloudbuild-temp.yaml
                exit 1
            }

        # Clean up
        rm -f /tmp/cloudbuild-temp.yaml

        echo "✅ Image built and pushed to GCR"
    else
        echo "2️⃣ Building Docker image locally..."

        # Check if Docker is running
        if ! docker info &> /dev/null; then
            echo "❌ Error: Docker is not running"
            echo "Please start Docker and try again"
            exit 1
        fi

        docker build -f Dockerfile.uv -t $IMAGE .

        echo "📤 Pushing to GCR..."
        gcloud auth configure-docker --quiet
        docker push $IMAGE
        echo "✅ Image pushed"
    fi
else
    echo "⏭️  Skipping image build"
fi

# Step 3: Deploy to Vertex AI Agent Engine using ADK
echo ""
echo "3️⃣ Deploying to Vertex AI Agent Engine..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚠️  IMPORTANT: Vertex AI Agent Engine Deployment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Vertex AI Agent Engine requires deployment using the ADK CLI or Python SDK."
echo "The 'gcloud ai agents' command does not exist."
echo ""
echo "📚 Deployment Options:"
echo ""
echo "Option 1: ADK CLI (Recommended)"
echo "  adk deploy agent_engine \\"
echo "    --project=$PROJECT_ID \\"
echo "    --region=$REGION \\"
echo "    --staging_bucket=gs://${PROJECT_ID}_cloudbuild \\"
echo "    --display_name=\"$AGENT_NAME\" \\"
echo "    ."
echo ""
echo "Option 2: Python SDK"
echo "  from vertexai import agent_engines"
echo "  import vertexai"
echo ""
echo "  vertexai.init("
echo "      project='$PROJECT_ID',"
echo "      location='$REGION',"
echo "      staging_bucket='gs://${PROJECT_ID}_cloudbuild'"
echo "  )"
echo ""
echo "  app = agent_engines.AdkApp(agent=root_agent, enable_tracing=True)"
echo "  remote_app = agent_engines.create("
echo "      agent_engine=app,"
echo "      requirements=['google-adk']"
echo "  )"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ Docker image built and pushed: $IMAGE"
echo ""
echo "📚 Next Steps:"
echo ""
echo "1. Install Google ADK (if not already installed):"
echo "   pip install google-adk"
echo ""
echo "2. Verify installation:"
echo "   adk --version"
echo ""
echo "3. Deploy using ADK CLI:"
echo "   adk deploy agent_engine --project=$PROJECT_ID --region=$REGION --staging_bucket=gs://${PROJECT_ID}_cloudbuild --display_name=\"$AGENT_NAME\" ."
echo ""
echo "4. Or see complete deployment guide:"
echo "   docs/ADK_DEPLOYMENT_GUIDE.md"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Image Build Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📦 Docker Image: $IMAGE"
echo ""
echo "🔗 View in Console:"
echo "  https://console.cloud.google.com/gcr/images/${PROJECT_ID}?project=${PROJECT_ID}"
echo ""
echo "📚 Complete Deployment Guide:"
echo "  See docs/VERTEX_AI_DEPLOYMENT.md for step-by-step instructions"
echo ""

