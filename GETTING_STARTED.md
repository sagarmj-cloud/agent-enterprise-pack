# 🚀 Getting Started with Agent Enterprise Pack

A quick guide to get you up and running with the Agent Enterprise Pack in minutes.

---

## Prerequisites

- **Python 3.10+** 
- **UV** (recommended) or pip - [Install UV](https://docs.astral.sh/uv/getting-started/installation/)
- **Google Cloud Project** (optional, for deployment)

---

## Quick Start (2 minutes)

### 1. Install Dependencies

```bash
# Using UV (recommended - 10-100x faster)
uv sync

# Or using pip
pip install -r requirements.txt
```

### 2. Run the Quick Start Example

```bash
# Using UV
uv run python examples/quick_start.py

# Or using python directly
python examples/quick_start.py
```

**Expected Output:**
```
============================================================
Agent Enterprise Pack - Quick Start
============================================================

1. Security Components
----------------------------------------
   Input Validation:
   - Original: 'Hello <script>alert...'
   - Sanitized: 'Hello  World!'
   - Threats: ['xss']

   Prompt Injection Detection:
   - Is Injection: True
   - Confidence: 0.95
   - Attack Types: ['instruction_override']

   Rate Limiting:
   - Status: allowed
   - Remaining: 9

2. Reliability Components
----------------------------------------
   Circuit Breaker:
   - Name: external-api
   - State: closed
   - Can Execute: True

   Retry Handler:
   - Max Attempts: 3
   - Strategy: exponential

3. Memory Components
----------------------------------------
   Context Window Manager:
   - Messages: 2
   - Tokens: 15
   - Available: 127985

   Session Cache:
   - Session ID: abc123...
   - Messages: 1

4. Observability Components
----------------------------------------
   SLO Manager:
   - SLO: agent_availability_999
   - Current: 99.01%
   - Target: 99.90%
   - Error Budget: 89.00%
   - Status: compliant

   Cost Tracker:
   - Requests: 1
   - Input Tokens: 1000
   - Output Tokens: 500
   - Total Cost: $0.001875

============================================================
Quick Start Complete!
============================================================
```

---

## What Just Happened?

You just tested all 4 enterprise modules:

1. **🔒 Security** - Input validation, prompt injection detection, rate limiting
2. **🔄 Reliability** - Circuit breakers, retry logic, health checks
3. **💾 Memory** - Context window management, session caching
4. **📊 Observability** - SLO tracking, cost monitoring

---

## Next Steps

### Option 1: Run the Full Application

```bash
# Start the FastAPI server
uv run python main.py

# In another terminal, test the endpoints
curl http://localhost:8080/health
curl http://localhost:8080/
```

### Option 2: Integrate into Your Agent

```python
from core.security import InputValidator, PromptInjectionDetector
from core.reliability import CircuitBreaker, RetryHandler
from core.memory import ContextWindowManager, AgentSessionCache
from core.observability import SLOManager, CostTracker

# Use the components in your agent code
validator = InputValidator()
circuit = CircuitBreaker(name="my-api")
context = ContextWindowManager(max_tokens=128000)
slo = SLOManager()
```

### Option 3: Deploy to Google Cloud

See the deployment guides:
- **[Vertex AI Deployment](docs/VERTEX_AI_DEPLOYMENT.md)** - Deploy to Vertex AI Agent Engine
- **[Cloud Build Setup](docs/CLOUD_BUILD_SETUP.md)** - Set up CI/CD with Cloud Build

---

## Project Structure

```
agent-enterprise-pack/
├── core/                    # Enterprise modules
│   ├── security/           # Input validation, auth, rate limiting
│   ├── reliability/        # Circuit breakers, retry, health checks
│   ├── memory/             # Context management, caching
│   └── observability/      # SLOs, cost tracking, alerting
├── examples/               # Example code
│   ├── quick_start.py     # Quick start demo (run this first!)
│   └── test_agent.py      # Test script for deployed agent
├── main.py                # FastAPI application
├── tests/                 # Unit tests
└── docs/                  # Documentation
```

---

## Common Commands

```bash
# Install dependencies
uv sync

# Run quick start
uv run python examples/quick_start.py

# Run main application
uv run python main.py

# Run tests
uv run pytest

# Format code
uv run black .

# Type check
uv run mypy .
```

---

## Need Help?

- **📖 Documentation**: Check the `docs/` directory
- **🐛 Issues**: Open an issue on GitHub
- **💬 Questions**: See [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

---

## What's Next?

1. ✅ **You are here** - Quick start complete!
2. 📚 **Learn More** - Read the [Development Guide](docs/GETTING_STARTED.md)
3. 🧪 **Run Tests** - `uv run pytest`
4. 🚀 **Deploy** - Follow the [Deployment Guide](docs/VERTEX_AI_DEPLOYMENT.md)

---

**Ready to build production-grade AI agents!** 🎉

