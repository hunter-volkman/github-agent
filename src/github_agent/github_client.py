"""GitHub API client with typed responses."""

from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel


# ============================================================================
# Data Models
# ============================================================================


class User(BaseModel):
    """GitHub user."""

    login: str
    avatar_url: str | None = None


class Label(BaseModel):
    """PR/Issue label."""

    name: str
    color: str


class ReviewRequest(BaseModel):
    """Pending review request."""

    login: str  # Reviewer's username


class PullRequestSummary(BaseModel):
    """Summary of a PR for list views."""

    number: int
    title: str
    state: str
    user: User
    created_at: datetime
    updated_at: datetime
    draft: bool
    labels: list[Label] = []


class PullRequestDetail(BaseModel):
    """Detailed PR information."""

    number: int
    title: str
    body: str | None
    state: str
    user: User
    created_at: datetime
    updated_at: datetime
    merged_at: datetime | None
    draft: bool
    mergeable: bool | None
    mergeable_state: str | None
    labels: list[Label] = []
    requested_reviewers: list[User] = []
    head_ref: str  # Branch name
    base_ref: str  # Target branch
    additions: int
    deletions: int
    changed_files: int
    comments: int
    review_comments: int


class Review(BaseModel):
    """PR review."""

    user: User
    state: str  # APPROVED, CHANGES_REQUESTED, COMMENTED, PENDING
    body: str | None
    submitted_at: datetime | None


class Comment(BaseModel):
    """PR comment (issue comment or review comment)."""

    user: User
    body: str
    created_at: datetime
    path: str | None = None  # For review comments, the file path
    line: int | None = None  # For review comments, the line number


class CheckRun(BaseModel):
    """CI check run."""

    name: str
    status: str  # queued, in_progress, completed
    conclusion: str | None  # success, failure, neutral, cancelled, skipped, timed_out
    started_at: datetime | None
    completed_at: datetime | None


class ChecksSummary(BaseModel):
    """Summary of all checks on a PR."""

    total: int
    passed: int
    failed: int
    pending: int
    checks: list[CheckRun]


class FileDiff(BaseModel):
    """File changed in a PR."""

    filename: str
    status: str  # added, removed, modified, renamed
    additions: int
    deletions: int
    patch: str | None = None  # The actual diff (can be large)


# ============================================================================
# GitHub Client
# ============================================================================


