# Contributing to Agent Enterprise Pack

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites
- Python 3.11 or higher
- [UV](https://github.com/astral-sh/uv) (recommended) or pip
- Docker (for integration tests)
- Redis (for integration tests)

### Setup with UV (Recommended)

```bash
# Install UV if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone <repo-url>
cd agent-enterprise-pack

# Install dependencies
uv sync --all-extras

# Run tests
uv run pytest
```

### Setup with pip

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev,test]"

# Run tests
pytest
```

## Development Workflow

### 1. Create a Branch
```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Changes
- Write clean, documented code
- Follow existing code style
- Add tests for new features
- Update documentation as needed

### 3. Run Tests
```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
uv run pytest tests/test_security.py -v
```

### 4. Lint and Format
```bash
# Format code
make format

# Check linting
make lint

# Fix linting issues
make lint-fix

# Type checking
make type-check
```

### 5. Run Full CI Locally
```bash
make ci
```

### 6. Commit Changes
Follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
git commit -m "feat: add new rate limiting algorithm"
git commit -m "fix: resolve circuit breaker state issue"
git commit -m "docs: update installation instructions"
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `build`: Build system changes
- `ci`: CI/CD changes
- `chore`: Other changes

### 7. Push and Create PR
```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Code Style

- Follow PEP 8
- Use type hints where appropriate
- Maximum line length: 100 characters
- Use docstrings for all public functions/classes
- Keep functions focused and small

## Testing Guidelines

### Unit Tests
- Test individual components in isolation
- Mock external dependencies
- Use descriptive test names
- Aim for >80% code coverage

### Integration Tests
- Test component interactions
- Use real Redis for cache tests
- Mark slow tests with `@pytest.mark.slow`

### Example Test Structure
```python
@pytest.mark.asyncio
class TestMyFeature:
    """Tests for MyFeature."""
    
    async def test_success_case(self):
        """Test successful operation."""
        # Arrange
        feature = MyFeature()
        
        # Act
        result = await feature.do_something()
        
        # Assert
        assert result == expected
```

## Documentation

- Update README.md for user-facing changes
- Add docstrings to all public APIs
- Include code examples in docstrings
- Update CHANGELOG.md

## Pull Request Process

1. Ensure all tests pass
2. Update documentation
3. Add entry to CHANGELOG.md
4. Request review from maintainers
5. Address review feedback
6. Squash commits if requested

## Release Process

Releases are automated via GitHub Actions:

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create and push tag:
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0"
   git push origin v1.0.0
   ```
4. GitHub Actions will:
   - Run CI tests
   - Build Docker image
   - Create GitHub release
   - Publish to PyPI (if configured)

## Questions?

- Open an issue for bugs or feature requests
- Start a discussion for questions
- Check existing issues and PRs first

Thank you for contributing! 🎉

