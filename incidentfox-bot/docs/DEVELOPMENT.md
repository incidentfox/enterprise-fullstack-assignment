# Development Guide

This guide covers local development setup, testing, and contribution guidelines for IncidentFox.

## Table of Contents

- [Quick Start](#quick-start)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Running Locally](#running-locally)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Debugging](#debugging)
- [Common Tasks](#common-tasks)

---

## Quick Start

```bash
# Clone repository
cd incidentfox-bot

# Setup development environment
make setup-dev

# Install dependencies
make install

# Start development server (hot reload enabled)
make dev

# In another terminal, start ngrok for webhook testing
make ngrok
```

---

## Development Setup

### Prerequisites

- Python 3.11+
- pip
- Docker & Docker Compose (optional, for full stack testing)
- ngrok (for local webhook testing)
- GitHub App created ([Setup Guide](./GITHUB_APP_SETUP.md))

### 1. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required variables for local development:
```bash
GITHUB_APP_ID=your_app_id
GITHUB_APP_PRIVATE_KEY_PATH=./private-key.pem
GITHUB_WEBHOOK_SECRET=your_webhook_secret
COOLIFY_API_URL=https://your-coolify-instance.com
COOLIFY_API_TOKEN=your_api_token
ANTHROPIC_API_KEY=your_anthropic_key  # or OPENAI_API_KEY
```

### 4. Add GitHub App Private Key

```bash
# Download from GitHub App settings
cp ~/Downloads/your-app.private-key.pem ./private-key.pem
chmod 600 private-key.pem
```

### 5. Initialize Database

```bash
# Database is auto-created on first run
# For development, SQLite is fine:
export DATABASE_URL=sqlite:///./incidentfox.db
```

---

## Project Structure

```
incidentfox-bot/
├── src/                      # Source code
│   ├── main.py              # FastAPI app & webhook handlers
│   ├── config.py            # Configuration management
│   ├── database.py          # Database connection & session
│   ├── models.py            # SQLAlchemy models
│   ├── github_client.py     # GitHub API integration
│   ├── coolify_client.py    # Coolify API integration
│   ├── analyzer.py          # Failure analysis engine
│   ├── patch_generator.py   # Safe patch generation
│   ├── comment_formatter.py # PR comment formatting
│   └── logging_config.py    # Structured logging
├── tests/                    # Test suite
│   ├── test_analyzer.py
│   ├── test_github_client.py
│   └── test_patch_generator.py
├── docs/                     # Documentation
├── deployment/              # Deployment configs
├── .env.example             # Environment template
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container image
├── docker-compose.yml       # Local stack
└── Makefile                 # Development commands
```

### Key Files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app, webhook handlers, event routing |
| `github_client.py` | GitHub App auth, API calls, comment posting |
| `coolify_client.py` | Coolify API integration, log fetching |
| `analyzer.py` | Pattern matching + LLM analysis |
| `patch_generator.py` | Safe file patching with whitelist |
| `models.py` | Database schema (PRs, deployments, analyses) |

---

## Running Locally

### Option 1: Direct Python (Recommended for Development)

```bash
# Start server with hot reload
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Or use make command
make dev
```

Server runs at: `http://localhost:8000`

### Option 2: Docker Compose (Full Stack)

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f incidentfox

# Stop
docker-compose down
```

### Setup Webhook Forwarding

For local testing, use ngrok to expose localhost:

```bash
# Start ngrok
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
# Update GitHub App webhook URL to: https://abc123.ngrok.io/webhooks/github
# Update Coolify webhook URL to: https://abc123.ngrok.io/webhooks/coolify
```

**Verify Webhooks**:

```bash
# Test GitHub webhook endpoint
curl -X POST http://localhost:8000/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: ping" \
  -d '{"zen": "Design for failure."}'

# Check health
curl http://localhost:8000/health
```

---

## Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Run with Coverage

```bash
pytest tests/ --cov=src --cov-report=html --cov-report=term

# Open coverage report
open htmlcov/index.html
```

### Run Specific Test

```bash
pytest tests/test_analyzer.py -v
pytest tests/test_analyzer.py::test_detect_env_var_missing -v
```

### Test Structure

```python
# tests/test_analyzer.py
import pytest
from src.analyzer import FailureAnalyzer, FailureCategory

def test_detect_env_var_missing():
    """Test detection of missing environment variables."""
    analyzer = FailureAnalyzer()
    logs = """
    Error: environment variable DATABASE_URL not set
    Backend service failed to start
    """

    matches = analyzer.detect_patterns(logs)
    assert len(matches) > 0

    category, confidence = analyzer.classify_failure(matches)
    assert category == FailureCategory.ENV_VAR_MISSING
    assert confidence >= 85
```

### Writing Tests

**Good practices**:
- Test one behavior per test function
- Use descriptive names: `test_<feature>_<scenario>`
- Mock external APIs (GitHub, Coolify, LLMs)
- Use fixtures for common setup
- Test both success and failure paths

**Example with mocking**:

```python
import pytest
from unittest.mock import Mock, patch
from src.github_client import GitHubClient

@patch('src.github_client.Github')
def test_post_pr_comment(mock_github):
    """Test posting a PR comment."""
    # Setup mock
    mock_repo = Mock()
    mock_pr = Mock()
    mock_repo.get_pull.return_value = mock_pr
    mock_github.return_value.get_repo.return_value = mock_repo

    # Test
    client = GitHubClient()
    comment = client.post_pr_comment(
        installation_id=123,
        repo_owner="test",
        repo_name="repo",
        pr_number=1,
        comment="Test comment"
    )

    # Verify
    mock_pr.create_issue_comment.assert_called_once_with("Test comment")
```

---

## Code Quality

### Linting

```bash
# Check code with ruff
ruff check src/

# Auto-fix issues
ruff check --fix src/

# Type checking with mypy
mypy src/
```

### Formatting

```bash
# Format code with black
black src/ tests/

# Or use make command
make format
```

### Pre-commit Checks

Before committing:

```bash
make lint
make test
make format
```

### Code Style Guidelines

- **PEP 8**: Follow Python style guide
- **Type hints**: Use type annotations for functions
- **Docstrings**: Document public functions
- **Max line length**: 100 characters
- **Imports**: Group stdlib, third-party, local

**Example**:

```python
"""Module for analyzing deployment failures."""
from typing import List, Optional

from .models import FailureCategory
from .logging_config import get_logger

logger = get_logger(__name__)


def analyze_failure(logs: str) -> Optional[FailureCategory]:
    """Analyze deployment logs to identify failure category.

    Args:
        logs: Raw deployment logs

    Returns:
        Failure category if detected, None otherwise
    """
    # Implementation
    pass
```

---

## Debugging

### Enable Debug Logging

```bash
# In .env
DEBUG=true
LOG_LEVEL=DEBUG

# Or set environment variable
export DEBUG=true
```

### View Structured Logs

Logs are output as JSON in production, pretty-printed in development:

```python
# Example log output (development)
2025-01-15 10:30:00 [info     ] github_webhook_received    event=pull_request pr_number=42
2025-01-15 10:30:01 [info     ] analysis_complete          category=env_var_missing confidence=95
```

### Debug Webhook Payloads

```python
# In main.py, add temporary logging
@app.post("/webhooks/github")
async def github_webhook(request: Request, ...):
    payload = await request.json()

    # Temporary debug logging
    logger.debug("webhook_payload", payload=payload)

    # ... rest of handler
```

### Interactive Debugging

Use Python debugger:

```python
# Add breakpoint in code
import pdb; pdb.set_trace()

# Or use built-in breakpoint()
breakpoint()
```

### Test Individual Components

```bash
# Python REPL
python

>>> from src.analyzer import FailureAnalyzer
>>> analyzer = FailureAnalyzer()
>>> logs = "Error: DATABASE_URL not set"
>>> matches = analyzer.detect_patterns(logs)
>>> print(matches)
```

---

## Common Tasks

### Add a New Failure Pattern

1. **Define pattern** in `src/analyzer.py`:

```python
FAILURE_PATTERNS.append(
    FailurePattern(
        category=FailureCategory.NEW_CATEGORY,
        pattern=r"your-regex-pattern",
        confidence=90,
        description="Description of this failure"
    )
)
```

2. **Write test** in `tests/test_analyzer.py`:

```python
def test_detect_new_category():
    analyzer = FailureAnalyzer()
    logs = "Sample log line that matches pattern"

    matches = analyzer.detect_patterns(logs)
    category, confidence = analyzer.classify_failure(matches)

    assert category == FailureCategory.NEW_CATEGORY
```

3. **Add to category enum** in `src/models.py`:

```python
class FailureCategory(str, Enum):
    # ... existing categories
    NEW_CATEGORY = "new_category"
```

### Add a New Command

1. **Parse command** in `src/main.py`:

```python
async def handle_issue_comment_event(payload: Dict, db: Session):
    # ... existing parsing

    if command == "newcommand":
        await handle_new_command(installation_id, pr, db)
```

2. **Implement handler**:

```python
async def handle_new_command(
    installation_id: int,
    pr: PullRequest,
    db: Session
):
    """Handle /incidentfox newcommand."""
    logger.info("handling_new_command", pr_id=pr.id)

    # Your logic here

    github_client.post_pr_comment(
        installation_id,
        pr.repo_owner,
        pr.repo_name,
        pr.pr_number,
        "Command result"
    )
```

3. **Update comment formatter** to include command in list

### Update Database Schema

1. **Modify model** in `src/models.py`:

```python
class NewTable(Base):
    __tablename__ = "new_table"
    id = Column(Integer, primary_key=True)
    # ... fields
```

2. **Create migration** (if using Alembic):

```bash
alembic revision --autogenerate -m "Add new_table"
alembic upgrade head
```

3. **Or auto-create** (development only):

```python
# Database tables are auto-created via init_db()
# in src/main.py lifespan
```

### Add LLM Provider

1. **Add client** in `src/analyzer.py`:

```python
if settings.new_llm_api_key:
    self.new_llm_client = NewLLMClient(
        api_key=settings.new_llm_api_key
    )
```

2. **Add analysis method**:

```python
async def _analyze_with_new_llm(self, prompt: str) -> Tuple[...]:
    response = self.new_llm_client.generate(prompt)
    # Parse and return
```

3. **Update config** in `src/config.py`:

```python
new_llm_api_key: Optional[str] = Field(...)
```

---

## Contributing

### Pull Request Process

1. **Fork** the repository
2. **Create branch**: `git checkout -b feature/your-feature`
3. **Make changes** with tests
4. **Run checks**: `make lint && make test`
5. **Commit**: Use clear, descriptive messages
6. **Push**: `git push origin feature/your-feature`
7. **Open PR** with description of changes

### Commit Message Format

```
<type>: <subject>

<body>

<footer>
```

**Types**: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`

**Example**:
```
feat: add support for Python runtime crashes

- Add pattern detection for Python tracebacks
- Extract stack trace from logs
- Generate fix recommendations

Closes #42
```

---

## Troubleshooting

### Common Issues

**1. "Module not found" errors**

```bash
# Ensure you're in virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

**2. "Database locked" (SQLite)**

```bash
# Stop all running instances
pkill -f uvicorn

# Delete database
rm incidentfox.db

# Restart
make dev
```

**3. "Webhook signature verification failed"**

- Check `GITHUB_WEBHOOK_SECRET` matches GitHub App settings
- Verify you're using raw request body (not parsed JSON)
- Check for ngrok URL changes (regenerate on each restart)

**4. "Private key not found"**

```bash
# Check file exists
ls -la private-key.pem

# Check permissions (should be 600)
chmod 600 private-key.pem

# Verify path in .env
grep GITHUB_APP_PRIVATE_KEY_PATH .env
```

**5. Import errors**

```bash
# Set PYTHONPATH
export PYTHONPATH=/path/to/incidentfox-bot:$PYTHONPATH

# Or run from project root
cd incidentfox-bot
python -m src.main
```

---

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [pytest Documentation](https://docs.pytest.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [structlog Documentation](https://www.structlog.org/)
- [GitHub Apps Documentation](https://docs.github.com/en/developers/apps)

---

## Getting Help

- **Issues**: Open a GitHub issue with details
- **Discussions**: Use GitHub Discussions for questions
- **Logs**: Always include relevant logs (redact secrets!)
