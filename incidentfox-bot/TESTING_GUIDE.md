# 🧪 IncidentFox Testing Guide

This guide provides **3 testing approaches** from simplest to most realistic.

## 🎯 Testing Approaches

### Option 1: Offline Analysis Testing (FASTEST - Start Here)

Test the analysis engine without any infrastructure.

**What you need:**
- Python 3.11+
- Anthropic API key

**Steps:**

```bash
cd incidentfox-bot

# Install dependencies
pip install -r requirements.txt

# Set up minimal .env
cat > .env << EOF
ANTHROPIC_API_KEY=sk-ant-your-key-here
LOG_LEVEL=INFO
EOF

# Run test scenarios
python test_runner.py --list                    # See available scenarios
python test_runner.py --scenario missing-env-var
python test_runner.py --scenario port-mismatch
python test_runner.py --scenario build-failure
python test_runner.py --scenario runtime-crash
```

**What this tests:**
- ✅ Failure detection patterns
- ✅ LLM analysis integration
- ✅ PR comment generation
- ✅ Recommendation engine
- ❌ No GitHub integration
- ❌ No Coolify integration
- ❌ No auto-patching

---

### Option 2: Local Bot with Simulated Webhooks (RECOMMENDED)

Run the full bot locally and send it simulated webhook payloads.

**What you need:**
- Everything from Option 1
- GitHub App created (see `docs/GITHUB_APP_SETUP.md`)
- PostgreSQL database

**Steps:**

1. **Create `.env` file:**

```bash
cd incidentfox-bot
cp .env.example .env
```

Edit `.env` with your values:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-your-key-here
GITHUB_APP_ID=123456                          # From GitHub App settings
GITHUB_INSTALLATION_ID=987654                 # After installing to repo
GITHUB_WEBHOOK_SECRET=your_webhook_secret
# Save your GitHub App private key as: ./private-key.pem

# Database (use docker-compose or local PostgreSQL)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/incidentfox

# Optional
OPENAI_API_KEY=sk-...                        # Alternative to Anthropic
COOLIFY_WEBHOOK_SECRET=test_secret           # For webhook verification
```

2. **Start database:**

```bash
docker-compose up -d postgres
```

3. **Run migrations:**

```bash
make migrate
```

4. **Start the bot:**

```bash
make dev
# Bot runs on http://localhost:8000
```

5. **In another terminal, send test webhook:**

```bash
cd incidentfox-bot

# Create a test webhook sender script
cat > send_test_webhook.py << 'EOF'
#!/usr/bin/env python3
"""Send a simulated Coolify webhook to local IncidentFox instance."""

import hashlib
import hmac
import json
import httpx

WEBHOOK_SECRET = "test_secret"  # Match COOLIFY_WEBHOOK_SECRET in .env
BOT_URL = "http://localhost:8000"

