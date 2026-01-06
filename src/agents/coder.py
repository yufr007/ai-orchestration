"""Coder agent - Implementation and file operations."""

import asyncio
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.github_tools import (
    create_branch,
    create_or_update_file,
    create_pull_request,
    get_file_contents,
)


CODER_SYSTEM_PROMPT = """You are an elite Staff Software Engineer at a Silicon Valley startup.

Your role:
- Implement features based on task specifications
- Write clean, production-grade code following best practices
- Create comprehensive tests alongside implementation
- Follow existing code patterns and architecture
- Document complex logic with clear comments

Guidelines:
- Always read existing code before making changes
- Maintain consistency with the existing codebase
- Write self-documenting code with meaningful names
- Include error handling and edge cases
- Add inline comments only for non-obvious logic
- Ensure code is testable and modular

Output:
- Complete, production-ready file contents
- No placeholders, TODOs, or partial implementations
- Full files, not diffs or snippets
"""


async def coder_node(state: OrchestrationState) -> dict[str, Any]:
    """Coder agent: Implement tasks and create PR."""
    settings = get_settings()
    repo = state["repo"]
    tasks = state.get("tasks", [])
    plan = state.get("plan")

    if not tasks:
        return {
            "agent_results": state.get("agent_results", [])
            + [
                {
                    "agent": AgentRole.CODER,
                    "status": TaskStatus.SKIPPED,
                    "output": "No tasks to implement",
                    "artifacts": {},
                    "metadata": {},
                    "timestamp": datetime.now(),
                }
            ],
            "current_agent": AgentRole.CODER,
        }

    try:
        # Initialize LLM
        llm = ChatAnthropic(
            model=settings.default_agent_model,
            temperature=0.2,  # Lower for consistent code generation
            api_key=settings.anthropic_api_key,
        )

        # Create feature branch
        branch_name = f"feature/ai-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        await create_branch(repo, branch_name)

        files_changed = []
        retry_count = state.get("retry_count", 0)

        # Process tasks (in production, could parallelize with asyncio.gather)
        for task in tasks:
            if task.get("status") == "completed":
                continue

            # Get context for this task
            task_context = f"""
# Task
{task['description']}

# Plan Context
{plan.get('content', '') if plan else 'No plan available'}

# Previous Failures (Retry {retry_count})
{get_failure_context(state) if retry_count > 0 else 'First attempt'}
"""

            # Determine which files to modify (simplified - production would be smarter)
            # For now, ask LLM to identify files
            file_identification = await llm.ainvoke(
                [
                    SystemMessage(content="You are a code architect."),
                    HumanMessage(
                        content=f"""Given this task, list the EXACT file paths that need to be created or modified.

{task_context}

Return ONLY file paths, one per line, no explanations.
Example:
src/api/routes.py
src/models/user.py
tests/test_user.py
"""
                    ),
                ]
            )

            file_paths = [line.strip() for line in file_identification.content.split("\n") if line.strip()]

            # Implement each file
            for file_path in file_paths:
                # Get existing content if file exists
                existing_content = ""
                try:
                    existing_content = await get_file_contents(repo, file_path, branch_name)
                except Exception:
                    existing_content = "# New file"

                # Generate new content
                implementation = await llm.ainvoke(
                    [
                        SystemMessage(content=CODER_SYSTEM_PROMPT),
                        HumanMessage(
                            content=f"""Implement the complete file content for:

**File**: {file_path}

**Task**: {task['description']}

**Plan Context**:
{plan.get('content', '')[:1000] if plan else ''}

**Existing Content**:
```
{existing_content}
```

**Instructions**:
- Provide COMPLETE file content (not a diff)
- Include all necessary imports
- Add comprehensive error handling
- Follow existing patterns
- Include docstrings and type hints
- No TODOs or placeholders

Output the full file content only, no explanations.
"""
                        ),
                    ]
                )

                # Write file to branch
                await create_or_update_file(
                    repo=repo,
                    path=file_path,
                    content=implementation.content,
                    branch=branch_name,
                    message=f"Implement: {task['description'][:50]}",
                )

                files_changed.append(file_path)

            # Mark task as completed
            task["status"] = "completed"

        # Create pull request
        pr_title = f"AI Implementation: {tasks[0]['description'][:60]}" if tasks else "AI Implementation"
        pr_body = f"""
## Summary
Automated implementation by AI orchestration system.

## Tasks Completed
{chr(10).join(f"- {task['description']}" for task in tasks)}

## Plan
{plan.get('content', 'No plan')[:500] if plan else 'No plan'}

## Files Changed
{chr(10).join(f"- `{file}`" for file in files_changed)}

---
*Generated by AI Orchestration Platform*
"""

        pr_number = await create_pull_request(
            repo=repo,
            title=pr_title,
            body=pr_body,
            head=branch_name,
            base="main",
        )

        agent_result: AgentResult = {
            "agent": AgentRole.CODER,
            "status": TaskStatus.COMPLETED,
            "output": f"Created PR #{pr_number} with {len(files_changed)} files",
            "artifacts": {
                "branch": branch_name,
                "pr_number": pr_number,
                "files_changed": files_changed,
            },
            "metadata": {
                "task_count": len(tasks),
                "retry_count": retry_count,
            },
            "timestamp": datetime.now(),
        }

        return {
            "files_changed": files_changed,
            "branches_created": state.get("branches_created", []) + [branch_name],
            "prs_created": state.get("prs_created", []) + [pr_number],
            "agent_results": state.get("agent_results", []) + [agent_result],
            "current_agent": AgentRole.CODER,
            "next_agents": [AgentRole.TESTER],
        }

    except Exception as e:
        agent_result: AgentResult = {
            "agent": AgentRole.CODER,
            "status": TaskStatus.FAILED,
            "output": f"Implementation failed: {str(e)}",
            "artifacts": {},
            "metadata": {"error": str(e)},
            "timestamp": datetime.now(),
        }

        return {
            "agent_results": state.get("agent_results", []) + [agent_result],
            "error": str(e),
            "current_agent": AgentRole.CODER,
        }


def get_failure_context(state: OrchestrationState) -> str:
    """Extract context from previous test failures for retry."""
    failures = state.get("test_failures", [])
    if not failures:
        return "No previous failures"

    context = "Previous test failures to address:\n\n"
    for failure in failures[-3:]:  # Last 3 failures
        context += f"- {failure.get('test_name', 'Unknown')}: {failure.get('message', 'No message')}\n"

    return context
