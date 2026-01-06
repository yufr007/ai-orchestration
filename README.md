# AI Orchestration Platform

> Elite multi-agent orchestration framework replicating a Silicon Valley startup team using LangGraph, Perplexity MCP, and GitHub integration.

## 🎯 Overview

This platform implements an autonomous software development team with specialized agents:

- **CTO/Tech Lead**: Architecture decisions, standards enforcement, code quality gates
- **Staff Engineers**: Parallel implementation, file operations, PR creation
- **SRE/DevOps**: Infrastructure-as-code, deployment automation, environment management
- **QA/Test Engineer**: Test generation, execution, failure reporting, merge gates
- **Security Engineer**: Dependency scanning, secrets detection, permission enforcement
- **Release Manager**: Version management, release notes, deployment gates

## 🏗️ Architecture

```
CodeMachine CLI / GitHub Actions
          ↓
   Orchestration Service (LangGraph)
          ↓
    ┌─────┴─────┬──────────┬─────────┐
    ↓           ↓          ↓         ↓
 Planner    Implementer  Tester  Reviewer
    ↓           ↓          ↓         ↓
    └──── MCP Tools Layer ────────────┘
           ↓           ↓
    Perplexity    GitHub API
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Node.js 20+** (for MCP servers)
- **Docker & Docker Compose** (optional, for containerized deployment)
- **WSL2** (if on Windows)
- **Git**

### Required Accounts & Keys

1. **Perplexity Pro** with API access
2. **GitHub** account with Personal Access Token (repo, workflow permissions)
3. **Anthropic** or **OpenAI** API key for agent reasoning
4. **Azure** account (optional, for production PostgreSQL)
5. **LangSmith** account (optional, for observability)

### Installation

#### 1. Clone and Setup Environment

```bash
git clone https://github.com/yufr007/ai-orchestration.git
cd ai-orchestration

# Copy environment template
cp .env.example .env

# Edit .env with your actual keys
nano .env  # or use your preferred editor
```

#### 2. Install Dependencies

**Option A: Local (WSL/Linux/macOS)**

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python packages
pip install -r requirements.txt

# Install Perplexity MCP server
npm install -g @perplexity-ai/mcp-server
```

**Option B: Docker**

```bash
# Build and start all services
docker-compose up --build -d

# View logs
docker-compose logs -f orchestration
```

#### 3. Initialize Database

```bash
# Local SQLite (development)
python -m src.cli.init_db

# Or with Docker Compose (uses PostgreSQL)
docker-compose exec orchestration python -m src.cli.init_db
```

#### 4. Verify Setup

```bash
# Test Perplexity MCP connection
python -m src.tools.test_mcp

# Test GitHub integration
python -m src.tools.test_github

# Run health check
curl http://localhost:8000/health
```

## 📚 Usage

### CLI Commands

```bash
# Run a complete workflow
python -m src.cli.orchestrate \
  --repo yufr007/your-project \
  --issue 123 \
  --mode autonomous

# Plan only (no execution)
python -m src.cli.orchestrate \
  --repo yufr007/your-project \
  --spec specs/feature.md \
  --mode plan

# Review existing PR
python -m src.cli.orchestrate \
  --repo yufr007/your-project \
  --pr 45 \
  --mode review
```

### API Endpoints

```bash
# Start the API server
uvicorn src.api.server:app --reload

# Submit a job
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "yufr007/your-project",
    "issue_number": 123,
    "mode": "autonomous"
  }'

# Check job status
curl http://localhost:8000/api/v1/jobs/{job_id}

# Stream job logs
curl -N http://localhost:8000/api/v1/jobs/{job_id}/stream
```

### GitHub Actions Integration

Add to your project's `.github/workflows/ai-orchestration.yml`:

```yaml
name: AI Orchestration

on:
  issues:
    types: [labeled]
  pull_request:
    types: [opened, synchronize]

jobs:
  orchestrate:
    runs-on: ubuntu-latest
    if: contains(github.event.issue.labels.*.name, 'ai-implement')
    steps:
      - uses: actions/checkout@v4
      
      - name: Run AI Orchestration
        env:
          PERPLEXITY_API_KEY: ${{ secrets.PERPLEXITY_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          docker run --rm \
            -e PERPLEXITY_API_KEY \
            -e ANTHROPIC_API_KEY \
            -e GITHUB_TOKEN \
            yufr007/ai-orchestration:latest \
            orchestrate --issue ${{ github.event.issue.number }}
```

