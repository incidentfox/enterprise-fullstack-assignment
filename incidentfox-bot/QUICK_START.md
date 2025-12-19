# ⚡ Quick Start - Get IncidentFox Running in 15 Minutes

Follow these steps to get IncidentFox analyzing failures locally.

## Step 1: Install GitHub App (5 min)

You already have a GitHub App ID (`2478810`), but you need to:

1. **Install the app to your repository:**
   - Go to: https://github.com/settings/apps
   - Find your IncidentFox app
   - Click "Install App"
   - Select the `enterprise-fullstack-assignment` repository
   - Click "Install"

2. **Get the Installation ID:**
   ```bash
   cd incidentfox-bot
   python3 get_installation_id.py
   ```

   This will output something like:
   ```
   ✨ Add this to your .env file:
   GITHUB_INSTALLATION_ID=12345678
   ```

3. **Add to your .env file:**
   ```bash
   # Open .env and add the line shown above
   nano .env
   ```

## Step 2: Start IncidentFox (5 min)

```bash
cd incidentfox-bot

# Run the setup script (installs dependencies, starts database, runs migrations)
./setup_local.sh
```

The bot will start and show:
```
🦊 IncidentFox is running at http://localhost:8000
```

Keep this terminal open!

## Step 3: Test Without Coolify (2 min)

In a **new terminal**:

```bash
cd incidentfox-bot

# Activate the virtual environment
source venv/bin/activate

# Send a simulated webhook
python simulate_webhook.py --scenario missing-env-var --pr 999
```

You should see:
- IncidentFox logs showing analysis
- A message saying it would post to PR #999

This tests the analysis engine works correctly.

## Step 4: Test With Real GitHub (Optional - 3 min)

To test real GitHub integration:

```bash
# In the main repo
cd ..

# Create a test PR
git checkout -b test/incidentfox-bot
echo "# Test PR for IncidentFox" >> TEST.md
git add TEST.md
git commit -m "test: trigger IncidentFox"
git push origin test/incidentfox-bot

# Open the PR
gh pr create --title "Test: IncidentFox Bot" --body "Testing IncidentFox bot integration"
```

Now manually trigger analysis by posting a comment:
```
/incidentfox help
```

IncidentFox should respond with help info!

## Next Steps

### Option A: Test with Simulated Failures (No Coolify Needed)

Keep testing with simulated webhooks:

```bash
# Test different failure scenarios
python simulate_webhook.py --list  # See available scenarios
python simulate_webhook.py --scenario port-mismatch --pr 999
python simulate_webhook.py --scenario build-failure --pr 999
python simulate_webhook.py --scenario runtime-crash --pr 999
```

Each will show you what IncidentFox would post to GitHub.

### Option B: Set Up Coolify for Real Deployments

Follow `../COOLIFY_LOCAL_SETUP.md` to:
1. Install Coolify locally or use Coolify Cloud
2. Configure the chartmetric repo in Coolify
3. Set up webhooks from Coolify → IncidentFox
4. Create PRs with deliberate bugs
5. Watch IncidentFox automatically diagnose and fix them!

---

## Troubleshooting

### "GITHUB_INSTALLATION_ID" error

```bash
# Make sure you've installed the GitHub App to your repo
# Then run:
python get_installation_id.py

# Add the output to .env
```

### "Anthropic API key" error

```bash
# Verify your .env has:
ANTHROPIC_API_KEY=sk-ant-...  # Should start with sk-ant-
```

### "Private key not found"

```bash
# Make sure private-key.pem is in the incidentfox-bot directory
ls -la private-key.pem

# If not there, download it from GitHub App settings
```

### Database connection errors

```bash
# Restart database
docker-compose restart postgres

# Check it's running
docker-compose ps postgres
```

### Port 8000 already in use

```bash
# Find what's using it
lsof -i :8000

# Kill it or change IncidentFox port in .env:
PORT=8001
```

---

## What's Next?

Once IncidentFox is running locally:

1. **Test all failure scenarios** using `simulate_webhook.py`
2. **Set up Coolify** to test real deployment failures
3. **Create deliberate bugs** in PRs and watch IncidentFox fix them
4. **Customize failure patterns** in `src/analyzer.py` for your stack
5. **Deploy to production** when ready

---

## Quick Reference

### Start IncidentFox
```bash
cd incidentfox-bot
./setup_local.sh
```

### Test Analysis
```bash
python simulate_webhook.py --scenario missing-env-var --pr 999
```

### View Logs
```bash
# In another terminal
tail -f app.log
```

### Stop Everything
```bash
# Press Ctrl+C in the terminal running IncidentFox
# Then stop database:
docker-compose down
```

### Restart Fresh
```bash
docker-compose down -v  # Remove database
./setup_local.sh        # Start fresh
```
