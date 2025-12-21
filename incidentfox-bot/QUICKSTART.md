# ⚡ IncidentFox Quick Start

Get IncidentFox running in 10 minutes.

## Prerequisites Checklist

- [ ] Python 3.11+ installed
- [ ] GitHub App created with webhook secret ([Setup Guide](./docs/GITHUB_APP_SETUP.md))
- [ ] GitHub App private key downloaded
- [ ] Anthropic API key OR OpenAI API key
- [ ] Coolify instance with API access

## Local Development (5 minutes)

### 1. Clone and Navigate

```bash
cd incidentfox-bot
```

### 2. Create Environment File

```bash
cp .env.example .env
```

### 3. Edit .env with Your Credentials

```bash
# Required - edit these values
GITHUB_APP_ID=your_app_id_here
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here
COOLIFY_API_URL=https://your-coolify-instance.com
COOLIFY_API_TOKEN=your_coolify_api_token_here
ANTHROPIC_API_KEY=sk-ant-your-key-here  # OR use OPENAI_API_KEY
```

### 4. Add GitHub App Private Key

```bash
# Copy your downloaded GitHub App private key
cp ~/Downloads/your-app-name.2025-01-15.private-key.pem ./private-key.pem
chmod 600 private-key.pem
```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

### 6. Start Development Server

```bash
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Server is now running at http://localhost:8000

### 7. Setup Webhook Forwarding (in another terminal)

```bash
# Install ngrok if you haven't: https://ngrok.com/download
ngrok http 8000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

### 8. Update GitHub App Webhook URL

1. Go to your GitHub App settings
2. Update webhook URL to: `https://abc123.ngrok.io/webhooks/github`
3. Save changes

### 9. Test

```bash
# Check health
curl http://localhost:8000/health

# Should return:
# {"status": "healthy", "timestamp": "...", "checks": {...}}
```

**Done!** Create a PR in a repository where the app is installed and watch it work.

---

## Production Deployment (Coolify)

### 1. Add Repository to Coolify

1. Open Coolify dashboard
2. **Projects** → **Add Resource** → **Application**
3. Select this repository
4. Choose **Dockerfile** as build pack

### 2. Set Environment Variables in Coolify UI

```bash
ENVIRONMENT=production
DEBUG=false
GITHUB_APP_ID=<your_app_id>
GITHUB_APP_PRIVATE_KEY_PATH=/app/keys/private-key.pem
GITHUB_WEBHOOK_SECRET=<your_secret>
COOLIFY_API_URL=<your_coolify_url>
COOLIFY_API_TOKEN=<your_token>
ANTHROPIC_API_KEY=<your_key>
DATABASE_URL=postgresql://user:pass@postgres:5432/incidentfox
```

Mark as secrets: `GITHUB_WEBHOOK_SECRET`, `COOLIFY_API_TOKEN`, `ANTHROPIC_API_KEY`, `DATABASE_URL`

### 3. Upload Private Key

**Option A**: Use Coolify file storage
- Upload `private-key.pem` to Coolify
- Mount at `/app/keys/private-key.pem` in container

**Option B**: Use environment variable (less secure)
- Set `GITHUB_APP_PRIVATE_KEY` env var with full key content
- Update code to read from env var instead of file

### 4. Configure Webhooks

**GitHub App**:
- Webhook URL: `https://your-incidentfox-domain.com/webhooks/github`

**Coolify**:
- For each application you want to monitor
- Add webhook: `https://your-incidentfox-domain.com/webhooks/coolify`
- Events: `deployment.started`, `deployment.success`, `deployment.failed`

### 5. Deploy

Click **Deploy** in Coolify.

### 6. Verify

```bash
curl https://your-incidentfox-domain.com/health
```

**Done!** IncidentFox is now monitoring your deployments.

---

## Docker Compose Deployment

### 1. Configure

```bash
cd incidentfox-bot
cp .env.example .env
# Edit .env with your credentials
cp ~/path/to/private-key.pem ./private-key.pem
chmod 600 private-key.pem
```

### 2. Start

```bash
docker-compose up -d
```

