#!/bin/bash
# Test on GCP - Assumes APIs are already enabled
# ===============================================
# Use this after manually enabling APIs through Console

set -e

echo "🚀 Agent Enterprise Pack - Test on GCP"
echo "======================================"
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

echo ""
echo -e "${BLUE}Using project: $PROJECT_ID${NC}"
gcloud config set project $PROJECT_ID
echo ""

# Check if APIs are enabled
echo "1️⃣ Checking required APIs..."
echo ""

REQUIRED_APIS=(
    "aiplatform.googleapis.com:Vertex AI API"
    "containerregistry.googleapis.com:Container Registry API"
    "secretmanager.googleapis.com:Secret Manager API"
    "cloudbuild.googleapis.com:Cloud Build API"
)

MISSING_APIS=()

for api_info in "${REQUIRED_APIS[@]}"; do
    IFS=':' read -r api name <<< "$api_info"
    if gcloud services list --enabled --filter="name:$api" --format="value(name)" 2>/dev/null | grep -q "$api"; then
        echo -e "${GREEN}✅ $name enabled${NC}"
    else
        echo -e "${RED}❌ $name NOT enabled${NC}"
        MISSING_APIS+=("$api:$name")
    fi
done

if [ ${#MISSING_APIS[@]} -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Some required APIs are not enabled.${NC}"
    echo ""
    echo "Please enable them manually through the Console:"
    echo ""
    for api_info in "${MISSING_APIS[@]}"; do
        IFS=':' read -r api name <<< "$api_info"
        echo "  • $name"
        echo "    https://console.cloud.google.com/apis/library/$api?project=$PROJECT_ID"
        echo ""
    done
    read -p "Press Enter after enabling the APIs, or Ctrl+C to exit..."
    echo ""
fi

echo -e "${GREEN}✅ All required APIs are enabled${NC}"
echo ""

# Authenticate
echo "2️⃣ Setting up authentication..."
echo ""

if gcloud auth application-default print-access-token &>/dev/null; then
    echo -e "${GREEN}✅ Already authenticated${NC}"
else
    echo "Setting up application default credentials..."
    gcloud auth application-default login
fi

echo ""

# Create or verify secrets
echo "3️⃣ Setting up secrets..."
echo ""

# JWT Secret
if gcloud secrets describe jwt-secret --project=$PROJECT_ID &>/dev/null; then
    echo -e "${GREEN}✅ jwt-secret already exists${NC}"
else
    echo "Creating jwt-secret..."
    JWT_SECRET=$(openssl rand -hex 32)
    echo -n "$JWT_SECRET" | gcloud secrets create jwt-secret \
        --project=$PROJECT_ID \
        --data-file=- 2>/dev/null && \
        echo -e "${GREEN}✅ jwt-secret created${NC}" || \
        echo -e "${YELLOW}⚠️  Could not create jwt-secret (may need permissions)${NC}"
fi

# Redis URL
if gcloud secrets describe redis-url --project=$PROJECT_ID &>/dev/null; then
    echo -e "${GREEN}✅ redis-url already exists${NC}"
else
    echo "Creating redis-url..."
    echo -n "redis://localhost:6379" | gcloud secrets create redis-url \
        --project=$PROJECT_ID \
        --data-file=- 2>/dev/null && \
        echo -e "${GREEN}✅ redis-url created${NC}" || \
        echo -e "${YELLOW}⚠️  Could not create redis-url (may need permissions)${NC}"
fi

echo ""

# Choose deployment method
echo "4️⃣ Choose deployment method:"
echo ""
echo "  1. Test locally first (recommended)"
echo "  2. Deploy to Vertex AI directly"
echo "  3. Exit"
echo ""
read -p "Enter choice (1-3): " CHOICE

case $CHOICE in
    1)
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo -e "${BLUE}Testing Locally with GCP Integration${NC}"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        # Start Redis
        echo "Starting Redis..."
        if docker ps | grep -q redis-test; then
            echo -e "${YELLOW}⚠️  Redis already running${NC}"
        else
            docker run -d --name redis-test -p 6379:6379 redis:7-alpine
            sleep 2
            echo -e "${GREEN}✅ Redis started${NC}"
        fi
        echo ""
        
        # Install dependencies
        echo "Installing dependencies..."
        if command -v uv &> /dev/null; then
            uv sync --quiet
        else
            pip install -r requirements.txt --quiet
        fi
        echo -e "${GREEN}✅ Dependencies installed${NC}"
        echo ""
        
        # Create .env
        echo "Creating configuration..."
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
        echo -e "${GREEN}✅ Configuration created${NC}"
        echo ""
        
        # Run tests
        echo "Running tests..."
        if command -v uv &> /dev/null; then
            uv run pytest tests/ -v --tb=short || echo -e "${YELLOW}⚠️  Some tests failed${NC}"
        else
            python -m pytest tests/ -v --tb=short || echo -e "${YELLOW}⚠️  Some tests failed${NC}"
        fi
        echo ""
        
        # Start server
        echo "Starting server..."
        if command -v uv &> /dev/null; then
            uv run python main.py > server.log 2>&1 &
        else
            python main.py > server.log 2>&1 &
        fi
        SERVER_PID=$!
        echo $SERVER_PID > .server.pid
        echo "Server PID: $SERVER_PID"
        sleep 5
        echo ""
        
        # Test endpoints
        echo "Testing endpoints..."
        if curl -f http://localhost:8080/health --silent 2>/dev/null; then
            echo -e "${GREEN}✅ Server is running!${NC}"
            echo ""
            echo "Test commands:"
            echo "  curl http://localhost:8080/health"
            echo "  curl http://localhost:8080/metrics"
            echo "  uv run python examples/test_agent.py"
            echo ""
            echo "View logs: tail -f server.log"
            echo "Stop server: kill $SERVER_PID"
        else
            echo -e "${RED}❌ Server failed to start. Check logs: tail -f server.log${NC}"
        fi
        ;;
        
    2)
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo -e "${BLUE}Deploying to Vertex AI${NC}"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        if [ -f "scripts/deploy-to-vertex-ai.sh" ]; then
            chmod +x scripts/deploy-to-vertex-ai.sh
            ./scripts/deploy-to-vertex-ai.sh
        else
            echo -e "${RED}❌ Deployment script not found${NC}"
            echo "Please run from the project root directory"
            exit 1
        fi
        ;;
        
    3)
        echo "Exiting..."
        exit 0
        ;;
        
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📚 Documentation:"
echo "  • Manual GCP Setup: docs/GCP_SETUP_MANUAL.md"
echo "  • Testing Guide: docs/TESTING_GUIDE.md"
echo "  • Vertex AI Deployment: docs/VERTEX_AI_DEPLOYMENT.md"
echo ""

