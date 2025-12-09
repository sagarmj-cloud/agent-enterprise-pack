.PHONY: help install dev-install test lint format clean docker-build docker-run

help:
	@echo "Agent Enterprise Pack - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install       Install dependencies with uv"
	@echo "  make dev-install   Install with dev dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make test          Run tests with pytest"
	@echo "  make test-cov      Run tests with coverage report"
	@echo "  make lint          Run linting checks"
	@echo "  make format        Format code with ruff"
	@echo "  make type-check    Run mypy type checking"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build  Build Docker image"
	@echo "  make docker-run    Run Docker container"
	@echo "  make docker-test   Test Docker container"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean         Remove build artifacts"

install:
	uv sync

dev-install:
	uv sync --all-extras

test:
	uv run pytest -v

test-cov:
	uv run pytest -v --cov --cov-report=html --cov-report=term

test-watch:
	uv run pytest-watch

lint:
	uv run ruff check .

lint-fix:
	uv run ruff check --fix .

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

type-check:
	uv run mypy core/ --ignore-missing-imports

security-check:
	uv pip install safety bandit
	uv run safety check
	uv run bandit -r core/

docker-build:
	docker build -t agent-enterprise-pack:latest .

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down

docker-test:
	docker run -d --name test-agent -p 8080:8080 \
		-e JWT_SECRET=test-secret \
		-e CACHE_BACKEND=memory \
		agent-enterprise-pack:latest
	sleep 10
	curl -f http://localhost:8080/health
	docker stop test-agent
	docker rm test-agent

run-dev:
	uv run python main.py

run-example:
	uv run python examples/quick_start.py

clean:
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .mypy_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

ci: lint format-check type-check test-cov
	@echo "✅ All CI checks passed!"