## 🔧 Configuration

### Project Mapping

Create `config/projects.yaml` to map target repositories:

```yaml
projects:
  vitaflow:
    repo: yufr007/vitaflow
    branch: main
    specs_dir: docs/specs
    agents:
      - planner
      - coder
      - tester
      - reviewer
    
  autom8:
    repo: yufr007/autom8
    branch: develop
    specs_dir: specs
    agents:
      - planner
      - coder
      - devops
      - security
      - reviewer
```

### Agent Configuration

Edit `config/agents.yaml` to customize agent behavior:

```yaml
agents:
  planner:
    model: claude-3-5-sonnet
    temperature: 0.3
    tools:
      - perplexity_research
      - github_issues
    max_iterations: 3
  
  coder:
    model: claude-3-5-sonnet
    temperature: 0.2
    parallelism: 3
    tools:
      - github_files
      - github_pr
    max_files_per_pr: 10
```

## 💰 Cost Estimation

### Monthly Budget (Moderate Usage)

| Service | Cost | Notes |
|---------|------|-------|
| **Perplexity API** | $5-20 | $5 included with Pro, ~500-1000 calls/month |
| **Claude API** | $50-150 | ~10k agent calls/month at Sonnet pricing |
| **GitHub Actions** | Free | 2000 min/month free tier |
| **PostgreSQL (Azure)** | $0-20 | Free tier or basic instance |
| **LangSmith** | Free | Developer tier sufficient |
| **Compute** | $20-100 | Self-hosted or cloud runners |
| **Total** | **$75-290/mo** | Scales with usage |

### Per-Operation Costs

- **Simple PR (bug fix)**: ~$0.50-1.00
- **Feature implementation**: ~$2-5
- **Architecture review**: ~$0.20-0.50
- **Deep research + planning**: ~$1-3

## 📊 Observability

### LangSmith Integration

```bash
# Enable tracing
export LANGSMITH_API_KEY=your_key
export LANGSMITH_PROJECT=ai-orchestration
export LANGCHAIN_TRACING_V2=true

# Run with full tracing
python -m src.cli.orchestrate --trace
```

### Local Logging

```bash
# View structured logs
tail -f logs/orchestration.json | jq

# Filter by agent
tail -f logs/orchestration.json | jq 'select(.agent=="planner")'

# Monitor Perplexity calls
tail -f logs/mcp.json | jq 'select(.tool=="perplexity")'
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test suite
pytest tests/agents/test_planner.py -v

# Run with coverage
pytest --cov=src --cov-report=html

# Integration tests (requires live APIs)
pytest tests/integration/ --live-api
```

## 🛡️ Security

### Secret Management

- **Never commit** `.env` or any file containing secrets
- Use **environment variables** or **secret managers** (Azure Key Vault, AWS Secrets Manager)
- **Rotate API keys** every 90 days
- Use **fine-grained GitHub tokens** with minimum required permissions

### Tool Permissions

Agents have restricted tool access:

- **Planner**: Read-only (issues, specs, Perplexity)
- **Coder**: File write, branch create, PR create (no merge)
- **Tester**: Read code, run tests, comment on PR
- **Reviewer**: Read PR, add comments, request changes (no approve/merge)
- **Human gates**: Required for security changes, production deploys, final merge

## 📖 Documentation

- [Architecture Deep Dive](docs/architecture.md)
- [Agent Design Patterns](docs/agents.md)
- [MCP Integration Guide](docs/mcp.md)
- [Deployment Guide](docs/deployment.md)
- [Troubleshooting](docs/troubleshooting.md)

## 🤝 Contributing

This is a personal project for autom8. If you'd like to adapt it:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a PR with detailed description

## 📄 License

MIT License - See [LICENSE](LICENSE) for details

## 🙏 Acknowledgments

- **LangGraph** team for the state-machine orchestration framework
- **Perplexity AI** for the MCP server and research capabilities
- **Anthropic** for Claude API and agent reasoning
- **GitHub** for comprehensive API and Education benefits

## 📧 Contact

Christian Mimmo - [@yufr007](https://github.com/yufr007)

Project Link: [https://github.com/yufr007/ai-orchestration](https://github.com/yufr007/ai-orchestration)
