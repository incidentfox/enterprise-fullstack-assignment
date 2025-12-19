"""IncidentFox FastAPI application."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .analyzer import FailureAnalyzer
from .comment_formatter import (
    format_analysis_comment,
    format_action_result_comment,
    format_logs_comment,
    format_success_comment
)
from .config import settings
from .coolify_client import coolify_client
from .database import get_db, init_db
from .github_client import github_client
from .logging_config import configure_logging, get_logger
from .models import (
    Action,
    ActionType,
    Analysis,
    AnalysisStatus,
    Deployment,
    DeploymentStatus,
    FailureCategory,
    PRComment,
    PullRequest,
)

# Configure logging
configure_logging()
logger = get_logger(__name__)

# Initialize analyzer with GitHub client for repo access
analyzer = FailureAnalyzer(github_client=github_client)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("starting_incidentfox", environment=settings.environment)

    # Initialize database
    init_db()
    logger.info("database_initialized")

    yield

    # Cleanup
    await coolify_client.close()
    logger.info("incidentfox_stopped")


# Create FastAPI app
app = FastAPI(
    title="IncidentFox",
    description="AI SRE for GitHub Pull Requests",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "IncidentFox",
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.environment
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": "ok",
            "github": "ok" if github_client else "unconfigured",
            "coolify": "ok" if coolify_client else "unconfigured",
            "llm": "ok" if analyzer else "unconfigured"
        }
    }


@app.post("/webhooks/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Handle GitHub webhooks."""
    # Verify signature
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not github_client.verify_webhook_signature(body, signature):
        logger.warning("github_webhook_signature_verification_failed")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    payload = await request.json()
    event_type = request.headers.get("X-GitHub-Event", "")

    logger.info("github_webhook_received", event_type=event_type)

    # Route to appropriate handler
    if event_type == "pull_request":
        background_tasks.add_task(handle_pull_request_event, payload, db)
    elif event_type == "issue_comment":
        background_tasks.add_task(handle_issue_comment_event, payload, db)
    else:
        logger.debug("github_webhook_event_ignored", event=event_type)

    return {"status": "accepted"}


