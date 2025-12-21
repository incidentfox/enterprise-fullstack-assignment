# IncidentFox Architecture

This document provides a comprehensive overview of IncidentFox's architecture, design decisions, and system components.

## Table of Contents

- [System Overview](#system-overview)
- [Component Architecture](#component-architecture)
- [Data Flow](#data-flow)
- [Database Schema](#database-schema)
- [Failure Analysis Pipeline](#failure-analysis-pipeline)
- [Security Architecture](#security-architecture)
- [Design Decisions](#design-decisions)

---

## System Overview

IncidentFox is a production-grade AI SRE system that integrates with GitHub and Coolify to automatically detect, diagnose, and remediate deployment failures.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         External Systems                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│   │   GitHub     │     │   Coolify    │     │  LLM APIs    │   │
│   │   (Webhooks) │────▶│  (Webhooks)  │────▶│ (OpenAI/     │   │
│   │              │     │   + API      │     │  Anthropic)  │   │
│   └──────────────┘     └──────────────┘     └──────────────┘   │
│           │                    │                     │           │
└───────────┼────────────────────┼─────────────────────┼───────────┘
            │                    │                     │
            ▼                    ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                        IncidentFox Core                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │              FastAPI Application Layer                    │  │
│   │  ┌────────────────┐  ┌────────────────┐                  │  │
│   │  │  GitHub        │  │  Coolify       │                  │  │
│   │  │  Webhook       │  │  Webhook       │                  │  │
│   │  │  Handler       │  │  Handler       │                  │  │
│   │  └────────┬───────┘  └────────┬───────┘                  │  │
│   │           │                   │                           │  │
│   │           └───────────┬───────┘                           │  │
│   │                       ▼                                   │  │
│   │           ┌───────────────────────┐                       │  │
│   │           │   Event Processor     │                       │  │
│   │           └───────────┬───────────┘                       │  │
│   └───────────────────────┼───────────────────────────────────┘  │
│                           │                                       │
│   ┌───────────────────────▼───────────────────────────────────┐  │
│   │                 Business Logic Layer                       │  │
│   │                                                             │  │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │  │
│   │  │   Analysis   │  │    Patch     │  │   Comment    │    │  │
│   │  │    Engine    │◀─│  Generator   │◀─│   Manager    │    │  │
│   │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │  │
│   │         │                  │                  │            │  │
│   │         ├──────────────────┴──────────────────┤            │  │
│   │         ▼                                     ▼            │  │
│   │  ┌──────────────┐                    ┌──────────────┐    │  │
│   │  │  Deterministic│                    │   GitHub     │    │  │
│   │  │  Patterns     │                    │   Client     │    │  │
│   │  └───────────────┘                    └──────────────┘    │  │
│   │         │                                                  │  │
│   │         ▼                                                  │  │
│   │  ┌──────────────┐                                         │  │
│   │  │  LLM Client  │                                         │  │
│   │  │  (OpenAI/    │                                         │  │
│   │  │  Anthropic)  │                                         │  │
│   │  └──────────────┘                                         │  │
│   └─────────────────────────────────────────────────────────────┘  │
│                           │                                       │
│   ┌───────────────────────▼───────────────────────────────────┐  │
│   │                  Data Access Layer                         │  │
│   │                                                             │  │
│   │  ┌──────────────────────────────────────────────────────┐ │  │
│   │  │            SQLAlchemy ORM + PostgreSQL               │ │  │
│   │  │                                                       │ │  │
│   │  │  • pull_requests    • deployments                    │ │  │
│   │  │  • analyses         • actions                        │ │  │
│   │  │  • pr_comments                                       │ │  │
│   │  └──────────────────────────────────────────────────────┘ │  │
│   └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. FastAPI Application (`main.py`)

**Responsibilities**:
- Handle incoming webhooks from GitHub and Coolify
- Route events to appropriate handlers
- Manage application lifecycle (startup, shutdown)
- Provide health check endpoints

**Key Endpoints**:
- `GET /` - Root health check
- `GET /health` - Detailed health status
- `POST /webhooks/github` - GitHub webhook receiver
- `POST /webhooks/coolify` - Coolify webhook receiver

**Design Pattern**: Event-driven architecture with background task processing

### 2. GitHub Client (`github_client.py`)

**Responsibilities**:
- Authenticate as GitHub App using JWT + installation tokens
- Verify webhook signatures (HMAC-SHA256)
- Perform GitHub API operations:
  - Post/update PR comments
  - Commit file changes
  - Read repository contents

**Authentication Flow**:
```
1. Generate JWT from App ID + Private Key
2. Exchange JWT for Installation Access Token
3. Use Installation Token for API calls (valid 1 hour)
4. Refresh token as needed
```

**Security**: All webhook payloads verified before processing

### 3. Coolify Client (`coolify_client.py`)

**Responsibilities**:
- Interact with Coolify API (authenticated via Bearer token)
- Fetch deployment logs and status
- Trigger new deployments
- Verify webhook signatures

**Features**:
- Automatic retry with exponential backoff (`tenacity`)
- Async HTTP client (`httpx`)
- Structured error logging

### 4. Analysis Engine (`analyzer.py`)

**Two-Stage Analysis**:

#### Stage 1: Deterministic Pattern Matching

Uses regex patterns to detect known failure modes:

```python
FAILURE_PATTERNS = [
    FailurePattern(
        category=FailureCategory.ENV_VAR_MISSING,
        pattern=r"environment variable.*?(not set|missing)",
        confidence=95
    ),
    # ... more patterns
]
```

**Advantages**:
- Fast (milliseconds)
- High confidence for known patterns
- No API costs
- Deterministic results

#### Stage 2: LLM-Powered Analysis

If patterns match OR no clear pattern found:

1. **Extract Evidence**: Context around matched patterns
2. **Truncate Logs**: Keep last 5000 chars (most recent errors)
3. **Generate Prompt**: Include category, evidence, logs
4. **LLM Analysis**: Claude 3.5 Sonnet or GPT-4 Turbo
5. **Parse Response**: Extract summary, root cause, recommendations

**LLM Prompt Structure**:
```
You are an expert SRE analyzing a failed deployment.

**Failure Category Detected:** env_var_missing

**Evidence from Logs:**
[matched patterns with context]

**Recent Logs:**
[last 5000 chars]

Provide:
1. Summary: One sentence
2. Root Cause: Detailed explanation
3. Recommendations: 3-5 actionable steps
```

**Token Usage Tracking**: All prompts/completions logged for cost analysis

### 5. Patch Generator (`patch_generator.py`)

**Safe Patch Generation**:

1. **File Whitelist**: Only touch approved file types
2. **Template-Based**: No arbitrary code generation
3. **Evidence-Driven**: Extract vars/ports/packages from logs
4. **Safety Validation**: Multiple checks before applying

**Supported Patch Types**:

| Failure Category | Auto-Fix Approach |
|------------------|-------------------|
| `env_var_missing` | Add to `docker-compose.yml` + `.env.example` with placeholders |
| `port_mismatch` | Document required changes (too risky to auto-fix) |
| `dependency_error` | Document missing packages (version unknown) |
| Others | Manual intervention required |

**File Whitelist** (configurable):
- `Dockerfile`
- `docker-compose*.yml`
- `.env.example`
- `package*.json`
- `requirements*.txt`
- Config files (`*.config.js`, `tsconfig.json`)

**Security**: Never executes arbitrary code, only template-based text replacements

### 6. Comment Formatter (`comment_formatter.py`)

**Responsibilities**:
- Format analysis results as rich Markdown
- Create interactive command menus
- Support collapsible sections for evidence
- Include deployment metadata

**Comment Types**:
1. **Analysis Comment**: Full failure diagnosis
2. **Action Result Comment**: Result of user commands
3. **Success Comment**: Deployment success notification
4. **Logs Comment**: Raw log display

**Features**:
- Sticky comments (update same comment, don't spam)
- HTML markers for identifying bot comments: `<!-- incidentfox-analysis -->`
- Emoji-rich formatting for readability
- Expandable/collapsible sections

---

## Data Flow

### Scenario 1: Deployment Failure

```
1. Developer pushes commit to PR
   │
   ▼
2. Coolify triggers deployment
   │
   ▼
3. Deployment fails
   │
   ▼
4. Coolify sends webhook → IncidentFox
   │  (POST /webhooks/coolify)
   │  Payload: { type: "deployment.failed", deployment_uuid: "...", ... }
   │
   ▼
5. IncidentFox verifies webhook signature
   │
   ▼
6. Create/update Deployment record in DB
   │  Status: FAILED
   │
   ▼
7. Fetch deployment logs from Coolify API
   │
   ▼
8. Run analysis:
   │  a. Pattern matching (deterministic)
   │  b. Classify failure category
   │  c. LLM analysis (if needed)
   │
   ▼
9. Store Analysis record in DB
   │  - Category, confidence, evidence
   │  - Root cause, recommendations
   │  - LLM metadata (tokens, model)
   │
   ▼
10. Format PR comment with results
    │
    ▼
11. Post/update comment on PR
    │
    ▼
12. Developer sees analysis in PR
```

### Scenario 2: User Applies Fix

```
1. Developer comments: "/incidentfox apply fix"
   │
   ▼
2. GitHub sends webhook → IncidentFox
   │  (POST /webhooks/github)
   │  Event: issue_comment.created
   │
   ▼
3. Parse command: "apply fix"
   │
   ▼
4. Find latest failed deployment for PR
   │
   ▼
5. Fetch associated analysis
   │
   ▼
6. Fetch repository files (docker-compose.yml, etc.)
   │
   ▼
7. Generate patch based on failure category
   │  - Extract missing env vars from evidence
   │  - Create patched versions of files
   │  - Validate against whitelist
   │
   ▼
8. Safety checks:
   │  - File count <= MAX_PATCH_FILES
   │  - All files in whitelist
   │  - No dangerous operations
   │
   ▼
9. Commit changes to PR branch
   │  via GitHub API (Contents API)
   │
   ▼
10. Record Action in DB
    │  - Type: APPLY_FIX
    │  - Files modified
    │  - Commit SHA
    │
    ▼
11. Post result comment to PR
    │
    ▼
12. New commit triggers redeploy (Coolify)
```

---

## Database Schema

### Entity-Relationship Diagram

```
┌─────────────────┐
│  pull_requests  │
│─────────────────│
│ • id (PK)       │
│ • repo_owner    │◀────┐
│ • repo_name     │     │
│ • pr_number     │     │
│ • branch_name   │     │
│ • head_sha      │     │
│ • author        │     │
│ • title         │     │
│ • pr_url        │     │
└─────────────────┘     │
         │              │
         │ 1:N          │
         │              │
         ▼              │
┌─────────────────┐     │
│   deployments   │     │
│─────────────────│     │
│ • id (PK)       │     │
│ • pr_id (FK)    │─────┘
│ • coolify_id    │◀────┐
│ • commit_sha    │     │
│ • status        │     │
│ • logs_url      │     │
│ • full_logs     │     │
│ • started_at    │     │
│ • completed_at  │     │
└─────────────────┘     │
         │              │
         │ 1:N          │
         ├──────────────┤
         │              │
         ▼              │
┌─────────────────┐     │
│    analyses     │     │
│─────────────────│     │
│ • id (PK)       │     │
│ • deployment_id │─────┘
│ • status        │
│ • category      │
│ • summary       │
│ • root_cause    │
│ • evidence      │ (JSON)
│ • recommendations│ (JSON)
│ • confidence    │
│ • llm_provider  │
│ • llm_tokens    │
└─────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────┐
│     actions     │
│─────────────────│
│ • id (PK)       │
│ • deployment_id │
│ • action_type   │
│ • requested_by  │
│ • command_text  │
│ • executed      │
│ • success       │
│ • patch_content │
│ • commit_sha    │
└─────────────────┘
```

### Table Details

#### `pull_requests`

Tracks GitHub pull requests.

```python
class PullRequest(Base):
    id = Column(Integer, primary_key=True)
    repo_owner = Column(String(255), nullable=False, index=True)
    repo_name = Column(String(255), nullable=False, index=True)
    pr_number = Column(Integer, nullable=False, index=True)
    branch_name = Column(String(255), nullable=False)
    head_sha = Column(String(40), nullable=False, index=True)
    author = Column(String(255), nullable=False)
    title = Column(Text, nullable=False)
    pr_url = Column(String(512), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
```

**Indexes**: `repo_owner`, `repo_name`, `pr_number`, `head_sha`

#### `deployments`

Tracks Coolify deployments.

```python
class Deployment(Base):
    id = Column(Integer, primary_key=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id"), index=True)
    coolify_deployment_id = Column(String(255), unique=True, index=True)
    coolify_application_id = Column(String(255), index=True)
    commit_sha = Column(String(40), nullable=False, index=True)
    status = Column(Enum(DeploymentStatus), index=True)
    deployment_url = Column(String(512))
    logs_url = Column(String(512))
    error_message = Column(Text)
    full_logs = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)
```

**Indexes**: `pr_id`, `coolify_deployment_id`, `commit_sha`, `status`

**Status Enum**: `PENDING`, `IN_PROGRESS`, `SUCCESS`, `FAILED`, `CANCELLED`

#### `analyses`

Stores failure analysis results.

```python
class Analysis(Base):
    id = Column(Integer, primary_key=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id"), index=True)
    status = Column(Enum(AnalysisStatus), index=True)
    failure_category = Column(Enum(FailureCategory), index=True)
    summary = Column(Text)
    root_cause = Column(Text)
    evidence = Column(JSON)  # List of matched patterns
    recommendations = Column(JSON)  # List of fix steps
    confidence_score = Column(Integer)  # 0-100
    llm_provider = Column(String(50))
    llm_model = Column(String(100))
    llm_prompt_tokens = Column(Integer)
    llm_completion_tokens = Column(Integer)
    llm_raw_response = Column(Text)
    patterns_matched = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
```

**Categories**: `ENV_VAR_MISSING`, `PORT_MISMATCH`, `DEPENDENCY_ERROR`, `BUILD_FAILURE`, `RUNTIME_CRASH`, `HEALTHCHECK_FAILURE`, `DATABASE_CONNECTION`, `UNKNOWN`

#### `actions`

Logs user commands and actions.

```python
class Action(Base):
    id = Column(Integer, primary_key=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id"), index=True)
    action_type = Column(Enum(ActionType), index=True)
    requested_by = Column(String(255), nullable=False)
    command_text = Column(Text)
    comment_id = Column(String(255))
    executed = Column(Boolean, default=False)
    success = Column(Boolean)
    result_message = Column(Text)
    files_modified = Column(JSON)  # List of file paths
    patch_content = Column(Text)
    commit_sha = Column(String(40))
    created_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime)
```

**Action Types**: `ANALYZE`, `SHOW_LOGS`, `APPLY_FIX`, `RERUN`

---

## Failure Analysis Pipeline

### Stage 1: Log Collection

```python
logs = await coolify_client.get_deployment_logs(deployment_id)
```

### Stage 2: Pattern Detection

```python
matches = []
for pattern in FAILURE_PATTERNS:
    for line in logs.split("\n"):
        if re.search(pattern.pattern, line):
            matches.append((pattern, line))
```

### Stage 3: Classification

```python
category_scores = {}
for pattern, evidence in matches:
    category_scores[pattern.category] += pattern.confidence

best_category = max(category_scores, key=category_scores.get)
```

### Stage 4: LLM Analysis

```python
prompt = f"""
You are an expert SRE analyzing a failed deployment.

**Failure Category Detected:** {category}
**Evidence:** {evidence_summary}
**Logs:** {truncated_logs}

Provide:
1. SUMMARY: <one sentence>
2. ROOT CAUSE: <detailed explanation>
3. RECOMMENDATIONS: <3-5 actionable steps>
"""

response = anthropic_client.messages.create(
    model="claude-3-5-sonnet-20241022",
    messages=[{"role": "user", "content": prompt}]
)
```

### Stage 5: Result Formatting

```python
result = AnalysisResult(
    category=category,
    confidence=confidence,
    summary=summary,
    root_cause=root_cause,
    evidence=evidence,
    recommendations=recommendations
)
```

---

## Security Architecture

### 1. Webhook Verification

**GitHub Webhooks**:
```python
expected = hmac.new(secret, payload, sha256).hexdigest()
valid = hmac.compare_digest(signature, expected)
```

**Coolify Webhooks**:
```python
expected = hmac.new(secret, payload, sha256).hexdigest()
valid = hmac.compare_digest(signature_header, expected)
```

### 2. File Whitelist

Only these file patterns can be modified:
- Configuration files (docker-compose, .env.example)
- Package manifests (package.json, requirements.txt)
- Build configs (Dockerfile, tsconfig.json)

**Never allowed**:
- Source code (`.js`, `.py`, `.ts`, `.go`)
- Scripts (`.sh`, `.bash`)
- Secrets (`.env`, `.pem`, `.key`)

### 3. Audit Trail

Every action logged with:
- Who requested it
- What files were modified
- When it happened
- What was the result

### 4. Rate Limiting

Implement at reverse proxy level:
```nginx
limit_req_zone $binary_remote_addr zone=webhooks:10m rate=10r/s;

location /webhooks/ {
    limit_req zone=webhooks burst=20;
}
```

### 5. Secret Management

- Private keys stored with 600 permissions
- Environment variables for secrets (never hardcoded)
- Secrets marked in Coolify/K8s
- No secrets in logs (structured logging filters)

---

## Design Decisions

### Why FastAPI?

- **Async support**: Critical for webhook handling and external API calls
- **Type safety**: Pydantic models prevent runtime errors
- **Auto documentation**: OpenAPI spec generated automatically
- **Performance**: One of the fastest Python frameworks
- **Modern**: Built for Python 3.7+

### Why PostgreSQL?

- **ACID compliance**: Critical for financial/audit data
- **JSON support**: Store evidence and recommendations as JSON
- **Mature ecosystem**: Well-supported, battle-tested
- **Scalability**: Handles high write throughput

### Why SQLAlchemy ORM?

- **Type safety**: MyPy support
- **Migration support**: Alembic integration
- **Query builder**: Prevents SQL injection
- **Relationship management**: Automatic joins, cascades

### Why Two LLM Providers?

- **Fallback**: If one is down, use the other
- **Cost optimization**: Use cheaper model for simple cases
- **A/B testing**: Compare quality across providers
- **Anthropic Claude**: Better at reasoning, fewer hallucinations
- **OpenAI GPT-4**: Faster, lower latency

### Why Deterministic + LLM Hybrid?

**Deterministic First**:
- Fast (no API calls)
- Free (no costs)
- Reliable (known patterns)
- High confidence

**LLM Second**:
- Handles unknown failures
- Better explanations
- Actionable recommendations
- Adapts to new failure modes

---

## Future Enhancements

1. **Machine Learning**: Train model on historical failures
2. **Multi-Language Support**: Comments in user's language
3. **Slack/Discord Integration**: Notify on failures
4. **Cost Analytics Dashboard**: Track LLM usage and costs
5. **Auto-Fix Learning**: Learn from successful fixes
6. **Prometheus Metrics**: Detailed observability
7. **GitHub Actions Integration**: Broader CI/CD support

---

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [PyGithub Documentation](https://pygithub.readthedocs.io/)
- [Coolify API Documentation](https://coolify.io/docs/api)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [OpenAI API](https://platform.openai.com/docs/)
