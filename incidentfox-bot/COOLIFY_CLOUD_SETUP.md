# ☁️ Coolify Cloud Setup Instructions

Your IncidentFox bot is ready! Follow these steps to connect it with Coolify Cloud.

## 🌐 Your Bot's Public URLs

Your ngrok tunnel is running:
- **Bot URL:** https://066ae13c072c.ngrok-free.app
- **Coolify Webhook Endpoint:** https://066ae13c072c.ngrok-free.app/webhooks/coolify
- **GitHub Webhook Endpoint:** https://066ae13c072c.ngrok-free.app/webhooks/github

---

## 📝 Step 1: Update GitHub App Webhooks

1. Go to: https://github.com/settings/apps
2. Find your IncidentFox app
3. Click "Edit"
4. Update **Webhook URL** to:
   ```
   https://066ae13c072c.ngrok-free.app/webhooks/github
   ```
5. Keep your webhook secret (already in .env)
6. Save changes

---

## 📝 Step 2: Sign Up for Coolify Cloud

1. Go to: **https://app.coolify.io**
2. Click **"Sign Up"** or **"Get Started"**
3. Create account with your email
4. Verify email if required

---

## 📝 Step 3: Connect GitHub to Coolify

1. In Coolify dashboard, go to **"Sources"** or **"Integrations"**
2. Click **"Add Source"** → Select **GitHub**
3. Authorize Coolify to access your GitHub account
4. Grant access to the `enterprise-fullstack-assignment` repository

---

## 📝 Step 4: Add Server (If Required)

Coolify Cloud may ask you to connect a server for deployments.

**Option A: Use Coolify's Infrastructure (Easiest)**
- If they offer managed infrastructure, use that
- Follow their wizard

**Option B: Bring Your Own Server**
- If you have a cloud server (DigitalOcean, AWS, etc.), connect it
- Coolify will install Docker and configure it automatically

**Option C: Skip for Now**
- Some Coolify plans let you test without infrastructure first
- You can add it later

---

## 📝 Step 5: Create Application in Coolify

1. In Coolify dashboard, click **"New Resource"** or **"Add Application"**
2. Select **"GitHub"** as source
3. Choose repository: **`extend/enterprise-fullstack-assignment`** (or your Extend fork)
4. Configure:
   - **Name:** extend-preview
   - **Environment:** Create new environment called "preview"
   - **Branch:** `main` (will be overridden per PR)
   - **Build Pack:** Docker Compose
   - **Docker Compose File:** `docker-compose.yml`

5. **Environment Variables** (Important!):
   Click "Add Environment Variable" and add these:

   ```
   NEXT_PUBLIC_API_URL=http://api:5000
   DATABASE_URL=postgresql://postgres:password@db:5432/app
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=password
   POSTGRES_DB=app
   ```

6. **Preview Deployments:**
   - ✅ Enable "Deploy on Pull Request"
   - ✅ Enable "Automatic Deployments"

7. Click **"Save"** or **"Create Application"**

---

## 📝 Step 6: Configure Coolify Webhook to IncidentFox

This is the crucial step that connects Coolify to your bot!

1. In Coolify, go to your application settings
2. Find **"Webhooks"** or **"Notifications"** section
3. Click **"Add Webhook"**
4. Configure:
   - **URL:** `https://066ae13c072c.ngrok-free.app/webhooks/coolify`
   - **Secret:** `test_secret` (same as in your .env)
   - **Events:** Select:
     - ✅ `deployment.started`
     - ✅ `deployment.failed`
     - ✅ `deployment.success`
5. Save webhook

---

## 📝 Step 7: Test with a Real PR

Now for the moment of truth!

### 7.1: Create a PR with a deliberate bug

```bash
cd /Users/jimmywei/development/repos/enterprise-fullstack-assignment

# Create a new branch
git checkout -b test/coolify-incidentfox

# Introduce a bug - remove DATABASE_URL from docker-compose.yml
sed -i '' '/DATABASE_URL/d' docker-compose.yml

# Commit and push
git add docker-compose.yml
git commit -m "test: remove DATABASE_URL to trigger failure"
git push origin test/coolify-incidentfox

# Create PR
gh pr create --title "Test: IncidentFox Integration" --body "Testing deployment failure detection and auto-fix"
```

