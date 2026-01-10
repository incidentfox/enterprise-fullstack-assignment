# 🦊 IncidentFox

**AI SRE for GitHub Pull Requests**

IncidentFox is a production-grade GitHub App that automatically detects, diagnoses, and helps fix deployment failures in pull request preview environments. Built specifically for teams using Coolify for ephemeral preview deployments.

## 🎯 Features

- **Automatic Failure Detection**: Monitors Coolify deployments and detects failures in real-time
- **Intelligent Analysis**: Combines deterministic pattern matching with LLM-powered root cause analysis
- **PR-Native UX**: All diagnostics and actions happen directly in GitHub PR comments
- **Safe Auto-Remediation**: Generate and apply fixes with human approval (file whitelist enforced)
- **Interactive Commands**: Control the bot via `/incidentfox` commands in PR comments
- **Production-Ready**: Webhook signature verification, structured logging, retry logic, idempotency

## 🏗️ Architecture

```
GitHub PR → Coolify Deployment (Fails)
    ↓
Coolify Webhook → IncidentFox
    ↓
Fetch Logs + Analyze (Pattern Matching + LLM)
    ↓
Post Diagnosis to PR Comment
    ↓
Developer: "/incidentfox apply fix"
    ↓
Generate Safe Patch → Commit → Redeploy
```

### Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy
- **Database**: PostgreSQL (or SQLite for development)
- **GitHub**: PyGithub for App authentication
- **AI**: Anthropic Claude 4.5 Sonnet (with optional Opus 4.5 for complex cases)
- **Deployment**: Docker + Coolify

## 🚀 Quick Start

### Prerequisites

1. **GitHub App**: You need to create a GitHub App ([Setup Guide](./docs/GITHUB_APP_SETUP.md))
2. **Coolify Instance**: A running Coolify server with API access (or use Coolify Cloud)
3. **Anthropic API Key**: Required for Claude 4.5 analysis

### Local Development

1. **Clone and Setup**:
   ```bash
   cd incidentfox-bot
   cp .env.example .env
   # Edit .env with your credentials
   ```

2. **Add GitHub App Private Key**:
   ```bash
   # Download your GitHub App private key and save as:
   cp ~/Downloads/your-app.private-key.pem ./private-key.pem
   chmod 600 private-key.pem
   ```

3. **Start with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

4. **Verify**:
   ```bash
   curl http://localhost:8000/health
   ```

5. **Setup Webhook Forwarding** (for local testing):
   ```bash
   # Using ngrok
   ngrok http 8000

   # Update GitHub App webhook URL to: https://your-ngrok-url.ngrok.io/webhooks/github
   # Update Coolify webhook URL to: https://your-ngrok-url.ngrok.io/webhooks/coolify
   ```

### Production Deployment

See [DEPLOYMENT.md](./docs/DEPLOYMENT.md) for detailed production deployment instructions.

**Quick Deploy to Coolify**:

1. Add this repository to your Coolify instance
2. Use the configuration in `deployment/coolify-config.json`
3. Set all required environment variables in Coolify UI
4. Deploy

## 📖 Usage

### In Your GitHub PRs

Once installed, IncidentFox automatically monitors your PRs. When a Coolify deployment fails, you'll see a comment like:

```markdown
## 🔐 IncidentFox Deployment Analysis

**Status:** ❌ Deployment Failed
**Category:** `env_var_missing`
**Confidence:** 🟢🟢🟢🟢🟢 (95%)

### 📋 Summary
> Environment variable DATABASE_URL is not defined in the backend service

### 🔍 Root Cause
The backend container is failing to start because the DATABASE_URL environment
variable is required but not set in docker-compose.yml...

### 💡 Recommended Fixes
1. Add DATABASE_URL to the backend service environment section
2. Ensure the database service is healthy before backend starts
3. Verify the connection string format

### 🤖 Available Commands
- `/incidentfox apply fix` - Generate and apply an automated fix
- `/incidentfox show logs` - Show detailed deployment logs
- `/incidentfox rerun` - Trigger a new deployment
```

### Available Commands

Reply to the bot's comment with:

- **`/incidentfox apply fix`**: Generates a safe patch and commits it to your PR branch
- **`/incidentfox show logs`**: Shows the full deployment logs
- **`/incidentfox rerun`**: Triggers a new Coolify deployment

## 🔍 Failure Detection

IncidentFox detects and analyzes these failure categories:

| Category | Description | Auto-Fix Available |
|----------|-------------|-------------------|
| `env_var_missing` | Missing environment variables | ✅ Yes |
| `port_mismatch` | Port conflicts or healthcheck issues | ⚠️ Partial |
| `dependency_error` | Missing npm/pip packages | ⚠️ Partial |
| `build_failure` | Docker build failures | ❌ No |
| `runtime_crash` | Application crashes on startup | ❌ No |
| `healthcheck_failure` | Container healthcheck timeout | ❌ No |
| `database_connection` | DB connection failures | ⚠️ Partial |

## 🛡️ Security

### File Whitelist

Auto-fixes are **only** allowed for these file patterns (configurable):

- `Dockerfile`
- `docker-compose*.yml`
- `.env.example`
- `package*.json`
- `requirements*.txt`
- `*.config.js`
- `*.config.ts`
- `tsconfig.json`
- `Makefile`

### Webhook Verification

All webhooks (GitHub + Coolify) use HMAC-SHA256 signature verification.

### Audit Logging

Every action is logged with:
- Timestamp
- User who triggered the action
- Files modified
- Commit SHA

## 📊 Database Schema

See [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) for full schema documentation.

Key tables:
- `pull_requests`: Track PRs
- `deployments`: Track Coolify deployments
- `analyses`: Store failure analyses
- `actions`: Log user commands

## 🔧 Configuration

### Environment Variables

See [.env.example](./.env.example) for all configuration options.

**Required**:
- `GITHUB_APP_ID`: Your GitHub App ID
- `GITHUB_APP_PRIVATE_KEY_PATH`: Path to private key file
- `GITHUB_WEBHOOK_SECRET`: Webhook secret from GitHub App
- `COOLIFY_API_URL`: Your Coolify instance URL
- `COOLIFY_API_TOKEN`: Coolify API token
- At least one of: `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`

**Optional**:
- `COOLIFY_WEBHOOK_SECRET`: Coolify webhook secret (recommended)
- `ENABLE_AUTO_FIX`: Allow automatic fixes (default: `false`)
- `MAX_PATCH_FILES`: Max files per patch (default: `5`)

### Feature Flags

- `ENABLE_AUTO_FIX=false`: Prevents automatic commits (safety)
- `ENABLE_ANTHROPIC=true`: Prefer Claude over GPT-4

## 🧪 Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Type checking
mypy src/

# Linting
ruff check src/
black --check src/
```

## 📚 Documentation

- [GitHub App Setup](./docs/GITHUB_APP_SETUP.md)
- [Deployment Guide](./docs/DEPLOYMENT.md)
- [Architecture Overview](./docs/ARCHITECTURE.md)
- [Development Guide](./docs/DEVELOPMENT.md)

## 🤝 Contributing

This is a production implementation for IncidentFox. For bugs or feature requests, please open an issue.

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

Built for the **Extend** team as a solution to real deployment pain points.

---

**🦊 IncidentFox** - Because your PRs deserve better incident response.
