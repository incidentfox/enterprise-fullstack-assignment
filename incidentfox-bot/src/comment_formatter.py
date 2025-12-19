"""Format PR comments with analysis results and actions."""
from datetime import datetime
from typing import List, Optional

from .analyzer import AnalysisResult
from .models import DeploymentStatus


def format_analysis_comment(
    analysis: AnalysisResult,
    deployment_id: str,
    deployment_url: Optional[str] = None,
    commit_sha: Optional[str] = None
) -> str:
    """Format failure analysis as a PR comment.

    Args:
        analysis: Analysis result
        deployment_id: Deployment ID
        deployment_url: Optional deployment URL
        commit_sha: Optional commit SHA

    Returns:
        Formatted markdown comment
    """
    # Build comment with Claude's markdown directly embedded
    lines = [
        "<!-- incidentfox-analysis -->",
        "",
        "## 🦊 IncidentFox Deployment Analysis",
        "",
        "**Status:** ❌ Deployment Failed",
        "",
        "---",
        "",
        # Claude's markdown analysis goes here directly
        analysis.root_cause,  # This contains the full markdown
        "",
    ]

    # Add action commands
    lines.extend([
        "---",
        "",
        "### 🎯 Quick Actions",
        "",
        "**Reply with `fix`, `approve`, or `lgtm`** to automatically generate and apply a fix",
        "",
        "Other commands:",
        "",
        "- `/incidentfox show logs` - Show detailed deployment logs",
        "- `/incidentfox rerun` - Trigger a new deployment",
        "",
    ])

    # Add metadata footer
    lines.extend([
        "<details>",
        "<summary>Deployment Details</summary>",
        "",
        f"- **Deployment ID:** `{deployment_id}`",
    ])

    if commit_sha:
        lines.append(f"- **Commit:** `{commit_sha[:8]}`")

    if deployment_url:
        lines.append(f"- **URL:** {deployment_url}")

    if analysis.llm_provider and analysis.llm_model:
        lines.append(f"- **Analysis:** {analysis.llm_provider} ({analysis.llm_model})")

    lines.extend([
        f"- **Analyzed:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "</details>",
        "",
        "<sub>🦊 Powered by IncidentFox | [Learn more](https://github.com/your-org/incidentfox)</sub>",
    ])

    return "\n".join(lines)


def format_action_result_comment(
    action_type: str,
    success: bool,
    message: str,
    details: Optional[dict] = None
) -> str:
    """Format action result as a comment.

    Args:
        action_type: Type of action performed
        success: Whether action succeeded
        message: Result message
        details: Optional additional details

    Returns:
        Formatted markdown comment
    """
    status_emoji = "✅" if success else "❌"
    status_text = "Success" if success else "Failed"

    lines = [
        "<!-- incidentfox-action-result -->",
        "",
        f"## {status_emoji} Action Result: {action_type}",
        "",
        f"**Status:** {status_text}",
        "",
        message,
        "",
    ]

    # Add details if provided
    if details:
        lines.extend([
            "<details>",
            "<summary>Details</summary>",
            "",
            "```json",
        ])

        import json
        lines.append(json.dumps(details, indent=2))

        lines.extend([
            "```",
            "</details>",
            "",
        ])

    lines.append(f"<sub>Executed at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</sub>")

    return "\n".join(lines)


def format_success_comment(
    deployment_id: str,
    deployment_url: Optional[str] = None,
    commit_sha: Optional[str] = None,
    duration_seconds: Optional[int] = None
) -> str:
    """Format success message as a PR comment.

    Args:
        deployment_id: Deployment ID
        deployment_url: Optional deployment URL
        commit_sha: Optional commit SHA
        duration_seconds: Optional deployment duration

    Returns:
        Formatted markdown comment
    """
    lines = [
        "<!-- incidentfox-analysis -->",
        "",
        "## ✅ Deployment Successful",
        "",
        f"Your deployment completed successfully!",
        "",
    ]

    if deployment_url:
        lines.extend([
            f"🔗 **Preview URL:** {deployment_url}",
            "",
        ])

    lines.extend([
        "<details>",
        "<summary>Deployment Details</summary>",
        "",
        f"- **Deployment ID:** `{deployment_id}`",
    ])

    if commit_sha:
        lines.append(f"- **Commit:** `{commit_sha[:8]}`")

    if duration_seconds:
        minutes = duration_seconds // 60
        seconds = duration_seconds % 60
        lines.append(f"- **Duration:** {minutes}m {seconds}s")

    lines.extend([
        f"- **Completed:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "</details>",
        "",
        "<sub>🦊 Powered by IncidentFox</sub>",
    ])

    return "\n".join(lines)


def format_logs_comment(logs: str, deployment_id: str, max_lines: int = 100) -> str:
    """Format deployment logs as a comment.

    Args:
        logs: Full deployment logs
        deployment_id: Deployment ID
        max_lines: Maximum lines to include

    Returns:
        Formatted markdown comment
    """
    log_lines = logs.split("\n")
    total_lines = len(log_lines)

    # Get last N lines
    display_lines = log_lines[-max_lines:] if total_lines > max_lines else log_lines

    lines = [
        "<!-- incidentfox-logs -->",
        "",
        f"## 📜 Deployment Logs",
        "",
        f"**Deployment ID:** `{deployment_id}`",
        "",
        f"Showing last {len(display_lines)} of {total_lines} lines:",
        "",
        "```",
    ]

    lines.extend(display_lines)

    lines.extend([
        "```",
        "",
        "<sub>🦊 IncidentFox</sub>",
    ])

    return "\n".join(lines)
