"""Tool definitions.

Each tool is just:
1. A schema (JSON for Claude)
2. A function (Python that runs)

"""

import json
from typing import Any

from .github_client import GitHubClient


# ============================================================================
# Tools: schema and implementation
# ============================================================================

TOOLS = {
    "list_pull_requests": {
        "schema": {
            "name": "list_pull_requests",
            "description": "List pull requests in a repository. Can filter by state and author.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository in 'owner/repo' format",
                    },
                    "state": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "description": "Filter by PR state. Default: open",
                    },
                    "author": {
                        "type": "string",
                        "description": "Filter by author username",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max PRs to return (1-30). Default: 10",
                    },
                },
                "required": ["repo"],
            },
        },
        "fn": lambda github, input: github.list_pull_requests(
            repo=input["repo"],
            state=input.get("state", "open"),
            per_page=min(input.get("limit", 10), 30),
            author=input.get("author"),
        ),
    },
    "get_pull_request": {
        "schema": {
            "name": "get_pull_request",
            "description": "Get detailed info about a specific PR: title, description, author, branches, merge status, stats.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository in 'owner/repo' format"},
                    "pr_number": {"type": "integer", "description": "The PR number"},
                },
                "required": ["repo", "pr_number"],
            },
        },
        "fn": lambda github, input: github.get_pull_request(input["repo"], input["pr_number"]),
    },
    "get_pr_reviews": {
        "schema": {
            "name": "get_pr_reviews",
            "description": "Get all reviews on a PR: who reviewed, their decision (approved/changes requested), comments.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository in 'owner/repo' format"},
                    "pr_number": {"type": "integer", "description": "The PR number"},
                },
                "required": ["repo", "pr_number"],
            },
        },
        "fn": lambda github, input: github.get_pr_reviews(input["repo"], input["pr_number"]),
    },
    "get_pr_checks": {
        "schema": {
            "name": "get_pr_checks",
            "description": "Get CI/CD check status for a PR: which checks passed, failed, or are running.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository in 'owner/repo' format"},
                    "pr_number": {"type": "integer", "description": "The PR number"},
                },
                "required": ["repo", "pr_number"],
            },
        },
        "fn": lambda github, input: github.get_pr_checks(input["repo"], input["pr_number"]),
    },
    "get_pr_files": {
        "schema": {
            "name": "get_pr_files",
            "description": "Get files changed in a PR with addition/deletion stats.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository in 'owner/repo' format"},
                    "pr_number": {"type": "integer", "description": "The PR number"},
                    "include_patches": {
                        "type": "boolean",
                        "description": "Include actual diff content. Default: false",
                    },
                },
                "required": ["repo", "pr_number"],
            },
        },
        "fn": lambda github, input: github.get_pr_files(
            input["repo"], input["pr_number"], include_patch=input.get("include_patches", False)
        ),
    },
    "get_pr_comments": {
        "schema": {
            "name": "get_pr_comments",
            "description": "Get all comments on a PR: general comments and inline code review comments.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository in 'owner/repo' format"},
                    "pr_number": {"type": "integer", "description": "The PR number"},
                },
                "required": ["repo", "pr_number"],
            },
        },
        "fn": lambda github, input: github.get_pr_comments(input["repo"], input["pr_number"]),
    },
    "search_pull_requests": {
        "schema": {
            "name": "search_pull_requests",
            "description": """Search PRs using GitHub search syntax.

Examples:
- author:username - PRs by author
- review-requested:username - PRs awaiting review
- is:open / is:merged / is:closed - by state
- is:draft - draft PRs
- created:>2024-01-01 - created after date
- label:bug - by label
- base:main - targeting branch

Combine: 'is:open author:alice'""",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "GitHub search query"},
                    "repo": {"type": "string", "description": "Limit to specific repo"},
                    "limit": {"type": "integer", "description": "Max results (1-30). Default: 10"},
                },
                "required": ["query"],
            },
        },
        "fn": lambda github, input: github.search_pull_requests(
            query=input["query"],
            repo=input.get("repo"),
            per_page=min(input.get("limit", 10), 30),
        ),
    },
}


# ============================================================================
# Execution: one function
# ============================================================================


async def execute_tool(name: str, input: dict[str, Any], github: GitHubClient) -> str:
    """Execute a tool and return result as string."""
    try:
        if name not in TOOLS:
            return f"Error: Unknown tool '{name}'"

        result = await TOOLS[name]["fn"](github, input)
        return _format_result(result)

    except Exception as e:
        return f"Error executing {name}: {e}"


def _format_result(result: Any) -> str:
    """Format tool result as JSON string for Claude."""
    if hasattr(result, "model_dump"):
        return json.dumps(result.model_dump(), indent=2, default=str)
    elif isinstance(result, list):
        return json.dumps(
            [item.model_dump() if hasattr(item, "model_dump") else item for item in result],
            indent=2,
            default=str,
        )
    return json.dumps(result, indent=2, default=str)