@app.post("/webhooks/coolify")
async def coolify_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Handle Coolify webhooks."""
    # Verify signature (if configured)
    body = await request.body()
    signature = request.headers.get("X-Signature", "")

    if settings.coolify_webhook_secret:
        if not coolify_client.verify_webhook_signature(body, signature):
            logger.warning("coolify_webhook_signature_verification_failed")
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    payload = await request.json()
    event_type = payload.get("event", "")

    logger.info("coolify_webhook_received", event_type=event_type, payload_keys=list(payload.keys()))

    # Route to appropriate handler based on event type
    # Note: Coolify uses underscores in event names, not dots
    if event_type in ["deployment_failed", "deployment_success", "deployment_started",
                      "deployment.failed", "deployment.success", "deployment.started"]:
        background_tasks.add_task(handle_coolify_deployment_event, payload, db)
    elif event_type in ["container_status_changed", "container.status_changed"]:
        background_tasks.add_task(handle_container_status_event, payload, db)
    elif event_type in ["server_disk_usage", "server.disk_usage"]:
        background_tasks.add_task(handle_server_disk_usage_event, payload, db)
    elif event_type in ["server_unreachable", "server.unreachable"]:
        background_tasks.add_task(handle_server_unreachable_event, payload, db)
    elif event_type in ["test", "ping"]:
        logger.info("coolify_test_webhook_acknowledged")
    else:
        logger.debug("coolify_webhook_event_ignored", event_type=event_type)

    return {"status": "accepted"}


async def handle_pull_request_event(payload: Dict, db: Session):
    """Handle pull_request webhook events."""
    action = payload.get("action")
    pr_data = payload.get("pull_request", {})
    repo_data = payload.get("repository", {})
    installation_id = payload.get("installation", {}).get("id")

    logger.info(
        "handling_pull_request_event",
        action=action,
        pr_number=pr_data.get("number"),
        repo=repo_data.get("full_name")
    )

    # Only track opened, reopened, and synchronize (new commits)
    if action not in ["opened", "reopened", "synchronize"]:
        return

    # Create or update PR record
    repo_owner = repo_data.get("owner", {}).get("login")
    repo_name = repo_data.get("name")
    pr_number = pr_data.get("number")

    pr = db.query(PullRequest).filter_by(
        repo_owner=repo_owner,
        repo_name=repo_name,
        pr_number=pr_number
    ).first()

    if not pr:
        pr = PullRequest(
            repo_owner=repo_owner,
            repo_name=repo_name,
            pr_number=pr_number,
            branch_name=pr_data.get("head", {}).get("ref"),
            head_sha=pr_data.get("head", {}).get("sha"),
            author=pr_data.get("user", {}).get("login"),
            title=pr_data.get("title"),
            pr_url=pr_data.get("html_url")
        )
        db.add(pr)
    else:
        pr.head_sha = pr_data.get("head", {}).get("sha")
        pr.updated_at = datetime.utcnow()

    db.commit()

    logger.info("pull_request_tracked", pr_id=pr.id, pr_number=pr_number)


async def handle_issue_comment_event(payload: Dict, db: Session):
    """Handle issue_comment webhook events (PR commands and keywords)."""
    action = payload.get("action")
    if action != "created":
        return

    comment_data = payload.get("comment", {})
    issue_data = payload.get("issue", {})
    repo_data = payload.get("repository", {})
    installation_id = payload.get("installation", {}).get("id")

    # Only handle PR comments
    if "pull_request" not in issue_data:
        return

    comment_body = comment_data.get("body", "").strip()
    comment_author = comment_data.get("user", {}).get("login")

    repo_owner = repo_data.get("owner", {}).get("login")
    repo_name = repo_data.get("name")
    pr_number = issue_data.get("number")

    # Ignore bot's own comments
    if comment_author and comment_author.endswith("[bot]"):
        return

    # Find PR in database
    pr = db.query(PullRequest).filter_by(
        repo_owner=repo_owner,
        repo_name=repo_name,
        pr_number=pr_number
    ).first()

    if not pr:
        logger.warning("pr_not_found_for_comment", pr_number=pr_number)
        return

    # Check for simple keyword approval (exact match or standalone word)
    # Only trigger on short, simple comments to avoid false positives
    comment_lower = comment_body.lower().strip()

    # Exact match keywords
    approval_keywords = ["fix", "approve", "lgtm", "apply", "autofix", "apply fix"]

    if comment_lower in approval_keywords:
        logger.info(
            "keyword_approval_detected",
            keyword=comment_lower,
            author=comment_author,
            pr=pr_number
        )

        # Post acknowledgment
        github_client.post_pr_comment(
            installation_id,
            pr.repo_owner,
            pr.repo_name,
            pr.pr_number,
            f"✅ @{comment_author} approved! Generating and applying fix automatically..."
        )

        # Trigger automatic fix
        await handle_apply_fix_command(installation_id, pr, comment_author, db)
        return

    # Check for IncidentFox slash commands (legacy support)
    if not comment_body.startswith("/incidentfox"):
        return

    logger.info(
        "incidentfox_command_received",
        command=comment_body,
        author=comment_author,
        pr=issue_data.get("number")
    )

    # Parse command
    parts = comment_body.split()
    if len(parts) < 2:
        return

    command = parts[1].lower()

    # Route to command handler
    if command == "apply" and len(parts) > 2 and parts[2].lower() == "fix":
        await handle_apply_fix_command(installation_id, pr, comment_author, db)
    elif command == "show" and len(parts) > 2 and parts[2].lower() == "logs":
        await handle_show_logs_command(installation_id, pr, db)
    elif command == "rerun":
        await handle_rerun_command(installation_id, pr, db)
    else:
        logger.warning("unknown_incidentfox_command", command=command)


async def handle_coolify_deployment_event(payload: Dict, db: Session):
    """Handle Coolify deployment events."""
    deployment_id = payload.get("deployment_uuid")
    application_id = payload.get("application_uuid")
    status = payload.get("status", "unknown")
    commit_sha = payload.get("commit_sha")

    logger.info(
        "handling_coolify_deployment_event",
        deployment_id=deployment_id,
        status=status,
        has_commit_sha=bool(commit_sha)
    )

    # If webhook doesn't include commit_sha, fetch deployment details from Coolify API
    if not commit_sha and deployment_id:
        logger.info("fetching_deployment_details_from_coolify", deployment_id=deployment_id)
        try:
            deployment_details = await coolify_client.get_deployment(deployment_id)
            if deployment_details:
                commit_sha = deployment_details.get("commit_sha") or deployment_details.get("commit")
                logger.info("commit_sha_fetched_from_api", commit_sha=commit_sha)
        except Exception as e:
            logger.error("failed_to_fetch_deployment_details", error=str(e))

    # Map status (support both underscore and dot notation)
    status_map = {
        "deployment_started": DeploymentStatus.IN_PROGRESS,
        "deployment_success": DeploymentStatus.SUCCESS,
        "deployment_failed": DeploymentStatus.FAILED,
        "deployment.started": DeploymentStatus.IN_PROGRESS,
        "deployment.success": DeploymentStatus.SUCCESS,
        "deployment.failed": DeploymentStatus.FAILED,
    }
    deployment_status = status_map.get(payload.get("event", payload.get("type")), DeploymentStatus.PENDING)

    # Find or create deployment
    deployment = db.query(Deployment).filter_by(
        coolify_deployment_id=deployment_id
    ).first()

    if not deployment:
        # Try to find PR by commit SHA
        pr = None
        if commit_sha:
            pr = db.query(PullRequest).filter_by(head_sha=commit_sha).first()

        # Fallback: If no commit_sha or PR not found, use the most recent PR
        if not pr:
            logger.info("no_commit_sha_in_webhook_using_fallback", application_id=application_id)
            pr = db.query(PullRequest).order_by(PullRequest.updated_at.desc()).first()

            if pr:
                logger.info("using_most_recent_pr_as_fallback", pr_number=pr.pr_number, pr_sha=pr.head_sha)
            else:
                logger.warning("no_pr_found_for_deployment", commit_sha=commit_sha)
                return

        deployment = Deployment(
            pr_id=pr.id,
            coolify_deployment_id=deployment_id,
            coolify_application_id=application_id,
            commit_sha=commit_sha,
            status=deployment_status,
            deployment_url=payload.get("deployment_url"),
            logs_url=payload.get("logs_url"),
            started_at=datetime.utcnow() if deployment_status == DeploymentStatus.IN_PROGRESS else None
        )
        db.add(deployment)
    else:
        # Update existing deployment
        deployment.status = deployment_status

        # Track start time
        if deployment_status == DeploymentStatus.IN_PROGRESS and not deployment.started_at:
            deployment.started_at = datetime.utcnow()

        # Track completion and calculate duration
        if deployment_status in [DeploymentStatus.SUCCESS, DeploymentStatus.FAILED]:
            deployment.completed_at = datetime.utcnow()
            if deployment.started_at:
                duration = (deployment.completed_at - deployment.started_at).seconds
                deployment.duration_seconds = duration

    db.commit()

    # Handle based on status
    if deployment_status == DeploymentStatus.FAILED:
        await analyze_deployment_failure(deployment, db)
    elif deployment_status == DeploymentStatus.SUCCESS:
        await post_success_comment(deployment, db)


async def analyze_deployment_failure(deployment: Deployment, db: Session):
    """Analyze a failed deployment and post results."""
    logger.info("analyzing_deployment_failure", deployment_id=deployment.id)

    pr = deployment.pull_request

    # Create analysis record
    analysis_record = Analysis(
        deployment_id=deployment.id,
        status=AnalysisStatus.IN_PROGRESS
    )
    db.add(analysis_record)
    db.commit()

    # Post immediate "Analyzing..." comment for better UX
    installation_id = settings.github_installation_id
    analyzing_comment = f"""<!-- incidentfox-analysis -->
