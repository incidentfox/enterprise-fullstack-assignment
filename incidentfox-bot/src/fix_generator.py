"""Automatic fix generation using Claude AI with tool calling."""
import json
from dataclasses import dataclass
from typing import Dict, List, Optional

import anthropic
from anthropic import APIConnectionError, APIStatusError, RateLimitError
from anthropic.types import TextBlock, ToolUseBlock

from .config import settings
from .github_client import GitHubClient
from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ProposedFix:
    """A proposed fix with file changes."""
    description: str
    file_changes: Dict[str, str]  # {file_path: new_content}
    reasoning: str
    confidence: str  # "high", "medium", "low"
    warnings: List[str]


class FixGenerator:
    """Generate automatic fixes using Claude AI with tool calling."""

    def __init__(self, github_client: GitHubClient):
        """Initialize fix generator.

        Args:
            github_client: GitHub client for repo access
        """
        self.github_client = github_client
        self.anthropic_client = None

        if settings.anthropic_api_key:
            self.anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            logger.info("fix_generator_initialized")
        else:
            logger.warning("anthropic_api_key_not_configured")

    def _define_tools(self) -> List[Dict]:
        """Define tools available to Claude."""
        return [
            {
                "name": "read_file",
                "description": "Read the contents of a file from the repository. Use this to examine source code, configuration files, tests, or any other files that might be relevant to fixing the failure.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "The path to the file relative to the repository root (e.g., 'docker-compose.yaml', 'src/index.js', 'package.json')"
                        }
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "list_directory",
                "description": "List files and directories in a repository directory. Use this to explore the repository structure.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "directory_path": {
                            "type": "string",
                            "description": "The path to the directory relative to the repository root (empty string for root)"
                        }
                    },
                    "required": ["directory_path"]
                }
            },
            {
                "name": "read_pr_comments",
                "description": "Read all comments on the Pull Request. Use this to understand previous fix attempts, user feedback, error discussions, and any additional context from the conversation. Especially useful when this is not the first fix attempt.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "propose_fix",
                "description": "Propose a fix by specifying which files to modify and their new contents. Call this tool once you've analyzed the issue and determined the necessary changes.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "A clear description of what this fix does (will be used as commit message)"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Detailed explanation of why this fix should work"
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Your confidence level in this fix"
                        },
                        "file_changes": {
                            "type": "object",
                            "description": "Dictionary mapping file paths to their new complete contents. Only include files that need to be modified.",
                            "additionalProperties": {
                                "type": "string"
                            }
                        },
                        "warnings": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Any warnings or caveats about this fix"
                        }
                    },
                    "required": ["description", "reasoning", "confidence", "file_changes"]
                }
            }
        ]

    def _handle_tool_call(
        self,
        tool_name: str,
        tool_input: Dict,
        installation_id: int,
        repo_owner: str,
        repo_name: str,
        branch: str
    ) -> str:
        """Handle a tool call from Claude.

        Args:
            tool_name: Name of the tool
            tool_input: Tool input parameters
            installation_id: GitHub installation ID
            repo_owner: Repository owner
            repo_name: Repository name
            branch: Branch name

        Returns:
            Tool result as string
        """
        try:
            if tool_name == "read_file":
                file_path = tool_input["file_path"]
                logger.info("reading_file_for_fix", file_path=file_path)

                repo = self.github_client.get_repository(installation_id, repo_owner, repo_name)

                try:
                    # Get file from specific branch
                    file_content = repo.get_contents(file_path, ref=branch)
                    content = file_content.decoded_content.decode('utf-8')
                    return content
                except Exception as e:
                    return f"Error reading file: {str(e)}"

            elif tool_name == "list_directory":
                directory_path = tool_input["directory_path"]
                logger.info("listing_directory_for_fix", directory=directory_path)

                repo = self.github_client.get_repository(installation_id, repo_owner, repo_name)

                try:
                    contents = repo.get_contents(directory_path or "/", ref=branch)
                    if not isinstance(contents, list):
                        contents = [contents]

                    items = []
                    for item in contents:
                        items.append(f"{'[DIR]' if item.type == 'dir' else '[FILE]'} {item.path}")

                    return "\n".join(items)
                except Exception as e:
                    return f"Error listing directory: {str(e)}"

            elif tool_name == "read_pr_comments":
                logger.info("reading_pr_comments_for_fix")

                repo = self.github_client.get_repository(installation_id, repo_owner, repo_name)

                try:
                    # Get PR number from branch (stored during generate_fix call)
                    pr_number = getattr(self, '_current_pr_number', None)
                    if not pr_number:
                        return "Error: PR number not available"

                    # Get PR and its comments
                    pr = repo.get_pull(pr_number)
                    comments = pr.get_issue_comments()

                    # Format comments for Claude
                    formatted_comments = []
                    for comment in comments:
                        author = comment.user.login
                        body = comment.body
                        created = comment.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                        formatted_comments.append(f"**@{author}** commented on {created}:\n{body}")

                    if not formatted_comments:
                        return "No comments on this PR yet."

                    return "\n\n---\n\n".join(formatted_comments)
                except Exception as e:
                    return f"Error reading PR comments: {str(e)}"

            elif tool_name == "propose_fix":
                # This is handled separately - just return success
                return "Fix proposal received"

            else:
                return f"Unknown tool: {tool_name}"

        except Exception as e:
            logger.error("tool_call_failed", tool=tool_name, error=str(e))
            return f"Error: {str(e)}"

    async def generate_fix(
        self,
        installation_id: int,
        repo_owner: str,
        repo_name: str,
        branch: str,
        pr_number: int,
        deployment_logs: str,
        analysis_summary: str,
        root_cause: str
    ) -> Optional[ProposedFix]:
        """Generate a fix for a CI/deployment failure.

        Args:
            installation_id: GitHub installation ID
            repo_owner: Repository owner
            repo_name: Repository name
            branch: Branch name to fix
            pr_number: Pull request number (for reading comments)
            deployment_logs: Failure logs (CI output or deployment logs)
            analysis_summary: Previous analysis summary
            root_cause: Root cause analysis

        Returns:
            ProposedFix if successful, None otherwise
        """
        if not self.anthropic_client:
            raise ValueError("Anthropic client not available")

        # Store PR number for use in tool calls
        self._current_pr_number = pr_number

        logger.info(
            "generating_fix",
            repo=f"{repo_owner}/{repo_name}",
            branch=branch,
            pr_number=pr_number
        )

        # Truncate logs
        truncated_logs = deployment_logs[-6000:] if len(deployment_logs) > 6000 else deployment_logs

        # Build context-rich prompt
        system_prompt = """You are an expert engineer helping to fix CI and deployment failures automatically.

**Deployment Environment Context:**
- Platform: Coolify (self-hosted PaaS)
- Deployment method: Docker Compose
- Common architectures: linux/amd64 (on DigitalOcean/Hetzner) or linux/arm64 (on AWS Graviton)
- You have access to the repository source code via tools

**Your Task:**
1. **IMPORTANT**: Start by reading PR comments with `read_pr_comments` to see if there were previous fix attempts, user feedback, or error discussions
2. Read relevant files from the repository (docker-compose.yaml, Dockerfiles, config files, etc.)
3. Analyze the failure logs and previous analysis
4. Determine the root cause and required fixes
5. Propose specific file changes to fix the issue

**Available Tools:**
- read_pr_comments: Read all PR comments to understand previous attempts and feedback (use this first!)
- read_file: Read any file from the repository
- list_directory: List files in a directory
- propose_fix: Submit your proposed fix with file changes

**Important Guidelines:**
- If this is not the first fix attempt, read PR comments first to learn from previous failures
- Only modify files that are necessary to fix the issue
- Provide complete file contents (not diffs) in your proposed changes
- Be conservative - only make changes you're confident about
- If you're unsure, set confidence to "medium" or "low"
- Add warnings for any potential side effects"""

        user_prompt = f"""A deployment has failed. Please analyze the issue and propose a fix.

**Repository:** {repo_owner}/{repo_name}
**Branch:** {branch}

**Previous Analysis Summary:**
{analysis_summary}

**Root Cause Analysis:**
{root_cause}

**Recent Deployment Logs:**
```
{truncated_logs}
```

Please use the available tools to read relevant files, analyze the issue, and propose a fix."""

        messages = [{"role": "user", "content": user_prompt}]
        tools = self._define_tools()

        proposed_fix = None
        max_iterations = 10

        for iteration in range(max_iterations):
            logger.debug(f"fix_generation_iteration", iteration=iteration)

            try:
                response = self.anthropic_client.messages.create(
                    model=settings.claude_model,
                    max_tokens=4000,
                    system=system_prompt,
                    messages=messages,
                    tools=tools
                )
            except RateLimitError as e:
                logger.error("anthropic_rate_limit_during_fix", error=str(e))
                return None
            except APIConnectionError as e:
                logger.error("anthropic_connection_error_during_fix", error=str(e))
                return None
            except APIStatusError as e:
                logger.error("anthropic_api_error_during_fix", error=str(e), status_code=e.status_code)
                return None
            except Exception as e:
                logger.error("fix_generation_api_error", error=str(e), error_type=type(e).__name__)
                return None

            logger.info(
                "claude_response_received",
                stop_reason=response.stop_reason,
                content_blocks=len(response.content)
            )

            # Add assistant response to conversation
            messages.append({
                "role": "assistant",
                "content": response.content
            })

            # Check if Claude wants to use tools
            if response.stop_reason == "tool_use":
                tool_results = []

                for block in response.content:
                    if isinstance(block, ToolUseBlock):
                        tool_name = block.name
                        tool_input = block.input

                        logger.info("tool_called", tool=tool_name, input=tool_input)

                        # Special handling for propose_fix
                        if tool_name == "propose_fix":
                            proposed_fix = ProposedFix(
                                description=tool_input["description"],
                                file_changes=tool_input["file_changes"],
                                reasoning=tool_input["reasoning"],
                                confidence=tool_input["confidence"],
                                warnings=tool_input.get("warnings", [])
                            )

                            tool_result = {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": "Fix proposal accepted. Analysis complete."
                            }
                        else:
                            # Handle other tools
                            result = self._handle_tool_call(
                                tool_name,
                                tool_input,
                                installation_id,
                                repo_owner,
                                repo_name,
                                branch
                            )

                            tool_result = {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result
                            }

                        tool_results.append(tool_result)

                # Add tool results to conversation
                messages.append({
                    "role": "user",
                    "content": tool_results
                })

                # If fix was proposed, we're done
                if proposed_fix:
                    logger.info(
                        "fix_generated",
                        confidence=proposed_fix.confidence,
                        files_changed=len(proposed_fix.file_changes)
                    )
                    return proposed_fix

            elif response.stop_reason == "end_turn":
                # Claude finished without proposing a fix
                logger.warning("claude_finished_without_proposing_fix")
                return None
            else:
                logger.warning("unexpected_stop_reason", reason=response.stop_reason)
                return None

        logger.warning("max_iterations_reached_without_fix")
        return None


# Global instance
def create_fix_generator(github_client: GitHubClient) -> FixGenerator:
    """Create a fix generator instance."""
    return FixGenerator(github_client)
