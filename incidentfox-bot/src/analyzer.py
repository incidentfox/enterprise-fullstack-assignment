"""Failure analysis engine using Claude AI."""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import anthropic
from anthropic import APIConnectionError, APIStatusError, RateLimitError
from anthropic.types import TextBlock, ToolUseBlock

from .config import settings
from .logging_config import get_logger
from .models import FailureCategory

logger = get_logger(__name__)


@dataclass
class AnalysisResult:
    """Result of failure analysis."""
    summary: str
    root_cause: str
    recommendations: List[str]
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


class FailureAnalyzer:
    """Analyze deployment failures using Claude AI."""

    def __init__(self, github_client=None):
        """Initialize analyzer with Anthropic Claude.

        Args:
            github_client: Optional GitHub client for repo access during analysis
        """
        self.github_client = github_client
        # Initialize Anthropic client
        self.anthropic_client = None

        if settings.anthropic_api_key:
            self.anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            logger.info(
                "anthropic_client_initialized",
                default_model=settings.claude_model
            )
        else:
            logger.warning("anthropic_api_key_not_configured")

    def _define_analysis_tools(self) -> List[Dict]:
        """Define tools available to Claude during analysis."""
        return [
            {
                "name": "read_file",
                "description": "Read the contents of a file from the repository. Use this to examine source code, configuration files (like docker-compose.yaml, Dockerfile, package.json), or any other files that might help understand the deployment failure.",
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
                "description": "List files and directories in a repository directory. Use this to explore the repository structure and find relevant files.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "directory_path": {
                            "type": "string",
                            "description": "The path to the directory relative to the repository root (use empty string '' for root directory)"
                        }
                    },
                    "required": ["directory_path"]
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
        """Handle a tool call from Claude during analysis.

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
        if not self.github_client:
            return "Error: GitHub client not available"

        try:
            if tool_name == "read_file":
                file_path = tool_input["file_path"]
                logger.info("reading_file_for_analysis", file_path=file_path)

                repo = self.github_client.get_repository(installation_id, repo_owner, repo_name)

                try:
                    file_content = repo.get_contents(file_path, ref=branch)
                    content = file_content.decoded_content.decode('utf-8')
                    return content
                except Exception as e:
                    return f"Error reading file '{file_path}': {str(e)}"

            elif tool_name == "list_directory":
                directory_path = tool_input["directory_path"]
                logger.info("listing_directory_for_analysis", directory=directory_path)

                repo = self.github_client.get_repository(installation_id, repo_owner, repo_name)

                try:
                    contents = repo.get_contents(directory_path or "/", ref=branch)
                    if not isinstance(contents, list):
                        contents = [contents]

                    items = []
                    for item in contents:
                        items.append(f"{'[DIR]' if item.type == 'dir' else '[FILE]'} {item.path}")

                    return "\n".join(items) if items else "Directory is empty"
                except Exception as e:
                    return f"Error listing directory '{directory_path}': {str(e)}"

            else:
                return f"Unknown tool: {tool_name}"

        except Exception as e:
            logger.error("tool_call_failed", tool=tool_name, error=str(e))
            return f"Error: {str(e)}"

    async def analyze_with_llm(
        self,
        logs: str,
        installation_id: Optional[int] = None,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        branch: Optional[str] = None
    ) -> Tuple[str, str, List[str], Optional[str], Optional[int], Optional[int]]:
        """Analyze failure using Claude AI for insights.

        Args:
            logs: Full deployment logs
            installation_id: Optional GitHub installation ID for repo access
            repo_owner: Optional repository owner
            repo_name: Optional repository name
            branch: Optional branch name

        Returns:
            (summary, root_cause, recommendations, model, prompt_tokens, completion_tokens)
        """
        # Truncate logs if too long (keep last 6000 chars - most recent)
        truncated_logs = logs[-6000:] if len(logs) > 6000 else logs

        # Check if we have repo access
        has_repo_access = all([
            self.github_client,
            installation_id,
            repo_owner,
            repo_name,
            branch
        ])

        system_prompt = """You are an expert SRE analyzing a failed deployment. Generate a GitHub PR comment (markdown) with your analysis.

