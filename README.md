# GitHub Agent

A minimal AI agent that answers natural language questions about GitHub pull requests using Claude.

## Architecture

```
User Question
     │
     ▼
┌─────────┐     ┌─────────┐     ┌─────────┐
│  Agent  │────▶│  Tools  │────▶│ GitHub  │
│  Loop   │◀────│         │◀────│   API   │
└─────────┘     └─────────┘     └─────────┘
     │
     ▼
Natural Language Response
```

## Components

| File | Purpose |
|------|---------|
| `agent.py` | Core loop: prompt → tools → response |
| `tools.py` | 7 tools as schemas + execute function |
| `github_client.py` | Typed GitHub API client |
| `cli.py` | Interactive CLI |
| `config.py` | Environment config |

## Setup

```bash
git clone https://github.com/hunter-volkman/github-agent
cd github-agent
pip install -e .

cp .env.example .env
# Add your ANTHROPIC_API_KEY and GITHUB_TOKEN
```

## Usage

```bash
# Interactive mode
github-agent

# Single query
github-agent "What's the status of PR #123 in owner/repo"
```

## Example

```
$ github-agent "What's blocking PR #6057 in block/goose"

Tools used: get_pull_request, get_pr_checks, get_pr_reviews

PR #6057 is blocked by two issues:

1. Merge conflicts with main branch
2. 5 failing CI checks: cleanup, bundle-desktop, comment-on-pr

Current state:
• 1 approval from @DOsinga
• 14/19 checks passing
• +868/-100 lines across 35 files

Next steps:
1. Rebase on main to resolve conflicts
2. Fix failing CI checks
```

## Tools

| Tool | Purpose |
|------|---------|
| `list_pull_requests` | List PRs, filter by state/author |
| `get_pull_request` | Full PR details |
| `get_pr_reviews` | Review decisions |
| `get_pr_checks` | CI/CD status |
| `get_pr_files` | Changed files |
| `get_pr_comments` | Discussion threads |
| `search_pull_requests` | GitHub search syntax |

## How It Works

1. User asks a question
2. Agent sends question + tool schemas to Claude
3. Claude decides which tools to call
4. Agent executes tools, returns results
5. Claude synthesizes natural language response

## License

MIT