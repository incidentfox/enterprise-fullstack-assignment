# GitHub App Setup Guide

This guide walks you through creating and configuring a GitHub App for IncidentFox.

## Step 1: Create GitHub App

1. Go to your GitHub organization settings (or personal settings)
2. Navigate to **Developer settings** → **GitHub Apps** → **New GitHub App**

## Step 2: Basic Information

Fill in the basic information:

- **GitHub App name**: `IncidentFox` (or your preferred name)
- **Homepage URL**: Your IncidentFox deployment URL or repo URL
- **Webhook URL**: `https://your-incidentfox-domain.com/webhooks/github`
- **Webhook secret**: Generate a strong secret (save this for `.env` file)
  ```bash
  # Generate a webhook secret
  openssl rand -hex 32
  ```

## Step 3: Permissions

Configure the following **Repository permissions**:

| Permission | Access | Reason |
|------------|--------|--------|
| **Contents** | Read & write | To commit fixes to PR branches |
| **Pull requests** | Read & write | To read PR data and post comments |
| **Issues** | Read & write | To read and respond to issue comments (PR comments are issues) |
| **Metadata** | Read-only | To access basic repository information |
| **Commit statuses** | Read-only | Optional: to check CI status |

## Step 4: Subscribe to Events

Subscribe to these webhook events:

- [x] **Pull request**
  - Triggers: `opened`, `reopened`, `synchronize` (new commits)
- [x] **Issue comment**
  - Triggers: To handle `/incidentfox` commands in PR comments

## Step 5: Where can this GitHub App be installed?

Choose based on your needs:

- **Only on this account**: For private/internal use
- **Any account**: If you want to distribute IncidentFox publicly

## Step 6: Create the App

Click **Create GitHub App**.

## Step 7: Generate Private Key

After creation:

1. Scroll down to **Private keys** section
2. Click **Generate a private key**
3. A `.pem` file will download automatically
4. Save this file securely as `private-key.pem` in your IncidentFox deployment directory
5. Set permissions: `chmod 600 private-key.pem`

## Step 8: Note Your App ID

At the top of your GitHub App settings page, you'll see:

```
App ID: 123456
```

Save this for your `.env` file.

## Step 9: Install the App

1. Go to **Install App** in the left sidebar
2. Choose the organization/account where you want to install it
3. Select repositories:
   - **All repositories**: IncidentFox will work on all repos
   - **Only select repositories**: Choose specific repos

4. Click **Install**

5. After installation, note the **Installation ID** from the URL:
   ```
   https://github.com/settings/installations/12345678
                                              ^^^^^^^^
                                           Installation ID
   ```

   You'll need this for API calls (though it's also available via webhooks).

## Step 10: Configure IncidentFox

Update your `.env` file:

```bash
# GitHub App Configuration
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_PATH=./private-key.pem
GITHUB_WEBHOOK_SECRET=your_webhook_secret_from_step_2
```

## Step 11: Test Webhook Delivery

### For Local Development (using ngrok):

```bash
# Start ngrok
ngrok http 8000

# Update GitHub App webhook URL to:
https://your-ngrok-url.ngrok.io/webhooks/github
```

### Verify Webhook:

1. Go to your GitHub App settings
2. Click **Advanced** → **Recent Deliveries**
3. You should see webhook events being delivered
4. Green checkmarks (200 response) indicate success

## Step 12: Verify Installation

Create a test PR in an installed repository and check:

1. **IncidentFox appears in "Checks"** (optional, if you add check runs)
2. **Webhook deliveries are successful** in GitHub App settings
3. **IncidentFox logs show received webhooks**:
   ```bash
   docker-compose logs -f incidentfox
   ```

## Troubleshooting

### Webhook Signature Verification Failed

- Double-check your `GITHUB_WEBHOOK_SECRET` matches the one in GitHub App settings
- Ensure you're passing the raw request body to verification (not parsed JSON)

### App Cannot Post Comments

- Verify **Pull requests** permission is set to **Read & write**
- Verify **Issues** permission is set to **Read & write**
- Check the GitHub App is installed on the repository

### Private Key Issues

```bash
# Verify private key format
head -n 1 private-key.pem
# Should output: -----BEGIN RSA PRIVATE KEY-----

# Check file permissions
ls -la private-key.pem
# Should be: -rw------- (600)
```

### Cannot Commit to Branch

- Verify **Contents** permission is set to **Read & write**
- Check branch protection rules don't block the bot
- Ensure the GitHub App has write access to the repository

## Security Best Practices

1. **Webhook Secret**: Use a cryptographically random secret (32+ bytes)
2. **Private Key**: Never commit the private key to git
   - Add to `.gitignore`
   - Store securely (e.g., Kubernetes secrets, encrypted vault)
3. **Permissions**: Only grant minimum required permissions
4. **Audit Logs**: Regularly review GitHub App audit logs
5. **Token Rotation**: Regenerate webhook secrets periodically

## Advanced: Multi-Tenant Setup

If deploying IncidentFox as a service for multiple organizations:

1. Use **Any account** installation option
2. Store installation IDs per repository in database
3. Implement per-installation rate limiting
4. Consider separate databases per tenant

## GitHub App Manifest (Alternative)

You can also create the app programmatically using a manifest:

```json
{
  "name": "IncidentFox",
  "url": "https://github.com/your-org/incidentfox",
  "hook_attributes": {
    "url": "https://your-incidentfox-domain.com/webhooks/github"
  },
  "public": false,
  "default_permissions": {
    "contents": "write",
    "pull_requests": "write",
    "issues": "write",
    "metadata": "read"
  },
  "default_events": [
    "pull_request",
    "issue_comment"
  ]
}
```

Navigate to:
```
https://github.com/settings/apps/new?manifest=<BASE64_ENCODED_MANIFEST>
```

## References

- [GitHub Apps Documentation](https://docs.github.com/en/developers/apps)
- [Authenticating with GitHub Apps](https://docs.github.com/en/developers/apps/building-github-apps/authenticating-with-github-apps)
- [Webhook Events](https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads)