**Deployment Environment Context:**
- Platform: Coolify (self-hosted PaaS similar to Heroku/Vercel)
- Deployment method: Docker Compose
- Common architectures: linux/amd64 (DigitalOcean/Hetzner) or linux/arm64 (AWS Graviton)"""

        if has_repo_access:
            system_prompt += """
- You have access to the repository source code via tools

**Available Tools:**
- read_file: Read any file from the repository (configuration files, source code, etc.)
- list_directory: List files in a directory to explore the repo structure

**Instructions:**
1. First, examine the deployment logs to understand the error
2. Use the tools to read relevant files (docker-compose.yaml, Dockerfiles, configs, etc.)
3. Provide a comprehensive analysis with specific insights from the actual code"""

        user_prompt = f"""A deployment has failed. Please analyze the issue and provide a detailed explanation.

**Repository:** {repo_owner}/{repo_name} (branch: {branch})

**Recent Deployment Logs:**
```
{truncated_logs}
```

Generate a markdown comment with:
1. **### 📋 Summary** - A brief summary (1-2 sentences) of what went wrong
2. **### 🔍 Root Cause Analysis** - Detailed analysis with specific references to code/config if available
3. **### ✅ Recommended Actions** - 3-5 specific, actionable recommendations to fix it

Use proper markdown formatting (headers, lists, code blocks). Be concise, technical, and actionable."""

        try:
            if not self.anthropic_client:
                raise ValueError("Anthropic client not available - check ANTHROPIC_API_KEY")

            return await self._analyze_with_anthropic(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                installation_id=installation_id,
                repo_owner=repo_owner,
                repo_name=repo_name,
                branch=branch
            )

        except RateLimitError as e:
            logger.error("anthropic_rate_limit", error=str(e), status_code=e.status_code)
            return (
                "Analysis rate limited - please try again",
                "Claude API rate limit reached. Please wait a moment and try again.",
                ["Wait a few seconds and retry", "Check your Anthropic API usage"],
                None,
                None,
                None
            )
        except APIConnectionError as e:
            logger.error("anthropic_connection_error", error=str(e))
            return (
                "Failed to connect to Claude API",
                "Unable to reach Anthropic's API. Please check your internet connection.",
                ["Verify internet connectivity", "Check Anthropic API status", "Retry the analysis"],
                None,
                None,
                None
            )
        except APIStatusError as e:
            logger.error("anthropic_api_error", error=str(e), status_code=e.status_code)
            return (
                f"Claude API error (status {e.status_code})",
                f"Anthropic API returned an error: {e.message}",
                ["Check your Anthropic API key", "Verify API permissions", "Review error logs"],
                None,
                None,
                None
            )
        except Exception as e:
            logger.error("llm_analysis_failed", error=str(e), error_type=type(e).__name__)
            return (
                "Deployment failed - unable to analyze",
                f"Unexpected error during analysis: {str(e)}",
                ["Check deployment logs manually", "Verify application configuration", "Review error details"],
                None,
                None,
                None
            )

    async def _analyze_with_anthropic(
        self,
        system_prompt: str,
        user_prompt: str,
        installation_id: Optional[int] = None,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        branch: Optional[str] = None
    ) -> Tuple[str, str, List[str], str, int, int]:
        """Analyze using Anthropic Claude with optional tool calling.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            installation_id: Optional GitHub installation ID
            repo_owner: Optional repository owner
            repo_name: Optional repository name
            branch: Optional branch name

        Returns:
            (summary, root_cause, recommendations, model, input_tokens, output_tokens)
        """
        model = settings.claude_model
        messages = [{"role": "user", "content": user_prompt}]

        # Check if we should enable tools
        has_repo_access = all([
            self.github_client,
            installation_id,
            repo_owner,
            repo_name,
            branch
        ])

        tools = self._define_analysis_tools() if has_repo_access else None
        max_iterations = 8  # Limit tool use iterations
        total_input_tokens = 0
        total_output_tokens = 0

        for iteration in range(max_iterations):
            logger.debug("analysis_iteration", iteration=iteration)

            # Make API call
            api_params = {
                "model": model,
                "max_tokens": 2000,
                "system": system_prompt,
                "messages": messages
            }

            if tools:
                api_params["tools"] = tools

            response = self.anthropic_client.messages.create(**api_params)

            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            logger.debug(
                "claude_response",
                stop_reason=response.stop_reason,
                iteration=iteration
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

                        logger.info("tool_called_during_analysis", tool=tool_name)

                        # Handle tool call
                        result = self._handle_tool_call(
                            tool_name,
                            tool_input,
                            installation_id,
                            repo_owner,
                            repo_name,
                            branch
                        )

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })

                # Add tool results to conversation
                messages.append({
                    "role": "user",
                    "content": tool_results
                })

                # Continue loop to get next response

            elif response.stop_reason == "end_turn":
                # Claude finished - extract the text content
                content = ""
                for block in response.content:
                    if isinstance(block, TextBlock):
                        content += block.text

                content = content.strip()

                logger.info(
                    "anthropic_analysis_complete",
                    model=response.model,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    iterations=iteration + 1,
                    used_tools=has_repo_access
                )

                # Return markdown content as both summary and root_cause
                return (
                    content[:200] + "..." if len(content) > 200 else content,  # Short summary for DB
                    content,  # Full markdown
                    [],  # No separate recommendations - they're in the markdown
                    response.model,
                    total_input_tokens,
                    total_output_tokens
                )

            else:
                logger.warning("unexpected_stop_reason", reason=response.stop_reason)
                break

        # If we get here, we hit max iterations
        # Make one final call without tools to synthesize everything learned
        logger.warning("max_analysis_iterations_reached_generating_final_report")

        # Add a final prompt asking Claude to synthesize
        messages.append({
            "role": "user",
            "content": "You've explored the repository thoroughly. Based on everything you've learned, please provide your final deployment failure analysis in the requested markdown format."
        })

        try:
            # Final call without tools
            final_response = self.anthropic_client.messages.create(
                model=model,
                max_tokens=2000,
                system=system_prompt,
                messages=messages
                # No tools - force a final text response
            )

            total_input_tokens += final_response.usage.input_tokens
            total_output_tokens += final_response.usage.output_tokens

            # Extract final content
            content = ""
            for block in final_response.content:
                if isinstance(block, TextBlock):
                    content += block.text

            content = content.strip()

            if content:
                logger.info(
                    "final_analysis_after_max_iterations",
                    model=final_response.model,
                    total_input_tokens=total_input_tokens,
                    total_output_tokens=total_output_tokens
                )

                return (
                    content[:200] + "..." if len(content) > 200 else content,
                    content,
                    [],
                    final_response.model,
                    total_input_tokens,
                    total_output_tokens
                )
        except Exception as e:
            logger.error("final_synthesis_failed", error=str(e))

        # Ultimate fallback
        content = "Unable to complete analysis after exploring the repository. Please review the logs manually."
        return (
            content,
            content,
            [],
            model,
            total_input_tokens,
            total_output_tokens
        )

    async def analyze(
        self,
        logs: str,
        installation_id: Optional[int] = None,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        branch: Optional[str] = None
    ) -> AnalysisResult:
        """Perform complete failure analysis using Claude AI.

        Args:
            logs: Deployment logs
            installation_id: Optional GitHub installation ID for repo access
            repo_owner: Optional repository owner
            repo_name: Optional repository name
            branch: Optional branch name

        Returns:
            Analysis result
        """
        logger.info(
            "starting_failure_analysis",
            log_size=len(logs),
            has_repo_access=bool(self.github_client and installation_id)
        )

        # Use Claude AI for analysis with optional repo access
        summary, root_cause, recommendations, model, prompt_tokens, completion_tokens = \
            await self.analyze_with_llm(
                logs,
                installation_id=installation_id,
                repo_owner=repo_owner,
                repo_name=repo_name,
                branch=branch
            )

        result = AnalysisResult(
            summary=summary,
            root_cause=root_cause,
            recommendations=recommendations,
            llm_provider="anthropic",
            llm_model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens
        )

        logger.info(
            "analysis_complete",
            has_recommendations=len(recommendations) > 0,
            model=model
        )

        return result


# Note: Global instance is created in main.py after github_client is initialized