## 🔍 IncidentFox is Analyzing Deployment Failure

**Deployment:** [`{deployment.coolify_deployment_id[:12]}...`]({deployment.deployment_url})
**Status:** 🔄 Analysis in progress...

I'm fetching logs and analyzing the failure with Claude 4.5 Sonnet. This usually takes 10-30 seconds.

---
*Powered by [IncidentFox](https://github.com/incidentfox) with Claude 4.5 Sonnet*
"""

    try:
        comment_obj = github_client.post_or_update_comment(
            installation_id,
            pr.repo_owner,
            pr.repo_name,
            pr.pr_number,
            analyzing_comment
        )
        logger.info("analyzing_comment_posted", pr_number=pr.pr_number, comment_id=comment_obj.id)
    except Exception as e:
        logger.error("failed_to_post_analyzing_comment", error=str(e))
        # Continue with analysis even if comment fails

    try:
        # Fetch logs from Coolify
        logs = await coolify_client.get_deployment_logs(deployment.coolify_deployment_id)
        if not logs:
            logs = deployment.error_message or "No logs available"

        deployment.full_logs = logs
        db.commit()

        # Get PR branch name for repo access
        try:
            repo = github_client.get_repository(
                installation_id,
                pr.repo_owner,
                pr.repo_name
            )
            gh_pr = repo.get_pull(pr.pr_number)
            branch = gh_pr.head.ref
            logger.info("got_pr_branch_for_analysis", branch=branch)
        except Exception as e:
            logger.warning("failed_to_get_branch_for_analysis", error=str(e))
            branch = None

        # Perform analysis with repo access
        result = await analyzer.analyze(
            logs,
            installation_id=installation_id if branch else None,
            repo_owner=pr.repo_owner if branch else None,
            repo_name=pr.repo_name if branch else None,
            branch=branch
        )

        # Update analysis record
        analysis_record.status = AnalysisStatus.COMPLETED
        analysis_record.failure_category = None  # No longer using pattern-based categorization
        analysis_record.summary = result.summary
        analysis_record.root_cause = result.root_cause
        analysis_record.evidence = None  # No longer using pattern-based evidence
        analysis_record.recommendations = result.recommendations
        analysis_record.confidence_score = None  # No longer using pattern-based confidence
        analysis_record.llm_provider = result.llm_provider
        analysis_record.llm_model = result.llm_model
        analysis_record.llm_prompt_tokens = result.prompt_tokens
        analysis_record.llm_completion_tokens = result.completion_tokens
        analysis_record.completed_at = datetime.utcnow()

        db.commit()

        # Format and post comment
        comment = format_analysis_comment(
            result,
            deployment.coolify_deployment_id,
            deployment.deployment_url,
            deployment.commit_sha
        )

        # Use installation ID from settings
        # TODO: Eventually store installation_id per PR from GitHub webhooks
        installation_id = int(settings.github_installation_id) if hasattr(settings, 'github_installation_id') else None

        if not installation_id:
            logger.error("no_github_installation_id_configured")
            raise ValueError("GitHub installation ID not configured in settings")

        github_client.post_or_update_comment(
            installation_id,
            pr.repo_owner,
            pr.repo_name,
            pr.pr_number,
            comment
        )

        logger.info("analysis_posted_to_pr", pr_number=pr.pr_number, analysis_id=analysis_record.id)

    except Exception as e:
        logger.error("analysis_failed", error=str(e), deployment_id=deployment.id)
        analysis_record.status = AnalysisStatus.FAILED
        db.commit()


async def post_success_comment(deployment: Deployment, db: Session):
    """Post success comment to PR."""
    pr = deployment.pull_request

    comment = format_success_comment(
        deployment.coolify_deployment_id,
        deployment.deployment_url,
        deployment.commit_sha,
        deployment.duration_seconds
    )

    # Use installation ID from settings
    installation_id = settings.github_installation_id

    github_client.post_or_update_comment(
        installation_id,
        pr.repo_owner,
        pr.repo_name,
        pr.pr_number,
        comment
    )

    logger.info("success_comment_posted", pr_number=pr.pr_number)


async def handle_container_status_event(payload: Dict, db: Session):
    """Handle container status change events."""
    container_name = payload.get("container_name", "unknown")
    status = payload.get("status", "unknown")
    deployment_id = payload.get("deployment_uuid")

    logger.info(
        "container_status_changed",
        container=container_name,
        status=status,
        deployment_id=deployment_id
    )

    if not deployment_id:
        return

    # Find deployment and add context
    deployment = db.query(Deployment).filter_by(
        coolify_deployment_id=deployment_id
    ).first()

    if deployment:
        # Append container status to logs for additional context
        context = f"\n[Container Status] {container_name}: {status}"
        if deployment.full_logs:
            deployment.full_logs += context
        else:
            deployment.full_logs = context

        db.commit()
        logger.debug("container_status_context_added", deployment_id=deployment.id)


async def handle_server_disk_usage_event(payload: Dict, db: Session):
    """Handle server disk usage warnings."""
    server_name = payload.get("server_name", "unknown")
    usage_percent = payload.get("usage_percent", 0)

    logger.warning(
        "server_disk_usage_high",
        server=server_name,
        usage=usage_percent
    )

    # Find recent in-progress deployments on this server
    # and add disk usage context if they fail
    deployments = db.query(Deployment).filter_by(
        status=DeploymentStatus.IN_PROGRESS
    ).limit(10).all()

    for deployment in deployments:
        context = f"\n[Server Alert] Disk usage at {usage_percent}% on {server_name}"
        if deployment.full_logs:
            deployment.full_logs += context
        else:
            deployment.full_logs = context

    db.commit()


async def handle_server_unreachable_event(payload: Dict, db: Session):
    """Handle server unreachable events."""
    server_name = payload.get("server_name", "unknown")

    logger.error(
        "server_unreachable",
        server=server_name
    )

    # Find recent in-progress deployments and mark them as likely to fail
    deployments = db.query(Deployment).filter_by(
        status=DeploymentStatus.IN_PROGRESS
    ).limit(10).all()

    for deployment in deployments:
        context = f"\n[Server Alert] Server {server_name} became unreachable"
        if deployment.full_logs:
            deployment.full_logs += context
        else:
            deployment.full_logs = context

    db.commit()


async def handle_apply_fix_command(
    installation_id: int,
    pr: PullRequest,
    author: str,
    db: Session
):
    """Handle /incidentfox apply fix command."""
    logger.info("handling_apply_fix_command", pr_id=pr.id, author=author)

    # Find most recent failed deployment
    deployment = db.query(Deployment).filter_by(
        pr_id=pr.id,
        status=DeploymentStatus.FAILED
    ).order_by(Deployment.started_at.desc()).first()

    if not deployment:
        github_client.post_pr_comment(
            installation_id,
            pr.repo_owner,
            pr.repo_name,
            pr.pr_number,
            "❌ No failed deployment found for this PR."
        )
        return

    # Get analysis
    analysis = db.query(Analysis).filter_by(
        deployment_id=deployment.id,
        status=AnalysisStatus.COMPLETED
    ).first()

    if not analysis:
        github_client.post_pr_comment(
            installation_id,
            pr.repo_owner,
            pr.repo_name,
            pr.pr_number,
            "❌ No analysis found. Please wait for analysis to complete."
        )
        return

    # Post "working on it" message
    working_comment = github_client.post_pr_comment(
        installation_id,
        pr.repo_owner,
        pr.repo_name,
        pr.pr_number,
        "🔧 Analyzing the issue and generating a fix... This may take 30-60 seconds."
    )

    try:
        # Import fix generator
        from .fix_generator import create_fix_generator

        # Create fix generator
        fix_gen = create_fix_generator(github_client)

        # Get deployment logs
        logs = deployment.full_logs or await coolify_client.get_deployment_logs(
            deployment.coolify_deployment_id
        )

        if not logs:
            logs = "No logs available"

        # Get PR branch name from commit SHA
        repo = github_client.get_repository(
            installation_id,
            pr.repo_owner,
            pr.repo_name
        )
        gh_pr = repo.get_pull(pr.pr_number)
        branch = gh_pr.head.ref

        # Generate fix
        logger.info("generating_fix", pr_number=pr.pr_number, branch=branch)

        proposed_fix = await fix_gen.generate_fix(
            installation_id=installation_id,
            repo_owner=pr.repo_owner,
            repo_name=pr.repo_name,
            branch=branch,
            pr_number=pr.pr_number,
            deployment_logs=logs,
            analysis_summary=analysis.summary or "",
            root_cause=analysis.root_cause or ""
        )

        if not proposed_fix:
            github_client.post_pr_comment(
                installation_id,
                pr.repo_owner,
                pr.repo_name,
                pr.pr_number,
                "❌ Unable to generate an automatic fix for this issue. Manual intervention required."
            )
            return

        # Commit the fix
        logger.info("committing_fix", files=list(proposed_fix.file_changes.keys()))

        commit_message = f"""🤖 Fix: {proposed_fix.description}

{proposed_fix.reasoning}

---
Generated by IncidentFox
Confidence: {proposed_fix.confidence}"""

        commit_sha = github_client.commit_file_changes(
            installation_id=installation_id,
            repo_owner=pr.repo_owner,
            repo_name=pr.repo_name,
            branch=branch,
            file_changes=proposed_fix.file_changes,
            commit_message=commit_message
        )

        # Format success message
        confidence_emoji = {
            "high": "🟢",
            "medium": "🟡",
            "low": "🟠"
        }.get(proposed_fix.confidence, "⚪")

        warnings_text = ""
        if proposed_fix.warnings:
            warnings_text = "\n\n**⚠️ Warnings:**\n" + "\n".join([f"- {w}" for w in proposed_fix.warnings])

        files_changed = "\n".join([f"- `{path}`" for path in proposed_fix.file_changes.keys()])

        success_message = f"""✅ **Fix Applied Successfully**

{confidence_emoji} **Confidence:** {proposed_fix.confidence.title()}

**Changes:**
{files_changed}

**Reasoning:**
{proposed_fix.reasoning}
{warnings_text}

**Commit:** [`{commit_sha[:8]}`](https://github.com/{pr.repo_owner}/{pr.repo_name}/commit/{commit_sha})

The fix has been committed to your branch. Coolify should automatically redeploy if you have auto-deployment enabled.

---
*🦊 Powered by IncidentFox with Claude {settings.claude_model}*"""

        github_client.post_pr_comment(
            installation_id,
            pr.repo_owner,
            pr.repo_name,
            pr.pr_number,
            success_message
        )

        logger.info(
            "fix_applied_successfully",
            pr_number=pr.pr_number,
            commit_sha=commit_sha,
            confidence=proposed_fix.confidence
        )

    except Exception as e:
        logger.error("fix_generation_failed", error=str(e), pr_number=pr.pr_number)
        github_client.post_pr_comment(
            installation_id,
            pr.repo_owner,
            pr.repo_name,
            pr.pr_number,
            f"❌ Failed to generate fix: {str(e)}\n\nPlease review the error and try again."
        )
        raise


async def handle_show_logs_command(
    installation_id: int,
    pr: PullRequest,
    db: Session
):
    """Handle /incidentfox show logs command."""
    logger.info("handling_show_logs_command", pr_id=pr.id)

    # Find most recent deployment
    deployment = db.query(Deployment).filter_by(
        pr_id=pr.id
    ).order_by(Deployment.started_at.desc()).first()

    if not deployment:
        github_client.post_pr_comment(
            installation_id,
            pr.repo_owner,
            pr.repo_name,
            pr.pr_number,
            "❌ No deployment found for this PR."
        )
        return

    logs = deployment.full_logs or await coolify_client.get_deployment_logs(
        deployment.coolify_deployment_id
    )

    if not logs:
        github_client.post_pr_comment(
            installation_id,
            pr.repo_owner,
            pr.repo_name,
            pr.pr_number,
            "❌ No logs available for this deployment."
        )
        return

    comment = format_logs_comment(logs, deployment.coolify_deployment_id)

    github_client.post_pr_comment(
        installation_id,
        pr.repo_owner,
        pr.repo_name,
        pr.pr_number,
        comment
    )


async def handle_rerun_command(
    installation_id: int,
    pr: PullRequest,
    db: Session
):
    """Handle /incidentfox rerun command."""
    logger.info("handling_rerun_command", pr_id=pr.id)

    # Find most recent deployment
    deployment = db.query(Deployment).filter_by(
        pr_id=pr.id
    ).order_by(Deployment.started_at.desc()).first()

    if not deployment:
        github_client.post_pr_comment(
            installation_id,
            pr.repo_owner,
            pr.repo_name,
            pr.pr_number,
            "❌ No deployment found for this PR."
        )
        return

    # Trigger new deployment
    new_deployment_id = await coolify_client.trigger_deployment(
        deployment.coolify_application_id,
        pr.branch_name
    )

    if new_deployment_id:
        github_client.post_pr_comment(
            installation_id,
            pr.repo_owner,
            pr.repo_name,
            pr.pr_number,
            f"✅ Triggered new deployment: `{new_deployment_id}`"
        )
    else:
        github_client.post_pr_comment(
            installation_id,
            pr.repo_owner,
            pr.repo_name,
            pr.pr_number,
            "❌ Failed to trigger new deployment."
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
