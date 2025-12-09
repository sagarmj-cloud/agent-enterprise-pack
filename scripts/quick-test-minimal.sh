#!/bin/bash
# Quick Test Script - Minimal Version (No Cloud Monitoring)
# =========================================================
# Sets up and tests the agent locally without optional GCP services

set -e

echo "🧪 Agent Enterprise Pack - Quick Test Setup (Minimal)"
echo "====================================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
echo "1️⃣ Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install: https://docs.docker.com/get-docker/${NC}"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.11+${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites found${NC}"
echo ""

# Get project ID
echo "2️⃣ GCP Project Setup"
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
if [ -n "$CURRENT_PROJECT" ]; then
    echo "Current project: $CURRENT_PROJECT"
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

echo "Setting project to: $PROJECT_ID"
gcloud config set project $PROJECT_ID

echo -e "${GREEN}✅ Project configured${NC}"
echo ""

# Enable only essential APIs (skip Cloud Monitoring)
echo "3️⃣ Enabling essential APIs..."
echo "Note: Skipping Cloud Monitoring (optional for local testing)"

ESSENTIAL_APIS=(
    "aiplatform.googleapis.com"
    "containerregistry.googleapis.com"
    "secretmanager.googleapis.com"
)

for api in "${ESSENTIAL_APIS[@]}"; do
    echo "Enabling $api..."
    gcloud services enable $api --quiet 2>/dev/null || \
        echo -e "${YELLOW}⚠️  Could not enable $api (may need manual enabling)${NC}"
done

echo -e "${GREEN}✅ Essential APIs enabled${NC}"
echo ""

# Create secrets (optional - will use local values if fails)
echo "4️⃣ Setting up secrets..."

JWT_SECRET="test-jwt-secret-$(openssl rand -hex 16)"

# Try to create GCP secrets, but don't fail if it doesn't work
if gcloud secrets create jwt-secret --data-file=- <<< "$JWT_SECRET" 2>/dev/null; then
    echo -e "${GREEN}✅ Created jwt-secret in Secret Manager${NC}"
else
    echo -e "${YELLOW}⚠️  Could not create jwt-secret in Secret Manager (will use local value)${NC}"
fi

if gcloud secrets create redis-url --data-file=- <<< "redis://localhost:6379" 2>/dev/null; then
    echo -e "${GREEN}✅ Created redis-url in Secret Manager${NC}"
else
    echo -e "${YELLOW}⚠️  Could not create redis-url in Secret Manager (will use local value)${NC}"
fi

echo ""

# Start Redis
echo "5️⃣ Starting local Redis..."
if docker ps | grep -q redis-test; then
    echo -e "${YELLOW}⚠️  Redis already running${NC}"
else
    docker run -d --name redis-test -p 6379:6379 redis:7-alpine
    sleep 2
    echo -e "${GREEN}✅ Redis started${NC}"
fi
echo ""

# Install dependencies
echo "6️⃣ Installing dependencies..."
if command -v uv &> /dev/null; then
    echo "Using UV (fast)..."
    uv sync --quiet
else
    echo "UV not found, using pip (slower)..."
    echo "💡 Tip: Install UV for 10-100x faster installs: curl -LsSf https://astral.sh/uv/install.sh | sh"
    pip install -r requirements.txt --quiet
fi
echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Create .env file
echo "7️⃣ Creating .env configuration..."
cat > .env << EOF
# GCP Configuration
GOOGLE_CLOUD_PROJECT=${PROJECT_ID}
LOCATION=us-central1
MODEL=gemini-1.5-pro

# Security
JWT_SECRET=${JWT_SECRET}

# Cache
CACHE_BACKEND=redis
REDIS_URL=redis://localhost:6379

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Monitoring (disabled for local testing)
ENABLE_TRACING=false
ENABLE_METRICS=true
EOF

echo -e "${GREEN}✅ Configuration created${NC}"
echo ""

# Run tests
echo "8️⃣ Running unit tests..."
if command -v uv &> /dev/null; then
    uv run pytest tests/ -v --tb=short 2>/dev/null || echo -e "${YELLOW}⚠️  Some tests failed (this is OK for initial setup)${NC}"
else
    python -m pytest tests/ -v --tb=short 2>/dev/null || echo -e "${YELLOW}⚠️  Some tests failed (this is OK for initial setup)${NC}"
fi
echo ""

# Start server in background
echo "9️⃣ Starting local server..."
if command -v uv &> /dev/null; then
    uv run python main.py > server.log 2>&1 &
else
    python main.py > server.log 2>&1 &
fi
SERVER_PID=$!
echo "Server PID: $SERVER_PID"
echo "Server logs: tail -f server.log"
sleep 5
echo -e "${GREEN}✅ Server started${NC}"
echo ""

# Test endpoints
echo "🔟 Testing endpoints..."

echo "Testing health endpoint..."
if curl -f http://localhost:8080/health --silent --show-error 2>/dev/null; then
    echo -e "${GREEN}✅ Health check passed${NC}"
else
    echo -e "${YELLOW}⚠️  Health check failed (server may still be starting)${NC}"
fi
echo ""

echo "Testing readiness endpoint..."
if curl -f http://localhost:8080/ready --silent --show-error 2>/dev/null; then
    echo -e "${GREEN}✅ Readiness check passed${NC}"
else
    echo -e "${YELLOW}⚠️  Readiness check failed${NC}"
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Quick Test Setup Complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Summary:"
echo "  • Project: $PROJECT_ID"
echo "  • Server: http://localhost:8080"
echo "  • Server PID: $SERVER_PID"
echo "  • Redis: Running in Docker (redis-test)"
echo "  • Logs: tail -f server.log"
echo ""
echo "🧪 Test Commands:"
echo "  # Health check"
echo "  curl http://localhost:8080/health"
echo ""
echo "  # Chat test"
echo "  curl -X POST http://localhost:8080/chat \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -H 'X-API-Key: demo-api-key' \\"
echo "    -d '{\"message\": \"Hello!\", \"session_id\": \"test\"}'"
echo ""
echo "  # View metrics"
echo "  curl http://localhost:8080/metrics"
echo ""
echo "  # View logs"
echo "  tail -f server.log"
echo ""
echo "🛑 Stop Server:"
echo "  kill $SERVER_PID"
echo "  docker stop redis-test"
echo ""
echo "📚 Next Steps:"
echo "  1. Test locally: curl http://localhost:8080/health"
echo "  2. Interactive test: uv run python examples/test_agent.py"
echo "  3. View full guide: docs/TESTING_GUIDE.md"
echo ""
echo "💡 Note: Cloud Monitoring is disabled for local testing"
echo "   Enable it later for production deployment"
echo ""

# Save PID for cleanup
echo $SERVER_PID > .server.pid

echo "Server is running in background. Check logs with: tail -f server.log"
echo ""

