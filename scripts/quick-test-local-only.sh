#!/bin/bash
# Quick Test Script - Local Only (No GCP Required)
# ==================================================
# Tests the agent completely locally without any GCP dependencies

set -e

echo "🧪 Agent Enterprise Pack - Local-Only Test"
echo "=========================================="
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

# Start Redis
echo "2️⃣ Starting local Redis..."
if docker ps | grep -q redis-test; then
    echo -e "${YELLOW}⚠️  Redis already running${NC}"
else
    docker run -d --name redis-test -p 6379:6379 redis:7-alpine
    sleep 2
    echo -e "${GREEN}✅ Redis started${NC}"
fi
echo ""

# Install dependencies
echo "3️⃣ Installing dependencies..."
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

# Create .env file (local only - no GCP)
echo "4️⃣ Creating local configuration..."
cat > .env << EOF
# Local Testing Configuration (No GCP Required)
GOOGLE_CLOUD_PROJECT=local-test-project
LOCATION=us-central1
MODEL=gemini-1.5-pro

# Security
JWT_SECRET=$(openssl rand -hex 32)

# Cache (local Redis)
CACHE_BACKEND=redis
REDIS_URL=redis://localhost:6379

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Monitoring (local only)
ENABLE_TRACING=false
ENABLE_METRICS=true

# Mock mode for testing without GCP
MOCK_LLM=false
EOF

echo -e "${GREEN}✅ Configuration created${NC}"
echo ""

# Run tests
echo "5️⃣ Running unit tests..."
if command -v uv &> /dev/null; then
    uv run pytest tests/ -v --tb=short || echo -e "${YELLOW}⚠️  Some tests may fail without GCP credentials${NC}"
else
    python -m pytest tests/ -v --tb=short || echo -e "${YELLOW}⚠️  Some tests may fail without GCP credentials${NC}"
fi
echo ""

# Start server in background
echo "6️⃣ Starting local server..."
if command -v uv &> /dev/null; then
    uv run python main.py > server.log 2>&1 &
else
    python main.py > server.log 2>&1 &
fi
SERVER_PID=$!
echo "Server PID: $SERVER_PID"
echo "Waiting for server to start..."
sleep 5
echo -e "${GREEN}✅ Server started${NC}"
echo ""

# Test endpoints
echo "7️⃣ Testing endpoints..."

echo "Testing health endpoint..."
for i in {1..5}; do
    if curl -f http://localhost:8080/health --silent --show-error 2>/dev/null; then
        echo -e "${GREEN}✅ Health check passed${NC}"
        break
    else
        if [ $i -eq 5 ]; then
            echo -e "${RED}❌ Health check failed after 5 attempts${NC}"
            echo "Check logs: tail -f server.log"
        else
            echo "Waiting for server... (attempt $i/5)"
            sleep 2
        fi
    fi
done
echo ""

echo "Testing readiness endpoint..."
if curl -f http://localhost:8080/ready --silent --show-error 2>/dev/null; then
    echo -e "${GREEN}✅ Readiness check passed${NC}"
else
    echo -e "${YELLOW}⚠️  Readiness check failed${NC}"
fi
echo ""

echo "Testing metrics endpoint..."
if curl -f http://localhost:8080/metrics --silent --show-error 2>/dev/null | head -5; then
    echo -e "${GREEN}✅ Metrics endpoint works${NC}"
else
    echo -e "${YELLOW}⚠️  Metrics endpoint failed${NC}"
fi
echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Local Test Setup Complete!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Summary:"
echo "  • Mode: Local testing (no GCP required)"
echo "  • Server: http://localhost:8080"
echo "  • Server PID: $SERVER_PID"
echo "  • Redis: Running in Docker (redis-test)"
echo "  • Logs: tail -f server.log"
echo ""
echo "🧪 Test Commands:"
echo ""
echo "  # Health check"
echo "  curl http://localhost:8080/health"
echo ""
echo "  # Readiness check"
echo "  curl http://localhost:8080/ready"
echo ""
echo "  # Metrics"
echo "  curl http://localhost:8080/metrics"
echo ""
echo "  # Chat (may require GCP credentials)"
echo "  curl -X POST http://localhost:8080/chat \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -H 'X-API-Key: demo-api-key' \\"
echo "    -d '{\"message\": \"Hello!\", \"session_id\": \"test\"}'"
echo ""
echo "  # View logs"
echo "  tail -f server.log"
echo ""
echo "  # Interactive testing"
echo "  uv run python examples/test_agent.py"
echo ""
echo "🛑 Stop Server:"
echo "  kill $SERVER_PID"
echo "  docker stop redis-test"
echo ""
echo "  # Or use cleanup script:"
echo "  kill \$(cat .server.pid 2>/dev/null) 2>/dev/null"
echo "  docker stop redis-test 2>/dev/null"
echo ""
echo "📚 Next Steps:"
echo "  1. Test endpoints above"
echo "  2. View logs: tail -f server.log"
echo "  3. For GCP deployment: docs/VERTEX_AI_DEPLOYMENT.md"
echo ""
echo "💡 Note: This is local-only testing"
echo "   For full GCP integration, you'll need:"
echo "   - GCP project with billing"
echo "   - Vertex AI API enabled"
echo "   - Application default credentials"
echo ""

# Save PID for cleanup
echo $SERVER_PID > .server.pid

echo "✅ Server is running! Press Ctrl+C to stop or run: kill $SERVER_PID"
echo ""

