# Deployment Guide

This guide covers deploying IncidentFox to production using various platforms.

## Table of Contents

- [Coolify Deployment](#coolify-deployment)
- [Docker Compose Deployment](#docker-compose-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Environment Variables](#environment-variables)
- [Database Setup](#database-setup)
- [Monitoring & Observability](#monitoring--observability)

---

## Coolify Deployment

### Prerequisites

- A running Coolify instance
- GitHub App created and configured ([Setup Guide](./GITHUB_APP_SETUP.md))
- API keys for OpenAI and/or Anthropic

### Step 1: Add Repository to Coolify

1. Log in to your Coolify dashboard
2. Navigate to **Projects** → **Add Resource** → **Application**
3. Choose **GitHub Repository**
4. Select or add your IncidentFox repository

### Step 2: Configure Application

1. **Build Pack**: Choose `Dockerfile`
2. **Dockerfile Location**: `./Dockerfile` (or `./incidentfox-bot/Dockerfile` if in monorepo)
3. **Port**: `8000`

### Step 3: Environment Variables

Add all required environment variables in Coolify UI:

```bash
# Application
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
PORT=8000

# Database (use Coolify PostgreSQL)
DATABASE_URL=postgresql://user:password@postgres:5432/incidentfox

# GitHub App
GITHUB_APP_ID=<your_app_id>
GITHUB_APP_PRIVATE_KEY_PATH=/app/keys/private-key.pem
GITHUB_WEBHOOK_SECRET=<your_webhook_secret>

# Coolify
COOLIFY_API_URL=https://your-coolify-instance.com
COOLIFY_API_TOKEN=<your_coolify_api_token>
COOLIFY_WEBHOOK_SECRET=<optional_coolify_webhook_secret>

# LLM APIs
OPENAI_API_KEY=<your_openai_key>
ANTHROPIC_API_KEY=<your_anthropic_key>

# Feature Flags
ENABLE_AUTO_FIX=false
ENABLE_ANTHROPIC=true
MAX_PATCH_FILES=5

# Security
ALLOWED_FILE_PATTERNS=Dockerfile,docker-compose*.yml,.env.example,package*.json,requirements*.txt,*.config.js,*.config.ts,tsconfig.json,Makefile
```

**Mark as secrets**: `DATABASE_URL`, `GITHUB_WEBHOOK_SECRET`, `COOLIFY_API_TOKEN`, `COOLIFY_WEBHOOK_SECRET`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`

### Step 4: Add Private Key

**Option A: Use Coolify File Storage**

1. In Coolify, go to **Storage** → **Add File**
2. Upload your `private-key.pem`
3. Mount it in your container:
   - Source: `/path/to/private-key.pem`
   - Destination: `/app/keys/private-key.pem`

**Option B: Use Secret in Environment**

```bash
# Not recommended, but possible for testing
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nMIIEp...\n-----END RSA PRIVATE KEY-----"
```

Then modify code to read from env var instead of file.

### Step 5: Configure Webhooks

1. **GitHub App Webhook**: Set to `https://your-incidentfox-domain.com/webhooks/github`
2. **Coolify Webhooks**: Configure in Coolify application settings:
   - Webhook URL: `https://your-incidentfox-domain.com/webhooks/coolify`
   - Events: `deployment.started`, `deployment.success`, `deployment.failed`

### Step 6: Deploy

Click **Deploy** in Coolify.

### Step 7: Verify

```bash
curl https://your-incidentfox-domain.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T10:30:00Z",
  "checks": {
    "database": "ok",
    "github": "ok",
    "coolify": "ok",
    "llm": "ok"
  }
}
```

---

## Docker Compose Deployment

### Prerequisites

- Docker and Docker Compose installed
- Domain with SSL certificate (or reverse proxy)

### Step 1: Clone Repository

```bash
git clone https://github.com/your-org/incidentfox-bot.git
cd incidentfox-bot
```

### Step 2: Configure Environment

```bash
cp .env.example .env
# Edit .env with your values
nano .env
```

### Step 3: Add Private Key

```bash
# Copy your GitHub App private key
cp ~/Downloads/your-app-private-key.pem ./private-key.pem
chmod 600 private-key.pem
```

### Step 4: Start Services

```bash
docker-compose up -d
```

### Step 5: Check Logs

```bash
docker-compose logs -f incidentfox
```

### Step 6: Configure Reverse Proxy

**Using Nginx**:

```nginx
server {
    listen 443 ssl http2;
    server_name incidentfox.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Using Caddy**:

```
incidentfox.yourdomain.com {
    reverse_proxy localhost:8000
}
```

---

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (v1.24+)
- `kubectl` configured
- Helm 3 (optional)

### Step 1: Create Namespace

```bash
kubectl create namespace incidentfox
```

### Step 2: Create Secrets

```bash
# GitHub App private key
kubectl create secret generic github-app-key \
  --from-file=private-key.pem=./private-key.pem \
  -n incidentfox

# Application secrets
kubectl create secret generic incidentfox-secrets \
  --from-literal=database-url="postgresql://..." \
  --from-literal=github-webhook-secret="..." \
  --from-literal=coolify-api-token="..." \
  --from-literal=openai-api-key="..." \
  --from-literal=anthropic-api-key="..." \
  -n incidentfox
```

### Step 3: Create ConfigMap

```bash
kubectl create configmap incidentfox-config \
  --from-literal=environment=production \
  --from-literal=log-level=INFO \
  --from-literal=github-app-id="123456" \
  --from-literal=coolify-api-url="https://..." \
  -n incidentfox
```

### Step 4: Deploy Application

Create `deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: incidentfox
  namespace: incidentfox
spec:
  replicas: 2
  selector:
    matchLabels:
      app: incidentfox
  template:
    metadata:
      labels:
        app: incidentfox
    spec:
      containers:
      - name: incidentfox
        image: your-registry/incidentfox:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          valueFrom:
            configMapKeyRef:
              name: incidentfox-config
              key: environment
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: incidentfox-secrets
              key: database-url
        # ... (add all other env vars)
        volumeMounts:
        - name: github-key
          mountPath: /app/keys
          readOnly: true
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
      volumes:
      - name: github-key
        secret:
          secretName: github-app-key
---
apiVersion: v1
kind: Service
metadata:
  name: incidentfox
  namespace: incidentfox
spec:
  selector:
    app: incidentfox
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: incidentfox
  namespace: incidentfox
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  rules:
  - host: incidentfox.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: incidentfox
            port:
              number: 80
  tls:
  - hosts:
    - incidentfox.yourdomain.com
    secretName: incidentfox-tls
```

Apply:

```bash
kubectl apply -f deployment.yaml
```

---

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `GITHUB_APP_ID` | GitHub App ID | `123456` |
| `GITHUB_APP_PRIVATE_KEY_PATH` | Path to private key | `/app/keys/private-key.pem` |
| `GITHUB_WEBHOOK_SECRET` | Webhook secret | `abc123...` |
| `COOLIFY_API_URL` | Coolify instance URL | `https://coolify.example.com` |
| `COOLIFY_API_TOKEN` | Coolify API token | `token_xyz...` |
| `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` | LLM API key | `sk-...` |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Environment name |
| `DEBUG` | `false` | Debug mode |
| `LOG_LEVEL` | `INFO` | Log level |
| `DATABASE_URL` | `sqlite:///./incidentfox.db` | Database connection |
| `ENABLE_AUTO_FIX` | `false` | Allow auto fixes |
| `MAX_PATCH_FILES` | `5` | Max files per patch |

---

## Database Setup

### PostgreSQL (Recommended for Production)

**Create Database**:

```sql
CREATE DATABASE incidentfox;
CREATE USER incidentfox_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE incidentfox TO incidentfox_user;
```

**Connection String**:

```
postgresql://incidentfox_user:secure_password@localhost:5432/incidentfox
```

**Migrations** (run on first deploy):

```bash
# Migrations are automatic via SQLAlchemy create_all()
# Or use Alembic for production:
alembic upgrade head
```

### SQLite (Development Only)

```bash
# Automatically created on first run
DATABASE_URL=sqlite:///./incidentfox.db
```

---

## Monitoring & Observability

### Health Checks

```bash
# Basic health
curl https://your-domain.com/health

# Detailed metrics (add Prometheus exporter)
curl https://your-domain.com/metrics
```

### Logging

IncidentFox uses structured JSON logging in production:

```json
{
  "timestamp": "2025-01-15T10:30:00Z",
  "level": "info",
  "event": "analysis_complete",
  "category": "env_var_missing",
  "confidence": 95,
  "pr_number": 42
}
```

**Aggregate logs** using:
- Loki + Grafana
- ELK Stack (Elasticsearch, Logstash, Kibana)
- CloudWatch / Datadog / New Relic

### Alerts

Set up alerts for:

- **High error rate**: `level="error"`
- **Webhook signature failures**: `event="webhook_signature_verification_failed"`
- **LLM API failures**: `event="llm_analysis_failed"`
- **Database connection issues**: Check health endpoint

### Metrics to Track

- Deployments analyzed (total, by category)
- Analysis latency (p50, p95, p99)
- Fix application success rate
- LLM token usage (cost tracking)
- Webhook delivery failures

---

## Scaling Considerations

### Horizontal Scaling

IncidentFox is stateless (aside from database), so you can run multiple replicas:

```yaml
replicas: 3
```

### Database Connection Pooling

For high load, tune connection pool:

```python
# In database.py
engine = create_engine(
    settings.database_url,
    pool_size=20,  # Increase for more concurrent requests
    max_overflow=40,
    pool_pre_ping=True
)
```

### Background Task Processing

For very high load, consider adding a task queue:

- **Celery** with Redis backend
- **RQ (Redis Queue)**
- **Kafka** for event streaming

---

## Troubleshooting

### Common Issues

**1. Webhooks not received**

- Check webhook URL is publicly accessible
- Verify SSL certificate is valid
- Check firewall rules

**2. Database connection errors**

```bash
# Test database connectivity
docker-compose exec incidentfox python -c "from src.database import engine; engine.connect()"
```

**3. LLM API rate limits**

- Add retry logic (already implemented via `tenacity`)
- Implement caching for repeated failures
- Use exponential backoff

**4. Memory issues**

```bash
# Monitor memory usage
docker stats incidentfox

# Increase memory limit
docker-compose.yml:
  services:
    incidentfox:
      mem_limit: 2g
```

---

## Security Checklist

- [ ] Webhook secrets configured and verified
- [ ] Private key has 600 permissions
- [ ] Database uses strong password
- [ ] All secrets stored securely (not in code)
- [ ] HTTPS enabled with valid certificate
- [ ] File whitelist configured properly
- [ ] Rate limiting enabled (reverse proxy)
- [ ] Regular security updates applied

---

## Backup & Disaster Recovery

### Database Backups

```bash
# PostgreSQL backup
pg_dump incidentfox > backup_$(date +%Y%m%d).sql

# Automated daily backups
0 2 * * * /usr/bin/pg_dump incidentfox > /backups/incidentfox_$(date +\%Y\%m\%d).sql
```

### Configuration Backups

- Store `.env` in secure vault (1Password, HashiCorp Vault)
- Keep GitHub App credentials in safe location
- Document all environment-specific configurations

---

## Support

For deployment issues:

1. Check logs: `docker-compose logs -f incidentfox`
2. Verify health endpoint: `curl https://your-domain/health`
3. Review [GitHub App Setup](./GITHUB_APP_SETUP.md)
4. Open an issue with logs (redact secrets!)