class GitHubClient:
    """Async client for GitHub API."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    def _parse_repo(self, repo: str) -> tuple[str, str]:
        """Parse 'owner/repo' into (owner, repo)."""
        parts = repo.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid repo format: {repo}. Expected 'owner/repo'")
        return parts[0], parts[1]

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Make GET request and return JSON response."""
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    # ========================================================================
    # Pull Request Operations
    # ========================================================================

    async def list_pull_requests(
        self,
        repo: str,
        state: str = "open",
        sort: str = "updated",
        direction: str = "desc",
        per_page: int = 10,
        author: str | None = None,
    ) -> list[PullRequestSummary]:
        """List pull requests for a repository."""
        owner, repo_name = self._parse_repo(repo)

        # If author filter specified, use search API instead (list API doesn't support author filter)
        if author:
            return await self.search_pull_requests(
                query=f"is:{state} author:{author}",
                repo=repo,
                per_page=per_page,
            )

        data = await self._get(
            f"/repos/{owner}/{repo_name}/pulls",
            params={
                "state": state,
                "sort": sort,
                "direction": direction,
                "per_page": per_page,
            },
        )
        return [self._parse_pr_summary(pr) for pr in data]

    async def get_pull_request(self, repo: str, pr_number: int) -> PullRequestDetail:
        """Get detailed information about a specific PR."""
        owner, repo_name = self._parse_repo(repo)
        data = await self._get(f"/repos/{owner}/{repo_name}/pulls/{pr_number}")
        return self._parse_pr_detail(data)

    async def get_pr_reviews(self, repo: str, pr_number: int) -> list[Review]:
        """Get all reviews on a PR."""
        owner, repo_name = self._parse_repo(repo)
        data = await self._get(f"/repos/{owner}/{repo_name}/pulls/{pr_number}/reviews")
        return [
            Review(
                user=User(login=r["user"]["login"], avatar_url=r["user"].get("avatar_url")),
                state=r["state"],
                body=r.get("body"),
                submitted_at=r.get("submitted_at"),
            )
            for r in data
        ]

    async def get_pr_comments(self, repo: str, pr_number: int) -> list[Comment]:
        """Get all comments on a PR (both issue comments and review comments)."""
        owner, repo_name = self._parse_repo(repo)

        # Get issue comments (general PR comments)
        issue_comments = await self._get(f"/repos/{owner}/{repo_name}/issues/{pr_number}/comments")

        # Get review comments (inline code comments)
        review_comments = await self._get(f"/repos/{owner}/{repo_name}/pulls/{pr_number}/comments")

        comments = []
        for c in issue_comments:
            comments.append(
                Comment(
                    user=User(login=c["user"]["login"]),
                    body=c["body"],
                    created_at=c["created_at"],
                )
            )
        for c in review_comments:
            comments.append(
                Comment(
                    user=User(login=c["user"]["login"]),
                    body=c["body"],
                    created_at=c["created_at"],
                    path=c.get("path"),
                    line=c.get("line"),
                )
            )

        # Sort by creation time
        comments.sort(key=lambda x: x.created_at)
        return comments

    async def get_pr_checks(self, repo: str, pr_number: int) -> ChecksSummary:
        """Get CI check status for a PR."""
        owner, repo_name = self._parse_repo(repo)

        # First get the PR to find the head SHA
        pr = await self._get(f"/repos/{owner}/{repo_name}/pulls/{pr_number}")
        head_sha = pr["head"]["sha"]

        # Get check runs for that commit
        data = await self._get(f"/repos/{owner}/{repo_name}/commits/{head_sha}/check-runs")

        checks = []
        passed = 0
        failed = 0
        pending = 0

        for run in data.get("check_runs", []):
            check = CheckRun(
                name=run["name"],
                status=run["status"],
                conclusion=run.get("conclusion"),
                started_at=run.get("started_at"),
                completed_at=run.get("completed_at"),
            )
            checks.append(check)

            if check.status != "completed":
                pending += 1
            elif check.conclusion == "success":
                passed += 1
            else:
                failed += 1

        return ChecksSummary(
            total=len(checks),
            passed=passed,
            failed=failed,
            pending=pending,
            checks=checks,
        )

    async def get_pr_files(
        self, repo: str, pr_number: int, include_patch: bool = False
    ) -> list[FileDiff]:
        """Get files changed in a PR."""
        owner, repo_name = self._parse_repo(repo)
        data = await self._get(f"/repos/{owner}/{repo_name}/pulls/{pr_number}/files")

        return [
            FileDiff(
                filename=f["filename"],
                status=f["status"],
                additions=f["additions"],
                deletions=f["deletions"],
                patch=f.get("patch") if include_patch else None,
            )
            for f in data
        ]

    async def search_pull_requests(
        self, query: str, repo: str | None = None, org: str | None = None, per_page: int = 10
    ) -> list[PullRequestSummary]:
        """Search for PRs using GitHub's search syntax."""
        search_query = f"is:pr {query}"
        if repo:
            search_query += f" repo:{repo}"
        elif org:
            search_query += f" org:{org}"

        data = await self._get("/search/issues", params={"q": search_query, "per_page": per_page})

        # Search returns slightly different format, normalize it
        results = []
        for item in data.get("items", []):
            results.append(
                PullRequestSummary(
                    number=item["number"],
                    title=item["title"],
                    state=item["state"],
                    user=User(login=item["user"]["login"]),
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                    draft=item.get("draft", False),
                    labels=[
                        Label(name=l["name"], color=l["color"]) for l in item.get("labels", [])
                    ],
                )
            )
        return results

    # ========================================================================
    # Parsing Helpers
    # ========================================================================

    def _parse_pr_summary(self, data: dict) -> PullRequestSummary:
        return PullRequestSummary(
            number=data["number"],
            title=data["title"],
            state=data["state"],
            user=User(login=data["user"]["login"], avatar_url=data["user"].get("avatar_url")),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            draft=data.get("draft", False),
            labels=[Label(name=l["name"], color=l["color"]) for l in data.get("labels", [])],
        )

    def _parse_pr_detail(self, data: dict) -> PullRequestDetail:
        return PullRequestDetail(
            number=data["number"],
            title=data["title"],
            body=data.get("body"),
            state=data["state"],
            user=User(login=data["user"]["login"], avatar_url=data["user"].get("avatar_url")),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            merged_at=data.get("merged_at"),
            draft=data.get("draft", False),
            mergeable=data.get("mergeable"),
            mergeable_state=data.get("mergeable_state"),
            labels=[Label(name=l["name"], color=l["color"]) for l in data.get("labels", [])],
            requested_reviewers=[
                User(login=r["login"]) for r in data.get("requested_reviewers", [])
            ],
            head_ref=data["head"]["ref"],
            base_ref=data["base"]["ref"],
            additions=data["additions"],
            deletions=data["deletions"],
            changed_files=data["changed_files"],
            comments=data["comments"],
            review_comments=data["review_comments"],
        )
