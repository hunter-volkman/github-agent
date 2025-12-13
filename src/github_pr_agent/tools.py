"""Tool definitions.

This module defines the tools (functions) that Claude can call to interact with GitHub.
Each tool has:
1. A schema (for Claude to understand what the tool does and its parameters)
2. An implementation (the actual code that runs when Claude calls the tool)
"""

import json
from typing import Any

from .github_client import GitHubClient


# ============================================================================
# Tool Schemas - These are sent to Claude so it knows what tools are available
# ============================================================================

TOOL_SCHEMAS = [
    {
        "name": "list_pull_requests",
        "description": "List pull requests in a repository. Use this to see what PRs exist, find PRs by state, or get an overview of PR activity. Can filter by author.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format (e.g., 'facebook/react')",
                },
                "state": {
                    "type": "string",
                    "enum": ["open", "closed", "all"],
                    "description": "Filter by PR state. Default: open",
                },
                "author": {
                    "type": "string",
                    "description": "Filter by author username (without @)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of PRs to return (1-30). Default: 10",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "get_pull_request",
        "description": "Get detailed information about a specific pull request, including title, description, author, branch info, merge status, and stats.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "pr_number": {
                    "type": "integer",
                    "description": "The PR number",
                },
            },
            "required": ["repo", "pr_number"],
        },
    },
    {
        "name": "get_pr_reviews",
        "description": "Get all reviews on a pull request. Shows who reviewed, their decision (approved, changes requested, commented), and review comments.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "pr_number": {
                    "type": "integer",
                    "description": "The PR number",
                },
            },
            "required": ["repo", "pr_number"],
        },
    },
    {
        "name": "get_pr_comments",
        "description": "Get all comments on a pull request, including both general comments and inline code review comments. Useful for understanding discussions and feedback.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "pr_number": {
                    "type": "integer",
                    "description": "The PR number",
                },
            },
            "required": ["repo", "pr_number"],
        },
    },
    {
        "name": "get_pr_checks",
        "description": "Get CI/CD check status for a pull request. Shows which checks passed, failed, or are still running.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "pr_number": {
                    "type": "integer",
                    "description": "The PR number",
                },
            },
            "required": ["repo", "pr_number"],
        },
    },
    {
        "name": "get_pr_files",
        "description": "Get the list of files changed in a pull request with addition/deletion stats. Optionally include the actual diff patches.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "pr_number": {
                    "type": "integer",
                    "description": "The PR number",
                },
                "include_patches": {
                    "type": "boolean",
                    "description": "Whether to include the actual diff content. Default: false (can be large)",
                },
            },
            "required": ["repo", "pr_number"],
        },
    },
    {
        "name": "search_pull_requests",
        "description": """Search for pull requests using GitHub search syntax. Very powerful for complex queries.

Common patterns:
- author:username - PRs by specific author
- review-requested:username - PRs waiting for someone's review  
- reviewed-by:username - PRs reviewed by someone
- is:open / is:merged / is:closed - by state
- is:draft / draft:false - draft status
- created:>2024-01-01 - created after date
- updated:>2024-01-01 - updated after date
- merged:>2024-01-01 - merged after date
- label:bug - by label
- base:main - PRs targeting specific branch
- review:required / review:approved / review:changes_requested

Combine: 'is:open review-requested:alice repo:myorg/myrepo'
For stale PRs: 'is:open created:<2024-01-01'""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query using GitHub search syntax",
                },
                "repo": {
                    "type": "string",
                    "description": "Optional: limit search to a specific repo ('owner/repo' format)",
                },
                "org": {
                    "type": "string",
                    "description": "Optional: search across all repos in an organization (e.g., 'atlassian')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (1-30). Default: 10",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_repo_activity",
        "description": "Get a summary of recent activity in a repository: open PRs needing attention, recently merged PRs, and PRs with failing checks. Great for daily standups or check-ins.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
            },
            "required": ["repo"],
        },
    },
    {
        "name": "get_pr_ready_status",
        "description": "Get a quick ready-to-merge assessment for a PR. Checks: CI status, review approvals, merge conflicts, and any blocking issues. Returns a summary with clear yes/no/blocked status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format",
                },
                "pr_number": {
                    "type": "integer",
                    "description": "The PR number",
                },
            },
            "required": ["repo", "pr_number"],
        },
    },
]


# ============================================================================
# Tool Executor - Runs tools and returns results
# ============================================================================


class ToolExecutor:
    """Executes tools called by the agent."""

    def __init__(self, github_client: GitHubClient, default_repo: str | None = None):
        self.github = github_client
        self.default_repo = default_repo

    def _resolve_repo(self, repo: str | None) -> str:
        """Resolve repo, using default if not provided."""
        if repo:
            return repo
        if self.default_repo:
            return self.default_repo
        raise ValueError("No repository specified and no default configured")

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool and return the result as a string for Claude."""
        try:
            result = await self._dispatch(tool_name, tool_input)
            return self._format_result(result)
        except Exception as e:
            return f"Error executing {tool_name}: {e}"

    async def _dispatch(self, tool_name: str, input: dict[str, Any]) -> Any:
        """Route tool call to appropriate method."""
        match tool_name:
            case "list_pull_requests":
                repo = self._resolve_repo(input.get("repo"))
                return await self.github.list_pull_requests(
                    repo=repo,
                    state=input.get("state", "open"),
                    per_page=min(input.get("limit", 10), 30),
                    author=input.get("author"),
                )

            case "get_pull_request":
                repo = self._resolve_repo(input.get("repo"))
                return await self.github.get_pull_request(repo, input["pr_number"])

            case "get_pr_reviews":
                repo = self._resolve_repo(input.get("repo"))
                return await self.github.get_pr_reviews(repo, input["pr_number"])

            case "get_pr_comments":
                repo = self._resolve_repo(input.get("repo"))
                return await self.github.get_pr_comments(repo, input["pr_number"])

            case "get_pr_checks":
                repo = self._resolve_repo(input.get("repo"))
                return await self.github.get_pr_checks(repo, input["pr_number"])

            case "get_pr_files":
                repo = self._resolve_repo(input.get("repo"))
                return await self.github.get_pr_files(
                    repo, input["pr_number"], include_patch=input.get("include_patches", False)
                )

            case "search_pull_requests":
                return await self.github.search_pull_requests(
                    query=input["query"],
                    repo=input.get("repo"),
                    org=input.get("org"),
                    per_page=min(input.get("limit", 10), 30),
                )

            case "get_repo_activity":
                repo = self._resolve_repo(input.get("repo"))
                return await self._get_repo_activity(repo)

            case "get_pr_ready_status":
                repo = self._resolve_repo(input.get("repo"))
                return await self._get_pr_ready_status(repo, input["pr_number"])

            case _:
                raise ValueError(f"Unknown tool: {tool_name}")

    async def _get_repo_activity(self, repo: str) -> dict[str, Any]:
        """Get a summary of repo activity for check-ins."""
        # Get open PRs
        open_prs = await self.github.list_pull_requests(repo, state="open", per_page=20)

        # Get recently merged (closed PRs we'll filter)
        closed_prs = await self.github.list_pull_requests(repo, state="closed", per_page=10)

        # Analyze open PRs
        needs_review = []
        has_approvals = []
        draft_prs = []

        for pr in open_prs:
            if pr.draft:
                draft_prs.append(pr)
            else:
                # Fetch reviews for each (that's expensive)
                # For now - categorize by basic information
                needs_review.append(pr)

        return {
            "summary": {
                "total_open": len(open_prs),
                "drafts": len(draft_prs),
                "ready_for_review": len(needs_review),
                "recently_closed": len(closed_prs),
            },
            "open_prs": [
                {
                    "number": pr.number,
                    "title": pr.title,
                    "author": pr.user.login,
                    "updated": pr.updated_at.isoformat(),
                    "draft": pr.draft,
                    "labels": [l.name for l in pr.labels],
                }
                # Limit for readability
                for pr in open_prs[:10]
            ],
            "recently_closed": [
                {
                    "number": pr.number,
                    "title": pr.title,
                    "author": pr.user.login,
                    "updated": pr.updated_at.isoformat(),
                }
                for pr in closed_prs[:5]
            ],
        }

    async def _get_pr_ready_status(self, repo: str, pr_number: int) -> dict[str, Any]:
        """Get a comprehensive ready-to-merge status for a PR."""
        # Fetch all relevant data
        pr = await self.github.get_pull_request(repo, pr_number)
        reviews = await self.github.get_pr_reviews(repo, pr_number)
        checks = await self.github.get_pr_checks(repo, pr_number)

        # Analyze reviews
        approvals = [r for r in reviews if r.state == "APPROVED"]
        changes_requested = [r for r in reviews if r.state == "CHANGES_REQUESTED"]
        pending_reviewers = pr.requested_reviewers

        # Determine blocking issues
        blockers = []
        if pr.draft:
            blockers.append("PR is still in draft")
        if changes_requested:
            blockers.append(
                f"Changes requested by: {', '.join(r.user.login for r in changes_requested)}"
            )
        if pending_reviewers:
            blockers.append(
                f"Waiting for review from: {', '.join(r.login for r in pending_reviewers)}"
            )
        if checks.failed > 0:
            failed_names = [
                c.name for c in checks.checks if c.conclusion and c.conclusion != "success"
            ]
            blockers.append(f"Failed checks: {', '.join(failed_names[:3])}")
        if checks.pending > 0:
            blockers.append(f"{checks.pending} checks still running")
        if pr.mergeable is False:
            blockers.append("Has merge conflicts")

        # Determine overall status
        if not blockers:
            status = "READY"
            message = "Ready to merge"
        elif pr.draft:
            status = "DRAFT"
            message = "Still in draft"
        elif changes_requested or (pr.mergeable is False):
            status = "BLOCKED"
            message = "Blocked - action required"
        else:
            status = "PENDING"
            message = "Waiting on reviews or checks"

        return {
            "status": status,
            "message": message,
            "pr": {
                "number": pr.number,
                "title": pr.title,
                "author": pr.user.login,
                "branch": f"{pr.head_ref} → {pr.base_ref}",
                "size": f"+{pr.additions}/-{pr.deletions} in {pr.changed_files} files",
            },
            "reviews": {
                "approvals": len(approvals),
                "approved_by": [r.user.login for r in approvals],
                "changes_requested_by": [r.user.login for r in changes_requested],
                "waiting_on": [r.login for r in pending_reviewers],
            },
            "checks": {
                "passed": checks.passed,
                "failed": checks.failed,
                "pending": checks.pending,
                "total": checks.total,
            },
            "blockers": blockers,
        }

    def _format_result(self, result: Any) -> str:
        """Format tool result as string for Claude."""
        if hasattr(result, "model_dump"):
            # Pydantic model
            return json.dumps(result.model_dump(), indent=2, default=str)
        elif isinstance(result, list):
            # List of Pydantic models
            return json.dumps(
                [item.model_dump() if hasattr(item, "model_dump") else item for item in result],
                indent=2,
                default=str,
            )
        else:
            return json.dumps(result, indent=2, default=str)
