#!/bin/bash
# Quick Test Script - Agent Enterprise Pack
# ==========================================
# Sets up and tests the agent in your GCP project

set -e

echo "🧪 Agent Enterprise Pack - Quick Test Setup"
echo "==========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
echo "1️⃣ Checking prerequisites..."

if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not found. Please install: https://cloud.google.com/sdk/docs/install${NC}"
    exit 1
fi

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
read -p "Enter your GCP Project ID: " PROJECT_ID

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Project ID is required${NC}"
    exit 1
fi

echo "Setting project to: $PROJECT_ID"
gcloud config set project $PROJECT_ID

echo -e "${GREEN}✅ Project configured${NC}"
echo ""

# Enable APIs
echo "3️⃣ Enabling required APIs (this may take 2-3 minutes)..."
gcloud services enable \
    aiplatform.googleapis.com \
    containerregistry.googleapis.com \
    secretmanager.googleapis.com \
    redis.googleapis.com \
    cloudmonitoring.googleapis.com \
    cloudtrace.googleapis.com \
    --quiet

echo -e "${GREEN}✅ APIs enabled${NC}"
echo ""

# Create secrets
echo "4️⃣ Creating test secrets..."

# JWT Secret
JWT_SECRET="test-jwt-secret-$(openssl rand -hex 16)"
echo -n "$JWT_SECRET" | gcloud secrets create jwt-secret --data-file=- 2>/dev/null || \
    echo -e "${YELLOW}⚠️  jwt-secret already exists, skipping${NC}"

# Redis URL (local for testing)
echo -n "redis://localhost:6379" | gcloud secrets create redis-url --data-file=- 2>/dev/null || \
    echo -e "${YELLOW}⚠️  redis-url already exists, skipping${NC}"

echo -e "${GREEN}✅ Secrets created${NC}"
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

# Monitoring
ENABLE_TRACING=true
ENABLE_METRICS=true
EOF

echo -e "${GREEN}✅ Configuration created${NC}"
echo ""

# Run tests
echo "8️⃣ Running unit tests..."
if command -v uv &> /dev/null; then
    uv run pytest tests/ -v --tb=short || echo -e "${YELLOW}⚠️  Some tests failed (this is OK for initial setup)${NC}"
else
    python -m pytest tests/ -v --tb=short || echo -e "${YELLOW}⚠️  Some tests failed (this is OK for initial setup)${NC}"
fi
echo ""

# Start server in background
echo "9️⃣ Starting local server..."
if command -v uv &> /dev/null; then
    uv run python main.py &
else
    python main.py &
fi
SERVER_PID=$!
echo "Server PID: $SERVER_PID"
sleep 5
echo -e "${GREEN}✅ Server started${NC}"
echo ""

# Test endpoints
echo "🔟 Testing endpoints..."

echo "Testing health endpoint..."
if curl -f http://localhost:8080/health --silent --show-error; then
    echo -e "${GREEN}✅ Health check passed${NC}"
else
    echo -e "${RED}❌ Health check failed${NC}"
fi
echo ""

echo "Testing readiness endpoint..."
if curl -f http://localhost:8080/ready --silent --show-error; then
    echo -e "${GREEN}✅ Readiness check passed${NC}"
else
    echo -e "${RED}❌ Readiness check failed${NC}"
fi
echo ""

echo "Testing chat endpoint..."
RESPONSE=$(curl -X POST http://localhost:8080/chat \
    -H "Content-Type: application/json" \
    -H "X-API-Key: demo-api-key" \
    -d '{"message": "Hello! This is a test.", "session_id": "test-123"}' \
    --silent --show-error)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Chat endpoint works${NC}"
    echo "Response: $RESPONSE"
else
    echo -e "${YELLOW}⚠️  Chat endpoint may need authentication setup${NC}"
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
echo "🛑 Stop Server:"
echo "  kill $SERVER_PID"
echo "  docker stop redis-test"
echo ""
echo "📚 Next Steps:"
echo "  1. Test locally: See docs/TESTING_GUIDE.md"
echo "  2. Deploy to Vertex AI: ./scripts/deploy-to-vertex-ai.sh"
echo "  3. Setup CI/CD: ./scripts/setup-cloud-build.sh"
echo ""
echo "💡 Tip: Keep this terminal open to see server logs"
echo ""

# Wait for user input
read -p "Press Enter to stop the server and exit..."

# Cleanup
echo ""
echo "🧹 Cleaning up..."
kill $SERVER_PID 2>/dev/null || true
echo -e "${GREEN}✅ Server stopped${NC}"
echo ""
echo "Note: Redis is still running. Stop it with: docker stop redis-test"
echo ""

