# GitHub PR Agent

An AI agent that answers natural language questions about GitHub pull requests using Claude.

**Key components:**

- `agent.py` - The core agent loop (LLM ↔ Tools orchestration)
- `tools.py` - Tool schemas and execution logic  
- `github_client.py` - Typed GitHub API client
- `cli.py` - Interactive command-line interface

## Setup

### 1. Clone and install

```bash
git clone https://github.com/yourusername/github-pr-agent
cd github-pr-agent
pip install -e .
```

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env with your API keys
```

You'll need:

- **Anthropic API key**: Get from [console.anthropic.com](https://console.anthropic.com)
- **GitHub token**: Create at [github.com/settings/tokens](https://github.com/settings/tokens) with `repo` scope

### 3. Run

```bash
# Interactive mode
pr-agent

# Single query
pr-agent "List open PRs in facebook/react"
```

## Example Usage

```
You: What's the status of PR #1234 in owner/repo?

[Tools used: get_pull_request, get_pr_reviews, get_pr_checks]

The PR "Add authentication flow" is open and ready for review:

- **Author**: @alice
- **Branch**: feature/auth → main
- **Changes**: +342 / -28 across 8 files

**Reviews**: 
- @bob: Approved ✓
- @carol: Requested changes (waiting)

**CI Status**: 3/4 checks passing
- ✓ lint, ✓ test, ✓ build
- ✗ integration-tests (failing)

**Blocking**: The integration tests are failing and @carol has requested changes.
```

## Project Structure

```
github-pr-agent/
├── src/github_pr_agent/
│   ├── __init__.py
│   ├── agent.py          # Core agent loop
│   ├── cli.py            # Command-line interface
│   ├── config.py         # Configuration management
│   ├── github_client.py  # GitHub API client
│   └── tools.py          # Tool definitions
├── pyproject.toml        # Project metadata
├── .env.example          # Environment template
└── README.md
```

## License

MIT