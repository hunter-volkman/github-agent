"""CLI for the GitHub Agent."""

import asyncio
import sys

import anthropic
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.theme import Theme

from .agent import GitHubAgent
from .config import get_settings
from .github_client import GitHubClient

# Custom theme for consistent styling
custom_theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "red bold",
        "success": "green",
        "tool": "magenta",
    }
)

console = Console(theme=custom_theme)


def print_welcome():
    """Print welcome message."""
    console.print(
        Panel(
            "[bold]GitHub Agent[/bold]\n\n"
            "Ask questions about things in GitHub.\n"
            "Examples:\n"
            '  • "List open PRs"\n'
            '  • "What\'s the status of PR #123?"\n'
            '  • "What\'s blocking the auth-refactor PR?"\n'
            '  • "Show me PRs by @username"\n\n'
            "[dim]Type 'quit' or 'exit' to leave, 'clear' to reset conversation[/dim]",
            title="Welcome",
            border_style="blue",
        )
    )


def print_tool_calls(tool_calls: list[dict]):
    """Print what tools were called."""
    if not tool_calls:
        return
    tools_str = ", ".join(f"[tool]{t['name']}[/tool]" for t in tool_calls)
    console.print(f"[dim]Tools used: {tools_str}[/dim]")


def print_response(response: str):
    """Print agent response with markdown formatting."""
    console.print()
    console.print(Markdown(response))
    console.print()


async def run_interactive(agent: GitHubAgent):
    """Run interactive chat loop."""
    print_welcome()

    while True:
        try:
            # Get user input
            console.print("[bold blue]You:[/bold blue] ", end="")
            user_input = input().strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            if user_input.lower() == "clear":
                agent.reset()
                console.print("[dim]Conversation cleared.[/dim]")
                continue

            # Run agent
            with console.status("[bold green]Thinking...", spinner="dots"):
                result = await agent.run(user_input)

            # Print results
            print_tool_calls(result.tool_calls)
            print_response(result.response)

        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted. Type 'quit' to exit.[/dim]")
        except Exception as e:
            console.print(f"[error]Error: {e}[/error]")


async def run_single_query(agent: GitHubAgent, query: str):
    """Run a single query and print result."""
    result = await agent.run(query)
    print_tool_calls(result.tool_calls)
    print_response(result.response)


async def async_main():
    """Async entry point."""
    # Load configuration
    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[error]Configuration error: {e}[/error]")
        console.print(
            "[dim]Make sure you have a .env file with ANTHROPIC_API_KEY and GITHUB_TOKEN[/dim]"
        )
        sys.exit(1)

    # Initialize clients
    anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async with GitHubClient(settings.github_token) as github_client:
        agent = GitHubAgent(
            anthropic_client=anthropic_client,
            github_client=github_client,
            model=settings.claude_model,
            max_iterations=settings.max_tool_iterations,
        )

        # Check if query provided as argument
        if len(sys.argv) > 1:
            query = " ".join(sys.argv[1:])
            await run_single_query(agent, query)
        else:
            await run_interactive(agent)


def main():
    """Entry point."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