def send_deployment_webhook(status: str, pr_number: int, logs: str):
    """Send a deployment status webhook."""

    payload = {
        "event": "deployment.status",
        "deployment": {
            "id": "test-deployment-123",
            "status": status,  # "success" or "failed"
            "application_id": "app-456",
            "environment": f"preview-pr-{pr_number}",
            "logs": logs,
            "created_at": "2025-12-15T10:30:00Z",
            "finished_at": "2025-12-15T10:35:00Z",
        },
        "application": {
            "name": "extend-preview",
            "repository": {
                "url": "https://github.com/extend/enterprise-fullstack-assignment",
                "branch": f"pr-{pr_number}",
            },
        },
    }

    # Sign the webhook
    payload_bytes = json.dumps(payload).encode()
    signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()

    # Send request
    response = httpx.post(
        f"{BOT_URL}/webhooks/coolify",
        json=payload,
        headers={
            "X-Coolify-Signature": f"sha256={signature}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

if __name__ == "__main__":
    # Simulate a failed deployment
    failed_logs = """
[2025-12-15T10:30:47Z] backend-1  | Error: DATABASE_URL environment variable is not set
[2025-12-15T10:30:47Z] backend-1 exited with code 1
[2025-12-15T10:30:48Z] Deployment failed
    """

    send_deployment_webhook(
        status="failed",
        pr_number=123,
        logs=failed_logs
    )
EOF

chmod +x send_test_webhook.py
python send_test_webhook.py
```

**What this tests:**
- ✅ Full webhook handling
- ✅ Database persistence
- ✅ Complete analysis flow
- ✅ GitHub PR comment posting
- ✅ Interactive commands (`/incidentfox` commands)
- ⚠️ Uses simulated webhooks (not real Coolify)

---

### Option 3: Full End-to-End with Real Coolify (PRODUCTION-LIKE)

Deploy both IncidentFox and Coolify, test with real preview deployments.

**What you need:**
- Everything from Option 2
- A server to run Coolify (DigitalOcean, AWS, etc.)
- Public URL for IncidentFox webhooks (ngrok or deployed instance)

**Architecture:**

```
GitHub PR → Coolify (deploys preview) → IncidentFox (analyzes failures) → GitHub PR Comment
```

**Steps:**

1. **Deploy Coolify** (on a cloud server):

```bash
# On your server (Ubuntu 22.04+)
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

2. **Configure Coolify for the Extend repo:**
   - Add the repo as an application
   - Use the `.coolify/config.json` I created in the main repo
   - Set up GitHub integration
   - Configure webhook to trigger on PR events

3. **Deploy IncidentFox:**

```bash
# Option A: Use ngrok for local testing
ngrok http 8000
# Copy the ngrok URL (e.g., https://abc123.ngrok.io)

# Option B: Deploy to Coolify itself
# Use the deployment/coolify-config.json file

# Option C: Deploy to cloud platform (Railway, Fly.io, etc.)
```

4. **Configure Coolify webhooks:**
   - In Coolify UI: Settings → Webhooks
   - Add webhook URL: `https://your-incidentfox-url.com/webhooks/coolify`
   - Add webhook secret (match `COOLIFY_WEBHOOK_SECRET` in IncidentFox `.env`)
   - Enable events: `deployment.started`, `deployment.finished`, `deployment.failed`

5. **Test the full flow:**

```bash
# In the main repo
git checkout -b test/introduce-bug

# Introduce a bug (e.g., remove DATABASE_URL from docker-compose.yml)
vim docker-compose.yml
# Delete the DATABASE_URL environment variable

git add docker-compose.yml
git commit -m "test: remove DATABASE_URL to trigger failure"
git push origin test/introduce-bug

# Open a PR on GitHub
gh pr create --title "Test: Introduce deployment bug" --body "Testing IncidentFox"
```

6. **Watch the magic:**
   - Coolify receives the PR webhook
   - Coolify attempts to deploy preview environment
   - Deployment fails due to missing DATABASE_URL
   - Coolify sends failure webhook to IncidentFox
   - IncidentFox analyzes the logs
   - IncidentFox posts a PR comment with diagnosis and fix
   - You comment: `/incidentfox apply fix`
   - IncidentFox commits the fix to your PR
   - Coolify redeploys automatically
   - Success! ✅

---

## 🎬 Demo Script for Stakeholders

If you want to demo IncidentFox to stakeholders, use **Option 2** with this script:

```bash
# Terminal 1: Start bot
cd incidentfox-bot
make dev

# Terminal 2: Watch logs
cd incidentfox-bot
make logs

# Terminal 3: Send test webhooks
python send_test_webhook.py --scenario missing-env-var
python send_test_webhook.py --scenario port-mismatch

# Show the PR comments that were generated
# Show the interactive commands available
# Demonstrate the `/incidentfox apply fix` flow
```

---

## 🐛 Deliberate Bug Scenarios

Here are specific bugs you can introduce to test IncidentFox:

### 1. Missing Environment Variable

**File:** `docker-compose.yml`

```yaml
# BEFORE (working)
backend:
  environment:
    - DATABASE_URL=postgresql://postgres:password@db:5432/app

# AFTER (broken)
backend:
  environment:
    # - DATABASE_URL=postgresql://postgres:password@db:5432/app  # ← Comment out
```

**Expected:** IncidentFox detects missing `DATABASE_URL`, suggests adding it back

### 2. Port Mismatch

**File:** `backend/server.js` and `docker-compose.yml`

```javascript
// server.js - Change port to 5001
const PORT = 5001;
app.listen(PORT);
```

```yaml
# docker-compose.yml - But healthcheck still checks 3000
backend:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:3000/health"]  # ← Wrong port
```

**Expected:** IncidentFox detects port mismatch, suggests fixing healthcheck to port 5001

### 3. Dependency Version Conflict

**File:** `frontend/package.json`

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "some-package-that-needs-react-17": "^1.0.0"  // ← Add incompatible dep
  }
}
```

**Expected:** IncidentFox detects dependency conflict, suggests resolution strategy

### 4. Syntax Error

**File:** `backend/server.js`

```javascript
// Add a syntax error
const app = express()
// Missing semicolon, extra brace
app.get('/api/data', (req, res) => {
  res.json({ data: 'test' })
}}  // ← Extra brace
```

**Expected:** IncidentFox detects syntax error, points to line number

---

## 📊 Success Metrics

After testing, you should see:

- ✅ PR comments appear within 30 seconds of deployment failure
- ✅ Analysis confidence > 70% for known failure types
- ✅ Recommended fixes are accurate and actionable
- ✅ `/incidentfox apply fix` successfully patches and redeploys
- ✅ No false positives (comments on successful deployments)
- ✅ Handles concurrent PR deployments without race conditions

---

## 🔍 Debugging Tips

If something doesn't work:

1. **Check logs:**
   ```bash
   make logs          # Docker logs
   tail -f app.log    # Application logs
   ```

2. **Verify webhook signature:**
   ```bash
   # In the bot logs, look for:
   # "Webhook signature verification failed"
   ```

3. **Test GitHub API connectivity:**
   ```bash
   python -c "from src.github_client import GitHubClient; client = GitHubClient(); print(client.verify_installation())"
   ```

4. **Test database connection:**
   ```bash
   python -c "from src.database import get_db_session; session = next(get_db_session()); print('DB connected')"
   ```

5. **Test LLM API:**
   ```bash
   python -c "from src.analyzer import FailureAnalyzer; analyzer = FailureAnalyzer(); print('LLM API working')"
   ```

---

## 🚀 Next Steps

Once testing is successful:

1. Deploy IncidentFox to production (see `docs/DEPLOYMENT.md`)
2. Set up monitoring (logs, metrics, alerts)
3. Onboard Extend team
4. Iterate based on real failure patterns
5. Expand failure mode coverage
6. Add custom failure patterns specific to Extend's stack

---

## 💡 Quick Start Recommendation

**For immediate testing:**

```bash
# 1. Install and test offline (5 minutes)
cd incidentfox-bot
pip install -r requirements.txt
echo "ANTHROPIC_API_KEY=your-key" > .env
python test_runner.py --scenario missing-env-var

# 2. If that works, move to local bot testing (15 minutes)
# Set up full .env, start docker-compose, run the bot
# Send simulated webhooks

# 3. If stakeholder demo needed, set up Coolify (1-2 hours)
# Deploy Coolify, configure webhooks, test end-to-end
```