### 7.2: What Should Happen

1. **Coolify receives GitHub webhook** (PR created)
2. **Coolify starts preview deployment** for your PR branch
3. **Deployment fails** (missing DATABASE_URL)
4. **Coolify sends webhook** to IncidentFox at `https://066ae13c072c.ngrok-free.app/webhooks/coolify`
5. **IncidentFox:**
   - Receives webhook ✅
   - Fetches deployment logs from Coolify ✅
   - Analyzes with Claude 4.5 Sonnet ✅
   - Posts diagnostic comment to PR ✅
6. **You see a PR comment** with:
   - Failure category
   - Root cause analysis
   - Recommended fixes
   - Interactive commands

### 7.3: Test Interactive Commands

Once you see the PR comment, try:
```
/incidentfox apply fix
```

IncidentFox should:
- Generate a safe patch
- Commit it to your PR
- Trigger Coolify to redeploy
- Success! ✅

---

## 🔍 Monitoring & Debugging

### Check Bot Logs

In your terminal where the bot is running, you should see:
```bash
# Watch live logs
tail -f /tmp/claude/tasks/b164b80.output

# Or check recent activity
tail -100 /tmp/claude/tasks/b164b80.output
```

Look for:
- `coolify_webhook_received` - Webhook arrived
- `anthropic_analysis_complete` - Claude analyzed it
- `pr_comment_posted` - Posted to GitHub

### Check Coolify Logs

In Coolify dashboard:
1. Go to your application
2. Click on the deployment
3. View "Logs" tab
4. Check "Webhooks" section to see if it sent to IncidentFox

### Test Webhook Manually

You can test the webhook endpoint:
```bash
curl https://066ae13c072c.ngrok-free.app/health
# Should return: {"status":"healthy","checks":{...}}
```

---

## ⚠️ Important Notes

### Ngrok Session
Your ngrok tunnel (`https://066ae13c072c.ngrok-free.app`) is:
- ✅ Running right now
- ⚠️ Will change if you restart ngrok
- ⚠️ Free tier may have rate limits

If ngrok disconnects, you'll need to:
1. Get the new ngrok URL
2. Update GitHub App webhook URL
3. Update Coolify webhook URL

### Keep Bot Running
Your IncidentFox bot is running in the background. To keep it alive:
- Don't close your terminal
- Or restart with: `cd incidentfox-bot && source .venv/bin/activate && uvicorn src.main:app --reload`

---

## 🎯 Success Checklist

Before creating the test PR, verify:

- [ ] Coolify account created
- [ ] GitHub connected to Coolify
- [ ] Application created in Coolify (extend-preview)
- [ ] Preview deployments enabled
- [ ] Coolify webhook configured with `https://066ae13c072c.ngrok-free.app/webhooks/coolify`
- [ ] GitHub App webhook updated with `https://066ae13c072c.ngrok-free.app/webhooks/github`
- [ ] IncidentFox bot is running (check http://localhost:8000/health)
- [ ] Ngrok is running (check https://066ae13c072c.ngrok-free.app/health)

---

## 🚀 Ready to Test!

Once you've completed Steps 1-6 above, run the commands in Step 7 to create a test PR.

**Expected timeline:**
- PR created → ~5 seconds
- Coolify starts deployment → ~30 seconds
- Deployment fails → ~1-2 minutes
- IncidentFox analyzes → ~5 seconds
- PR comment appears → ~2 seconds

**Total:** ~2-3 minutes from PR creation to seeing IncidentFox's comment!

---

## ❓ Need Help?

Check:
- Bot logs: `tail -f /tmp/claude/tasks/b164b80.output`
- Coolify logs: In Coolify dashboard → Your app → Deployments
- Webhook deliveries: GitHub App settings → Advanced → Recent Deliveries
- Ngrok web interface: http://localhost:4040

Let me know if you hit any issues!
