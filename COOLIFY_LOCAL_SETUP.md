# 🚀 Local Coolify Setup Guide

This guide will help you run Coolify locally to test the full IncidentFox integration.

## Option 1: Coolify via Docker (Simplest)

Coolify provides an official Docker setup for local testing.

### Prerequisites

- Docker Desktop installed and running
- At least 4GB RAM available
- Ports 80, 443, 8000, 6001 available

### Step 1: Install Coolify Locally

```bash
# Create a directory for Coolify
mkdir -p ~/coolify-local
cd ~/coolify-local

# Download Coolify's docker-compose
curl -fsSL https://cdn.coollabs.io/coolify/docker-compose.yml -o docker-compose.yml

# Start Coolify
docker-compose up -d

# Check status
docker-compose ps
```

### Step 2: Access Coolify UI

1. Open browser: `http://localhost:8000`
2. Create admin account (first time only)
3. Complete setup wizard

### Step 3: Configure GitHub Integration

In Coolify UI:

1. Go to **Settings** → **Sources**
2. Click **Add Source**
3. Select **GitHub**
4. Follow OAuth flow to connect your GitHub account
5. Grant access to the `chartmetric/enterprise-fullstack-assignment` repo

### Step 4: Add the Chartmetric App

1. Go to **Applications** → **New Application**
2. Select **Docker Compose**
3. Configure:
   - **Name:** chartmetric-preview
   - **Repository:** chartmetric/enterprise-fullstack-assignment
   - **Branch:** Leave as `main` (will be overridden per PR)
   - **Docker Compose File:** `docker-compose.yml`
4. Click **Create**

### Step 5: Set Environment Variables

In the application settings, add:

```
NEXT_PUBLIC_API_URL=http://backend:5001
DATABASE_URL=postgresql://postgres:password@db:5432/chartmetric
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=chartmetric
```

### Step 6: Configure Webhooks

1. In Coolify, go to **Settings** → **Webhooks**
2. Click **Add Webhook**
3. Configure:
   - **URL:** `http://host.docker.internal:8000/webhooks/coolify` (for local IncidentFox)
   - **Secret:** Generate a random string (e.g., `openssl rand -hex 32`)
   - **Events:** Select all deployment events
4. Save the secret

### Step 7: Update IncidentFox .env

```bash
cd incidentfox-bot
```

Edit `.env`:

```bash
# Update these lines
COOLIFY_API_URL=http://localhost:8000
COOLIFY_API_TOKEN=<get_from_coolify_settings_api>
COOLIFY_WEBHOOK_SECRET=<your_webhook_secret_from_step_6>
```

To get API token:
- In Coolify UI: **Settings** → **API Tokens** → **Generate New Token**

---

## Option 2: Coolify Cloud (Fastest - Recommended)

If you don't want to run Coolify locally, use their managed service:

1. Go to [https://app.coolify.io](https://app.coolify.io)
2. Sign up for free account
3. Follow the same steps above (Step 3-7)
4. Your Coolify URL will be: `https://app.coolify.io`

**Pros:**
- No local resources needed
- Real webhook URLs (no ngrok needed)
- Faster setup

**Cons:**
- Requires internet connection
- May have rate limits on free tier

---

## Testing the Setup

Once Coolify is running:

### 1. Test Coolify is Working

```bash
# Check Coolify API
curl http://localhost:8000/api/health

# Should return: {"status":"ok"}
```

### 2. Test IncidentFox Connection

```bash
cd incidentfox-bot

# Start IncidentFox
make dev

# In another terminal, send a test webhook
python simulate_webhook.py --scenario missing-env-var --pr 123
```

### 3. Trigger Real Deployment

```bash
# In the main repo
cd /Users/jimmywei/development/repos/enterprise-fullstack-assignment

# Create test PR with intentional bug
git checkout -b test/coolify-integration

# Introduce a bug (remove DATABASE_URL)
sed -i '' '/DATABASE_URL=/d' docker-compose.yml

git add docker-compose.yml
git commit -m "test: remove DATABASE_URL to trigger failure"
git push origin test/coolify-integration

# Open PR
gh pr create --title "Test: Coolify Integration" --body "Testing IncidentFox with real Coolify deployment"
```

### 4. Watch the Magic

1. **Coolify** receives GitHub webhook
2. **Coolify** attempts to deploy preview environment
3. **Deployment fails** (missing DATABASE_URL)
4. **Coolify** sends failure webhook to IncidentFox
5. **IncidentFox** analyzes logs
6. **IncidentFox** posts diagnostic comment to PR
7. Comment on PR: `/incidentfox apply fix`
8. **IncidentFox** commits the fix
9. **Coolify** auto-redeploys
10. **Success!** ✅

---

## Troubleshooting

### Coolify won't start

```bash
# Check logs
docker-compose logs -f

# Common issues:
# - Port 8000 already in use (stop other services)
# - Docker out of memory (increase Docker RAM to 4GB+)
```

### Webhooks not reaching IncidentFox

If running both locally:

```bash
# Use host.docker.internal instead of localhost
COOLIFY_WEBHOOK_URL=http://host.docker.internal:8000/webhooks/coolify
```

If IncidentFox is on a different machine:

```bash
# Use ngrok to expose IncidentFox
ngrok http 8000

# Use ngrok URL in Coolify webhook settings
COOLIFY_WEBHOOK_URL=https://abc123.ngrok.io/webhooks/coolify
```

### Coolify can't access GitHub repo

1. Check GitHub App permissions in Coolify settings
2. Ensure repo is accessible to the connected GitHub account
3. Try reconnecting GitHub source

### Deployments not triggering

1. Check Coolify has webhook configured in GitHub (Settings → Webhooks)
2. Verify branch is monitored in Coolify app settings
3. Check GitHub webhook delivery logs

---

## Next Steps

Once Coolify is working:

1. ✅ Test with a simple deployment (no bugs)
2. ✅ Introduce deliberate bugs (see TESTING_GUIDE.md)
3. ✅ Verify IncidentFox responds correctly
4. ✅ Test interactive commands (`/incidentfox apply fix`)
5. ✅ Test multiple concurrent PRs

---

## Production Deployment

For production, deploy Coolify to a cloud server:

```bash
# On Ubuntu 22.04+ server
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash

# Follow prompts to configure domain, SSL, etc.
```

See Coolify docs: https://coolify.io/docs/installation