### 3. Check Logs

```bash
docker-compose logs -f incidentfox
```

### 4. Setup Reverse Proxy

Configure nginx/caddy to forward `yourdomain.com` → `localhost:8000`

**Done!**

---

## Available Commands (in PR comments)

Once deployed, use these commands in PR comments:

```
/incidentfox apply fix
```
Generates and applies an automated fix (if safe to do so)

```
/incidentfox show logs
```
Shows the full deployment logs in a comment

```
/incidentfox rerun
```
Triggers a new deployment in Coolify

---

## Troubleshooting

### "Webhook signature verification failed"

→ Check that `GITHUB_WEBHOOK_SECRET` matches GitHub App settings

### "Module not found" errors

```bash
pip install -r requirements.txt
```

### "Private key not found"

```bash
ls -la private-key.pem  # Check it exists
chmod 600 private-key.pem  # Fix permissions
```

### "Database connection failed"

→ If using PostgreSQL, ensure `DATABASE_URL` is correct
→ For local dev, use SQLite: `DATABASE_URL=sqlite:///./incidentfox.db`

### ngrok URL keeps changing

→ Get a free permanent ngrok domain: `ngrok http 8000 --domain=your-domain.ngrok.io`

### "Cannot connect to Coolify API"

→ Check `COOLIFY_API_URL` is correct (include `https://`)
→ Verify `COOLIFY_API_TOKEN` is valid

---

## Common Make Commands

```bash
make setup-dev    # Setup development environment
make install      # Install dependencies
make dev          # Run with hot reload
make test         # Run tests
make lint         # Check code quality
make format       # Format code
make build        # Build Docker image
make up           # Start docker-compose
make down         # Stop docker-compose
make logs         # View logs
```

---

## File Structure Quick Reference

```
incidentfox-bot/
├── src/main.py              # FastAPI app (webhook handlers)
├── src/analyzer.py          # Failure analysis (patterns + LLM)
├── src/github_client.py     # GitHub API integration
├── src/coolify_client.py    # Coolify API integration
├── src/patch_generator.py   # Safe patch generation
├── .env                     # Your configuration (git-ignored)
├── private-key.pem          # GitHub App key (git-ignored)
├── requirements.txt         # Python dependencies
└── docker-compose.yml       # Local stack
```

---

## Configuration Cheat Sheet

### Minimum Required .env

```bash
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_PATH=./private-key.pem
GITHUB_WEBHOOK_SECRET=your_secret
COOLIFY_API_URL=https://coolify.example.com
COOLIFY_API_TOKEN=your_token
ANTHROPIC_API_KEY=sk-ant-...
```

### Optional Settings

```bash
DATABASE_URL=postgresql://...  # Default: SQLite
ENABLE_AUTO_FIX=true          # Default: false (safety)
DEBUG=true                    # Default: false
LOG_LEVEL=DEBUG               # Default: INFO
MAX_PATCH_FILES=10            # Default: 5
```

---

## Security Checklist

- [ ] Webhook secret is strong (32+ random bytes)
- [ ] Private key has 600 permissions
- [ ] Database uses strong password (if Postgres)
- [ ] All secrets in environment variables (not code)
- [ ] HTTPS enabled with valid certificate
- [ ] `.env` and `private-key.pem` in `.gitignore`

---

## Getting Help

- **Documentation**: See [docs/](./docs/) directory
- **Architecture**: [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)
- **Setup Issues**: [docs/GITHUB_APP_SETUP.md](./docs/GITHUB_APP_SETUP.md)
- **Deployment**: [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md)
- **Development**: [docs/DEVELOPMENT.md](./docs/DEVELOPMENT.md)

---

## What's Next?

1. **Test it**: Create a PR with a deployment failure
2. **Customize**: Add more failure patterns in `src/analyzer.py`
3. **Monitor**: Watch structured logs for insights
4. **Optimize**: Tune LLM usage based on your needs
5. **Extend**: Add new commands or integrations

---

**Ready to go!** 🚀

Visit http://localhost:8000 (local) or your deployed domain to verify it's running.
