# Architecture Deep Dive

## Overview

The AI Orchestration Platform implements a state-machine-based multi-agent system using LangGraph for workflow orchestration, Perplexity for research capabilities, and GitHub for code operations.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Orchestration Layer                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           LangGraph State Machine                    │   │
│  │  - Conditional routing                               │   │
│  │  - State persistence (SQLite/PostgreSQL)            │   │
│  │  - Automatic retries                                 │   │
│  │  - Checkpointing for resume                          │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                       Agent Layer                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Planner  │  │  Coder   │  │  Tester  │  │ Reviewer │  │
│  │          │  │          │  │          │  │          │  │
│  │ Claude   │  │ Claude   │  │ Claude   │  │ Claude   │  │
│  │ Sonn et  │  │ Sonnet   │  │ Sonnet   │  │ Sonnet   │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                        Tool Layer                            │
│  ┌─────────────────────┐       ┌─────────────────────┐    │
│  │  Perplexity MCP     │       │   GitHub API        │    │
│  │  - Research         │       │   - Issues          │    │
│  │  - Best practices   │       │   - Files           │    │
│  │  - Citations        │       │   - Branches        │    │
│  └─────────────────────┘       │   - Pull Requests   │    │
│                                 │   - Reviews         │    │
│                                 └─────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Agent Workflows

### 1. Planner Agent

**Responsibilities:**
- Gather context (GitHub issue, specs, existing code)
- Research problem domain via Perplexity
- Decompose into actionable tasks
- Define file structure and dependencies

**Workflow:**
```
Input → [Get Issue] → [Research] → [Analyze Code] → [Create Plan] → Output
```

### 2. Coder Agent

**Responsibilities:**
- Implement features based on plan
- Create/update files
- Manage branches
- Create pull requests
- Handle retry logic for test failures

**Workflow:**
```
Plan → [Read Context] → [Generate Code] → [Create Branch] → 
[Commit Files] → [Create PR] → Output
```

### 3. Tester Agent

**Responsibilities:**
- Generate comprehensive tests
- Execute test suite
- Report failures
- Calculate coverage

**Workflow:**
```
PR → [Get Changes] → [Generate Tests] → [Run Tests] → 
[Report Results] → Output
```

### 4. Reviewer Agent

**Responsibilities:**
- Review code changes
- Check for issues (bugs, performance, security)
- Provide actionable feedback
- Approve or request changes

**Workflow:**
```
PR → [Get Diff] → [Analyze Code] → [Check Quality] → 
[Post Review] → Output
```

## State Management

### OrchestrationState

Central state shared across all agents:

```python
OrchestrationState = {
    # Input
    "repo": str,
    "issue_number": int | None,
    "pr_number": int | None,
    "spec_content": str | None,
    "mode": str,  # autonomous, plan, review
    
    # Planning
    "plan": dict,
    "tasks": list,
    
    # Implementation
    "files_changed": list,
    "branches_created": list,
    "prs_created": list,
    
    # Testing
    "test_results": dict,
    "test_failures": list,
    
    # Review
    "review_comments": list,
    "approval_status": str,
    
    # Control
    "retry_count": int,
    "error": str | None,
}
```

### Persistence

LangGraph checkpoints state after each agent execution:
- Enables resume on failure
- Supports debugging and replay
- Stored in SQLite (dev) or PostgreSQL (prod)

## Conditional Routing

### Decision Points

1. **After Planner**:
   - Plan-only mode → END
   - Autonomous mode → Coder

2. **After Coder**:
   - Review mode → Reviewer
   - Otherwise → Tester

3. **After Tester**:
   - Tests passed → Reviewer
   - Tests failed + retries available → Coder
   - Tests failed + no retries → END

4. **After Reviewer**:
   - Changes requested + retries available → Coder
   - Approved or no retries → END

## Error Handling

### Retry Strategy

- Max 3 retries per workflow
- Exponential backoff for API calls
- Preserve context across retries
- Human escalation on repeated failures

### Failure Modes

1. **Agent Failure**: Logged, state persisted, workflow stopped
2. **Tool Failure**: Retry with backoff, fallback to alternative
3. **Rate Limit**: Queue job, retry after cooldown
4. **Timeout**: Save checkpoint, allow manual resume

## Observability

### Logging

- Structured JSON logs (structlog)
- Agent-level tracing
- Tool call recording
- Performance metrics

### Metrics

- Job duration
- Agent execution time
- Tool call latency
- Success/failure rates
- Cost per operation

### Tracing (LangSmith)

- Full workflow trace
- LLM call details
- Token usage
- Latency breakdown

## Security

### Secrets Management

- Environment variables only
- Never logged or committed
- Rotation every 90 days
- Separate dev/prod keys

### GitHub Permissions

- Fine-grained tokens
- Minimum required scopes
- Per-repo access
- Human gates for sensitive operations

### Code Execution

- No arbitrary code execution
- All operations via GitHub API
- Read-only file access
- Isolated environments

## Scalability

### Horizontal Scaling

- Stateless API servers
- Shared database for state
- Queue-based job distribution
- Multiple worker processes

### Cost Optimization

- Cache Perplexity results
- Batch GitHub operations
- Lazy agent initialization
- Smart retry limits

## Future Enhancements

- [ ] Parallel agent execution
- [ ] Custom agent teams per project
- [ ] Multi-repository workflows
- [ ] Learning from past executions
- [ ] Auto-scaling based on load
- [ ] Advanced cost tracking
