"""Tests.

Run with: pytest tests/ -v
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from github_pr_agent.github_client import GitHubClient, PullRequestSummary, User
from github_pr_agent.tools import ToolExecutor, TOOL_SCHEMAS
from github_pr_agent.agent import GitHubPRAgent


# ============================================================================
# Tool Schema Tests - Verify tools are properly defined
# ============================================================================

class TestToolSchemas:
    """Verify tool definitions are valid."""

    def test_all_tools_have_required_fields(self):
        """Each tool must have name, description, and input_schema."""
        for tool in TOOL_SCHEMAS:
            assert "name" in tool, f"Tool missing name: {tool}"
            assert "description" in tool, f"Tool {tool.get('name')} missing description"
            assert "input_schema" in tool, f"Tool {tool.get('name')} missing input_schema"

    def test_tool_names_are_unique(self):
        """No duplicate tool names."""
        names = [t["name"] for t in TOOL_SCHEMAS]
        assert len(names) == len(set(names)), "Duplicate tool names found"

    def test_expected_tools_exist(self):
        """Core tools we expect to have."""
        names = {t["name"] for t in TOOL_SCHEMAS}
        expected = {
            "list_pull_requests",
            "get_pull_request",
            "get_pr_reviews",
            "get_pr_checks",
            "search_pull_requests",
        }
        assert expected.issubset(names), f"Missing tools: {expected - names}"


# ============================================================================
# GitHub Client Tests - Test API response parsing
# ============================================================================

class TestGitHubClient:
    """Test GitHub API client."""

    def test_parse_repo_valid(self):
        """Parse owner/repo format."""
        client = GitHubClient("fake-token")
        owner, repo = client._parse_repo("facebook/react")
        assert owner == "facebook"
        assert repo == "react"

    def test_parse_repo_invalid(self):
        """Reject invalid repo format."""
        client = GitHubClient("fake-token")
        with pytest.raises(ValueError):
            client._parse_repo("invalid-format")

    def test_parse_pr_summary(self):
        """Parse PR data into typed model."""
        client = GitHubClient("fake-token")
        raw_data = {
            "number": 123,
            "title": "Fix bug",
            "state": "open",
            "user": {"login": "alice", "avatar_url": "https://..."},
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-16T10:00:00Z",
            "draft": False,
            "labels": [{"name": "bug", "color": "red"}],
        }
        pr = client._parse_pr_summary(raw_data)
        assert pr.number == 123
        assert pr.title == "Fix bug"
        assert pr.user.login == "alice"
        assert pr.draft is False


# ============================================================================
# Tool Executor Tests - Test tool dispatch
# ============================================================================

class TestToolExecutor:
    """Test tool execution logic."""

    @pytest.fixture
    def mock_github(self):
        """Create mock GitHub client."""
        return AsyncMock(spec=GitHubClient)

    @pytest.fixture
    def executor(self, mock_github):
        """Create executor with mock client."""
        return ToolExecutor(mock_github, default_repo="test/repo")

    @pytest.mark.asyncio
    async def test_list_prs_uses_default_repo(self, executor, mock_github):
        """Should use default repo when none specified."""
        mock_github.list_pull_requests.return_value = []
        
        await executor.execute("list_pull_requests", {})
        
        mock_github.list_pull_requests.assert_called_once()
        call_args = mock_github.list_pull_requests.call_args
        assert call_args.kwargs["repo"] == "test/repo"

    @pytest.mark.asyncio
    async def test_list_prs_respects_provided_repo(self, executor, mock_github):
        """Should use provided repo over default."""
        mock_github.list_pull_requests.return_value = []
        
        await executor.execute("list_pull_requests", {"repo": "other/repo"})
        
        call_args = mock_github.list_pull_requests.call_args
        assert call_args.kwargs["repo"] == "other/repo"

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, executor):
        """Unknown tools should return error message."""
        result = await executor.execute("nonexistent_tool", {})
        assert "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_api_error_handled_gracefully(self, executor, mock_github):
        """API errors should be caught and returned as message."""
        mock_github.list_pull_requests.side_effect = Exception("API rate limit")
        
        result = await executor.execute("list_pull_requests", {"repo": "test/repo"})
        
        assert "Error" in result
        assert "rate limit" in result


# ============================================================================
# Integration Test - Full agent loop (mocked)
# ============================================================================

class TestAgentLoop:
    """Test the agent orchestration loop."""

    @pytest.mark.asyncio
    async def test_agent_calls_tool_and_responds(self):
        """Agent should call tools and synthesize response."""
        # Mock Anthropic client
        mock_anthropic = MagicMock()
        
        # First response: Claude wants to use a tool
        tool_response = MagicMock()
        tool_response.stop_reason = "tool_use"
        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.id = "tool_1"
        tool_use_block.name = "list_pull_requests"  # Explicit assignment, not constructor arg
        tool_use_block.input = {"repo": "test/repo"}
        tool_response.content = [tool_use_block]
        
        # Second response: Claude gives final answer
        final_response = MagicMock()
        final_response.stop_reason = "end_turn"
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Found 3 open PRs."
        final_response.content = [text_block]
        
        mock_anthropic.messages.create.side_effect = [tool_response, final_response]
        
        # Mock GitHub client
        mock_github = AsyncMock(spec=GitHubClient)
        mock_github.list_pull_requests.return_value = []
        
        # Run agent
        agent = GitHubPRAgent(
            anthropic_client=mock_anthropic,
            github_client=mock_github,
            default_repo="test/repo",
        )
        result = await agent.run("List PRs")
        
        # Verify
        assert result.response == "Found 3 open PRs."
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "list_pull_requests"


# ============================================================================
# Smoke Test - Can be run manually against real APIs
# ============================================================================

@pytest.mark.skip(reason="Requires real API keys - run manually with: pytest -k smoke --run-smoke")
class TestSmoke:
    """Smoke tests against real APIs with API key authentication. Run manually to verify setup."""

    @pytest.mark.asyncio
    async def test_can_list_react_prs(self):
        """Verify we can query facebook/react."""
        from github_pr_agent.config import get_settings
        
        settings = get_settings()
        async with GitHubClient(settings.github_token) as client:
            prs = await client.list_pull_requests("facebook/react", per_page=3)
            assert len(prs) > 0
            assert all(pr.number > 0 for pr in prs)