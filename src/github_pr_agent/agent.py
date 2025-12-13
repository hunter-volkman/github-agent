"""The core agent loop. The agent:
1. Takes a user query
2. Sends it to Claude along with available tools
3. If Claude wants to use a tool, executes it and sends result back
4. Repeats until Claude has a final answer
"""

from dataclasses import dataclass, field
from typing import Any

import anthropic

from .github_client import GitHubClient
from .tools import TOOL_SCHEMAS, ToolExecutor


SYSTEM_PROMPT = """\
You are a GitHub PR assistant that provides clear, actionable status updates on pull requests and repository activity.

## Response Patterns

**Status queries** ("is it ready?", "what's blocking?"):
- Lead with verdict: Ready / Blocked / Needs attention
- List specific blockers: failing checks, pending reviews, requested changes
- Name people and checks, not just counts

**Summary queries** ("what changed?", "summarize this PR"):
- One sentence on what the PR does
- Scope: files changed, lines added/removed
- Status: CI, reviews, conflicts

**Activity queries** ("what's new?", "show recent PRs"):
- Group by status or priority
- Flag stale items (>7 days without activity)
- Note items needing action

## Tool Usage

- Gather complete context before responding—check PR details, reviews, and CI status together
- Use `get_repo_activity` for broad "what's happening?" questions
- Use `get_pr_ready_status` for merge-readiness questions
- For complex questions, make multiple tool calls rather than giving partial answers

## Communication

- Concise but complete
- Use plain English; avoid GitHub jargon unless the user uses it
- Bold key statuses and action items
- Bullets for lists of 3+ items

## Handling Ambiguity

- If no repository is specified, ask which repo to query
- If a PR reference is ambiguous, ask for the PR number
- If a query could match multiple PRs, list them and ask which one
"""


@dataclass
class Message:
    """A message in the conversation."""

    role: str  # "user" or "assistant"
    content: str


@dataclass
class AgentResult:
    """Result from running the agent."""

    response: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    iterations: int = 0


class GitHubPRAgent:
    """Agent that answers questions about GitHub PRs."""

    def __init__(
        self,
        anthropic_client: anthropic.Anthropic,
        github_client: GitHubClient,
        default_repo: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        max_iterations: int = 10,
    ):
        self.anthropic = anthropic_client
        self.tool_executor = ToolExecutor(github_client, default_repo)
        self.model = model
        self.max_iterations = max_iterations
        self.conversation: list[dict[str, Any]] = []

    async def run(self, user_message: str) -> AgentResult:
        """Run the agent with a user message and return the response.

        This is the main agent loop:
        1. Send message to Claude with tools
        2. If Claude uses a tool, execute it and send result back
        3. Repeat until Claude gives a final text response
        """
        # Add user message to conversation
        self.conversation.append({"role": "user", "content": user_message})

        tool_calls = []
        iterations = 0

        while iterations < self.max_iterations:
            iterations += 1

            # Call Claude
            response = self.anthropic.messages.create(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMAS,
                messages=self.conversation,
            )

            # Check stop reason
            if response.stop_reason == "end_turn":
                # Claude is done - extract text response
                text_content = self._extract_text(response.content)
                self.conversation.append({"role": "assistant", "content": response.content})
                return AgentResult(
                    response=text_content,
                    tool_calls=tool_calls,
                    iterations=iterations,
                )

            elif response.stop_reason == "tool_use":
                # Claude wants to use tools - execute them
                self.conversation.append({"role": "assistant", "content": response.content})

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_calls.append({"name": block.name, "input": block.input})

                        # Execute the tool
                        result = await self.tool_executor.execute(block.name, block.input)

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            }
                        )

                # Add tool results to conversation
                self.conversation.append({"role": "user", "content": tool_results})

            else:
                # Unexpected stop reason
                raise RuntimeError(f"Unexpected stop reason: {response.stop_reason}")

        # Hit max iterations
        return AgentResult(
            response="I've done a lot of research but haven't reached a final answer. Here's what I found so far...",
            tool_calls=tool_calls,
            iterations=iterations,
        )

    def _extract_text(self, content: list) -> str:
        """Extract text from response content blocks."""
        texts = []
        for block in content:
            if hasattr(block, "text"):
                texts.append(block.text)
        return "\n".join(texts)

    def reset(self):
        """Clear conversation history."""
        self.conversation = []