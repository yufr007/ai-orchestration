"""Coder agent: Implementation and file operations."""

from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.github import (
    create_branch,
    create_or_update_file,
    create_pull_request,
    get_file_contents,
)


CODER_SYSTEM_PROMPT = """You are an elite Staff Engineer responsible for implementing features.

Your responsibilities:
1. Read the implementation plan and current codebase
2. Write production-grade code following existing patterns
3. Implement complete solutions - no TODOs, no placeholders, no "sample" code
4. Add comprehensive error handling and input validation
5. Write clear, self-documenting code with minimal comments
6. Follow repository conventions (formatting, naming, structure)
7. Create/update files as needed

Code quality standards:
- Type hints for all functions
- Docstrings for public APIs
- Defensive programming (validate inputs, handle edge cases)
- DRY principle (don't repeat yourself)
- SOLID principles
- Consistent with existing codebase style

Output format:
For each file to create/modify, provide:
```json
{
  "path": "relative/path/to/file.py",
  "content": "complete file content",
  "reason": "why this change is needed"
}
```

Never output partial implementations. Each file must be complete and functional."""


async def coder_node(state: OrchestrationState) -> dict[str, Any]:
    """Coder agent node: Implement features based on plan."""
    settings = get_settings()
    
    # Initialize LLM
    llm = ChatAnthropic(
        model=settings.default_agent_model,
        temperature=0.2,
        api_key=settings.anthropic_api_key,
    )
    
    # Get plan and tasks
    plan = state.get("plan", {})
    tasks = state.get("tasks", [])
    
    if not plan or not tasks:
        return {
            "error": "No plan or tasks available for implementation",
            "agent_results": [
                {
                    "agent": AgentRole.CODER,
                    "status": TaskStatus.FAILED,
                    "output": "Missing plan",
                    "artifacts": {},
                    "metadata": {},
                    "timestamp": datetime.now(),
                }
            ],
        }
    
    # Gather existing code context
    context_parts = []
    context_parts.append(f"Implementation Plan:\n{plan.get('full_plan', '')}")
    
    # Get review feedback if this is a retry
    review_comments = state.get("review_comments", [])
    test_failures = state.get("test_failures", [])
    
    if review_comments:
        context_parts.append(f"\nReview Feedback to Address:\n")
        for comment in review_comments:
            context_parts.append(f"- {comment.get('body', '')}")
    
    if test_failures:
        context_parts.append(f"\nTest Failures to Fix:\n")
        for failure in test_failures:
            context_parts.append(f"- {failure.get('test', '')}: {failure.get('error', '')}")
    
    # Build implementation prompt
    context = "\n\n".join(context_parts)
    
    messages = [
        SystemMessage(content=CODER_SYSTEM_PROMPT),
        HumanMessage(
            content=f"{context}\n\nImplement all required changes. Output complete file contents in JSON format."
        ),
    ]
    
    # Invoke LLM
    response = await llm.ainvoke(messages)
    implementation = response.content
    
    # Parse file changes (simplified - in production use structured output)
    # For demo purposes, create a sample implementation
    files_to_change = [
        {
            "path": "src/feature/new_feature.py",
            "content": '''"""New feature implementation."""\n\ndef new_feature() -> str:\n    """Implement new feature."""\n    return "Feature implemented"\n''',
            "reason": "Core feature implementation",
        }
    ]
    
    # Create branch
    repo_parts = state["repo"].split("/")
    owner, repo_name = repo_parts[0], repo_parts[1]
    
    branch_name = f"feature/issue-{state.get('issue_number', 'auto')}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    try:
        await create_branch(owner=owner, repo=repo_name, branch=branch_name)
    except Exception as e:
        # Branch might already exist if this is a retry
        if "already exists" not in str(e).lower():
            raise
    
    # Apply file changes
    files_changed = []
    for file_change in files_to_change:
        try:
            await create_or_update_file(
                owner=owner,
                repo=repo_name,
                path=file_change["path"],
                content=file_change["content"],
                message=f"Implement: {file_change['reason']}",
                branch=branch_name,
            )
            files_changed.append(file_change["path"])
        except Exception as e:
            print(f"Error updating {file_change['path']}: {e}")
    
    # Create pull request
    pr_title = f"Implement: {plan.get('summary', 'Feature implementation')[:100]}"
    pr_body = f"""## Implementation

{plan.get('summary', '')}

## Changes

{chr(10).join(f'- {f["path"]}: {f["reason"]}' for f in files_to_change)}

## Related

- Issue: #{state.get('issue_number', 'N/A')}
- Plan: See implementation plan in planning phase

Auto-generated by AI Orchestration Platform
"""
    
    pr = await create_pull_request(
        owner=owner,
        repo=repo_name,
        title=pr_title,
        body=pr_body,
        head=branch_name,
        base="main",
    )
    
    # Create agent result
    result: AgentResult = {
        "agent": AgentRole.CODER,
        "status": TaskStatus.COMPLETED,
        "output": implementation,
        "artifacts": {
            "branch": branch_name,
            "pr_number": pr["number"],
            "files_changed": files_changed,
        },
        "metadata": {"retry_count": state.get("retry_count", 0)},
        "timestamp": datetime.now(),
    }
    
    return {
        "files_changed": files_changed,
        "branches_created": [branch_name],
        "prs_created": [pr["number"]],
        "agent_results": [result],
        "current_agent": AgentRole.CODER,
        "messages": [HumanMessage(content=f"PR #{pr['number']} created with {len(files_changed)} files")],
    }
