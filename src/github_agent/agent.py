"""Agent loop.

The agent:
1. Takes a user query
2. Sends it to Claude along with available tools
3. If Claude wants to use a tool, executes it and sends result back
4. Repeats until Claude has a final answer

"""

from dataclasses import dataclass, field
from typing import Any

import anthropic

from .github_client import GitHubClient
from .tools import TOOLS, execute_tool


SYSTEM_PROMPT = """\
You are a GitHub assistant. Answer questions about repositories, pull requests, and development activity.

Be concise. Lead with the answer. Use the tools to gather information before responding.

If no repository is specified, ask which repo to query.
"""


@dataclass
class AgentResult:
    """Result from running the agent."""
    response: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    iterations: int = 0


class GitHubAgent:
    """Minimal agent that answers questions about GitHub."""

    def __init__(
        self,
        anthropic_client: anthropic.Anthropic,
        github_client: GitHubClient,
        model: str = "claude-sonnet-4-20250514",
        max_iterations: int = 10,
    ):
        self.anthropic = anthropic_client
        self.github = github_client
        self.model = model
        self.max_iterations = max_iterations
        self.conversation: list[dict[str, Any]] = []

    async def run(self, user_message: str) -> AgentResult:
        """Run the agent loop."""
        self.conversation.append({"role": "user", "content": user_message})
        tool_calls = []

        for iteration in range(self.max_iterations):
            response = self.anthropic.messages.create(
                model=self.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=[t["schema"] for t in TOOLS.values()],
                messages=self.conversation,
            )

            # Done - Claude gave a final answer
            if response.stop_reason == "end_turn":
                text = "".join(b.text for b in response.content if hasattr(b, "text"))
                self.conversation.append({"role": "assistant", "content": response.content})
                return AgentResult(response=text, tool_calls=tool_calls, iterations=iteration + 1)

            # Tool use - execute and continue
            if response.stop_reason == "tool_use":
                self.conversation.append({"role": "assistant", "content": response.content})
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        tool_calls.append({"name": block.name, "input": block.input})
                        result = await execute_tool(block.name, block.input, self.github)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                self.conversation.append({"role": "user", "content": tool_results})

        return AgentResult(
            response="Reached maximum iterations without a final answer.",
            tool_calls=tool_calls,
            iterations=self.max_iterations,
        )

    def reset(self):
        """Clear conversation history."""
        self.conversation = []