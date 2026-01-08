"""GitHub API client with App authentication."""
import hashlib
import hmac
import time
import zipfile
from io import BytesIO
from typing import Dict, List, Optional

import httpx
import jwt
from github import Github, GithubIntegration, Auth, InputGitTreeElement
from github.PullRequest import PullRequest
from github.Repository import Repository
from github.IssueComment import IssueComment

from .config import settings
from .logging_config import get_logger

logger = get_logger(__name__)


class GitHubClient:
    """GitHub API client with App authentication."""

    def __init__(self):
        """Initialize GitHub client."""
        self.app_id = settings.github_app_id
        self.private_key = settings.github_private_key
        self.webhook_secret = settings.github_webhook_secret

        self.integration = None
        if self.app_id and self.private_key:
            # Create GithubIntegration for App authentication
            self.integration = GithubIntegration(
                self.app_id,
                self.private_key,
            )
            logger.info("github_client_initialized", app_id=self.app_id)
        else:
            logger.warning("github_not_configured", app_id=bool(self.app_id), has_private_key=bool(self.private_key))

    def verify_webhook_signature(self, payload: bytes, signature_header: str) -> bool:
        """Verify GitHub webhook signature.

        Args:
            payload: Raw request body
            signature_header: X-Hub-Signature-256 header value

        Returns:
            True if signature is valid
        """
        # If no webhook secret configured, skip verification (dev mode)
        if not self.webhook_secret:
            logger.warning("github_webhook_secret_not_configured_skipping_verification")
            return True

        if not signature_header:
            logger.warning("webhook_signature_missing")
            return False

        # Extract the signature from header (format: "sha256=<signature>")
        try:
            hash_algorithm, signature = signature_header.split("=", 1)
        except ValueError:
            logger.warning("webhook_signature_invalid_format", header=signature_header)
            return False

        if hash_algorithm != "sha256":
            logger.warning("webhook_signature_wrong_algorithm", algorithm=hash_algorithm)
            return False

        # Compute expected signature
        mac = hmac.new(
            self.webhook_secret.encode(),
            msg=payload,
            digestmod=hashlib.sha256
        )
        expected_signature = mac.hexdigest()

        # Compare signatures (constant-time comparison)
        is_valid = hmac.compare_digest(signature, expected_signature)

        if not is_valid:
            logger.warning("webhook_signature_mismatch")

        return is_valid

    def get_installation_client(self, installation_id: int) -> Github:
        """Get authenticated GitHub client for an installation.

        Args:
            installation_id: GitHub App installation ID

        Returns:
            Authenticated GitHub client
        """
        if not self.integration:
            raise RuntimeError("GitHub App not configured (missing GITHUB_APP_ID / private key).")

        # Get installation access token
        auth = self.integration.get_access_token(installation_id)

        # Create authenticated client
        client = Github(auth.token)

        logger.info(
            "installation_client_created",
            installation_id=installation_id,
            expires_at=auth.expires_at
        )

        return client

    def get_installation_token(self, installation_id: int) -> str:
        """Get an installation access token string for direct REST calls."""
        if not self.integration:
            raise RuntimeError("GitHub App not configured (missing GITHUB_APP_ID / private key).")
        auth = self.integration.get_access_token(installation_id)
        return auth.token

    def download_workflow_run_logs(
        self,
        installation_id: int,
        repo_owner: str,
        repo_name: str,
        run_id: int,
        max_chars: int = 200_000,
    ) -> str:
        """Download GitHub Actions workflow run logs as text.

        Uses GitHub REST API:
          GET /repos/{owner}/{repo}/actions/runs/{run_id}/logs

        Returns concatenated text extracted from the log ZIP.
        """
        token = self.get_installation_token(installation_id)
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/runs/{run_id}/logs"

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }

        try:
            with httpx.Client(follow_redirects=True, timeout=60.0) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                zip_bytes = resp.content
        except Exception as e:
            logger.error(
                "download_workflow_run_logs_failed",
                repo=f"{repo_owner}/{repo_name}",
                run_id=run_id,
                error=str(e),
            )
            return (
                "Unable to download GitHub Actions logs.\n"
                "Common causes:\n"
                "- GitHub App missing Actions permissions (needs Actions: Read)\n"
                "- Workflow logs are expired or unavailable\n"
                f"- Error: {e}"
            )

        try:
            with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
                parts: List[str] = []
                # Prefer text-like files
                names = [n for n in zf.namelist() if not n.endswith("/")]
                for name in names:
                    # Skip very large binary-ish files
                    if not (name.endswith(".txt") or name.endswith(".log") or name.endswith(".json")):
                        continue
                    try:
                        raw = zf.read(name)
                        text = raw.decode("utf-8", errors="replace")
                    except Exception:
                        continue
                    parts.append(f"\n===== {name} =====\n{text}")

                if not parts:
                    # Fallback: include first few files whatever they are
                    for name in names[:10]:
                        try:
                            raw = zf.read(name)
                            text = raw.decode("utf-8", errors="replace")
                        except Exception:
                            continue
                        parts.append(f"\n===== {name} =====\n{text}")

                combined = "\n".join(parts).strip()
                if len(combined) > max_chars:
                    combined = combined[-max_chars:]
                return combined or "No logs found in workflow run ZIP."
        except Exception as e:
            logger.error("workflow_logs_zip_parse_failed", run_id=run_id, error=str(e))
            return f"Downloaded workflow logs but failed to parse ZIP: {e}"

    def get_repository(
        self,
        installation_id: int,
        repo_owner: str,
        repo_name: str
    ) -> Repository:
        """Get repository object.

        Args:
            installation_id: GitHub App installation ID
            repo_owner: Repository owner
            repo_name: Repository name

        Returns:
            GitHub repository object
        """
        client = self.get_installation_client(installation_id)
        repo = client.get_repo(f"{repo_owner}/{repo_name}")

        logger.debug("repository_fetched", repo=f"{repo_owner}/{repo_name}")

        return repo

    def get_pull_request(
        self,
        installation_id: int,
        repo_owner: str,
        repo_name: str,
        pr_number: int
    ) -> PullRequest:
        """Get pull request object.

        Args:
            installation_id: GitHub App installation ID
            repo_owner: Repository owner
            repo_name: Repository name
            pr_number: PR number

        Returns:
            GitHub pull request object
        """
        repo = self.get_repository(installation_id, repo_owner, repo_name)
        pr = repo.get_pull(pr_number)

        logger.debug("pull_request_fetched", pr=f"{repo_owner}/{repo_name}#{pr_number}")

        return pr

    def post_pr_comment(
        self,
        installation_id: int,
        repo_owner: str,
        repo_name: str,
        pr_number: int,
        comment: str
    ) -> IssueComment:
        """Post a comment on a pull request.

        Args:
            installation_id: GitHub App installation ID
            repo_owner: Repository owner
            repo_name: Repository name
            pr_number: PR number
            comment: Comment text (Markdown supported)

        Returns:
            Created comment object
        """
        pr = self.get_pull_request(installation_id, repo_owner, repo_name, pr_number)
        comment_obj = pr.create_issue_comment(comment)

        logger.info(
            "pr_comment_posted",
            pr=f"{repo_owner}/{repo_name}#{pr_number}",
            comment_id=comment_obj.id
        )

        return comment_obj

    def update_pr_comment(
        self,
        installation_id: int,
        repo_owner: str,
        repo_name: str,
        comment_id: int,
        new_body: str,
        pr_number: Optional[int] = None
    ) -> IssueComment:
        """Update an existing PR comment.

        Args:
            installation_id: GitHub App installation ID
            repo_owner: Repository owner
            repo_name: Repository name
            comment_id: Comment ID to update
            new_body: New comment text
            pr_number: Optional PR number (not used, for API compatibility)

        Returns:
            Updated comment object
        """
        try:
            # Get client
            client = self.get_installation_client(installation_id)

            # Use PyGithub's internal request method to fetch comment directly by ID
            # GitHub API: GET /repos/{owner}/{repo}/issues/comments/{comment_id}
            headers, data = client._Github__requester.requestJsonAndCheck(
                "GET",
                f"/repos/{repo_owner}/{repo_name}/issues/comments/{comment_id}"
            )

            # Now update the comment using PATCH
            headers, data = client._Github__requester.requestJsonAndCheck(
                "PATCH",
                f"/repos/{repo_owner}/{repo_name}/issues/comments/{comment_id}",
                input={"body": new_body}
            )

            # Reconstruct IssueComment object from response
            from github.IssueComment import IssueComment
            comment = IssueComment(
                client._Github__requester,
                headers,
                data,
                completed=True
            )

            logger.info(
                "pr_comment_updated",
                repo=f"{repo_owner}/{repo_name}",
                comment_id=comment_id
            )

            return comment

        except Exception as e:
            logger.error(
                "update_comment_failed",
                repo=f"{repo_owner}/{repo_name}",
                comment_id=comment_id,
                error=str(e)
            )
            raise

    def find_bot_comment(
        self,
        installation_id: int,
        repo_owner: str,
        repo_name: str,
        pr_number: int,
        marker: str = "<!-- incidentfox-analysis -->"
    ) -> Optional[IssueComment]:
        """Find existing bot comment with specific marker.

        Args:
            installation_id: GitHub App installation ID
            repo_owner: Repository owner
            repo_name: Repository name
            pr_number: PR number
            marker: HTML comment marker to identify bot comments

        Returns:
            Existing comment if found, None otherwise
        """
        pr = self.get_pull_request(installation_id, repo_owner, repo_name, pr_number)

        # Search through comments for our marker (don't need to check username)
        # The marker is unique enough to identify our comments
        for comment in pr.get_issue_comments():
            if marker in comment.body:
                logger.debug(
                    "bot_comment_found",
                    pr=f"{repo_owner}/{repo_name}#{pr_number}",
                    comment_id=comment.id
                )
                return comment

        logger.debug(
            "bot_comment_not_found",
            pr=f"{repo_owner}/{repo_name}#{pr_number}"
        )
        return None

    def post_or_update_comment(
        self,
        installation_id: int,
        repo_owner: str,
        repo_name: str,
        pr_number: int,
        comment_body: str,
        marker: str = "<!-- incidentfox-analysis -->"
    ) -> IssueComment:
        """Post a new comment or update existing one (sticky comment behavior).

        Args:
            installation_id: GitHub App installation ID
            repo_owner: Repository owner
            repo_name: Repository name
            pr_number: PR number
            comment_body: Comment text (should include marker)
            marker: HTML comment marker to identify bot comments

        Returns:
            Created or updated comment object
        """
        existing = self.find_bot_comment(
            installation_id, repo_owner, repo_name, pr_number, marker
        )

        if existing:
            return self.update_pr_comment(
                installation_id, repo_owner, repo_name, existing.id, comment_body, pr_number=pr_number
            )
        else:
            return self.post_pr_comment(
                installation_id, repo_owner, repo_name, pr_number, comment_body
            )

    def commit_file_changes(
        self,
        installation_id: int,
        repo_owner: str,
        repo_name: str,
        branch: str,
        file_changes: Dict[str, str],
        commit_message: str
    ) -> str:
        """Commit file changes to a branch.

        Args:
            installation_id: GitHub App installation ID
            repo_owner: Repository owner
            repo_name: Repository name
            branch: Branch name
            file_changes: Dict of {file_path: new_content}
            commit_message: Commit message

        Returns:
            Commit SHA
        """
        repo = self.get_repository(installation_id, repo_owner, repo_name)

        # Get current commit SHA
        ref = repo.get_git_ref(f"heads/{branch}")
        current_sha = ref.object.sha

        # Get base tree
        base_tree = repo.get_git_commit(current_sha).tree

        # Create new tree with file changes
        tree_elements = []
        for file_path, content in file_changes.items():
            # Create blob for file content
            blob = repo.create_git_blob(content, "utf-8")
            tree_elements.append(
                InputGitTreeElement(
                    path=file_path,
                    mode="100644",  # Regular file
                    type="blob",
                    sha=blob.sha
                )
            )

        new_tree = repo.create_git_tree(tree_elements, base_tree)

        # Create commit
        new_commit = repo.create_git_commit(
            commit_message,
            new_tree,
            [repo.get_git_commit(current_sha)]
        )

        # Update reference
        ref.edit(new_commit.sha)

        logger.info(
            "files_committed",
            repo=f"{repo_owner}/{repo_name}",
            branch=branch,
            commit_sha=new_commit.sha,
            files_changed=list(file_changes.keys())
        )

        return new_commit.sha


# Global instance
github_client = GitHubClient()
