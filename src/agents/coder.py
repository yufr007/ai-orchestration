"""Coder agent: Implementation using GitHub MCP tools."""

import asyncio
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

settings = get_settings()

CODER_SYSTEM_PROMPT = """You are an elite Staff Engineer implementing features to production standards.

Your responsibilities:
1. Implement tasks from the plan with clean, maintainable code
2. Follow best practices and coding standards
3. Add comprehensive error handling
4. Write self-documenting code with clear comments
5. Ensure backward compatibility when modifying existing code
6. Consider performance, security, and scalability

When implementing:
- Read existing files to understand context
- Make minimal, focused changes
- Preserve existing functionality
- Add appropriate logging
- Follow the project's style and conventions

Output implementation decisions and file changes in structured format."""


async def implement_task(llm: ChatAnthropic, task: dict[str, Any], repo: str, branch: str) -> dict[str, Any]:
    """Implement a single task."""
    print(f"\n📦 CODER: Implementing task: {task.get('title', 'Unnamed task')}")

    # Get existing file contents if modifying
    file_contexts = []
    files_to_modify = task.get("files_to_modify", [])

    for file_path in files_to_modify:
        try:
            content = await get_file_contents(repo, file_path, branch)
            file_contexts.append(f"**{file_path}:**\n```\n{content}\n```")
        except Exception:
            file_contexts.append(f"**{file_path}:** (new file)")

    context = "\n\n".join(file_contexts) if file_contexts else "No existing files"

    # Generate implementation
    messages = [
        SystemMessage(content=CODER_SYSTEM_PROMPT),
        HumanMessage(
            content=f"""Task: {task.get('title')}
Description: {task.get('description')}

Existing code:
{context}

Provide complete file contents for each file that needs to be created or modified.
Format as:

FILE: path/to/file.py
```python
(complete file contents)
```

FILE: path/to/another.py
```python
(complete file contents)
```"""
        ),
    ]

    response = await llm.ainvoke(messages)
    implementation = response.content

    # Parse file changes
    file_changes = []
    lines = implementation.split("\n")
    current_file = None
    current_content = []
    in_code_block = False

    for line in lines:
        if line.startswith("FILE:"):
            if current_file and current_content:
                file_changes.append({"path": current_file, "content": "\n".join(current_content)})
            current_file = line.replace("FILE:", "").strip()
            current_content = []
            in_code_block = False
        elif line.strip().startswith("```"):
            in_code_block = not in_code_block
        elif in_code_block and current_file:
            current_content.append(line)

    # Add last file
    if current_file and current_content:
        file_changes.append({"path": current_file, "content": "\n".join(current_content)})

    # Commit changes
    files_changed = []
    for change in file_changes:
        try:
            await create_or_update_file(
                repo=repo,
                path=change["path"],
                content=change["content"],
                branch=branch,
                message=f"Implement: {task.get('title')}",
            )
            files_changed.append(change["path"])
            print(f"  ✓ Updated {change['path']}")
        except Exception as e:
            print(f"  ✗ Failed to update {change['path']}: {e}")

    return {"task_id": task.get("id"), "files_changed": files_changed, "implementation": implementation}


async def coder_node(state: OrchestrationState) -> dict[str, Any]:
    """Execute the coder agent to implement tasks."""
    print("\n⚡ CODER: Starting implementation phase...")

    repo = state["repo"]
    tasks = state.get("tasks", [])
    retry_count = state.get("retry_count", 0)

    if not tasks:
        return {
            "error": "No tasks to implement",
            "agent_results": [
                AgentResult(
                    agent=AgentRole.CODER,
                    status=TaskStatus.FAILED,
                    output="No tasks provided",
                    artifacts={},
                    metadata={},
                    timestamp=datetime.now(),
                )
            ],
        }

    # Initialize LLM
    llm = ChatAnthropic(
        model=settings.default_agent_model,
        temperature=0.2,
        api_key=settings.anthropic_api_key,
    )

    # Create feature branch
    issue_number = state.get("issue_number", "feature")
    branch_name = f"feature/issue-{issue_number}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    if retry_count > 0:
        branch_name = f"{branch_name}-retry{retry_count}"

    print(f"🌿 CODER: Creating branch: {branch_name}")
    await create_branch(repo, branch_name)

    # Implement tasks (parallel for independent tasks)
    print(f"🔨 CODER: Implementing {len(tasks)} tasks...")
    implementations = await asyncio.gather(
        *[implement_task(llm, task, repo, branch_name) for task in tasks[:settings.max_concurrent_agents]],
        return_exceptions=True,
    )

    # Collect results
    all_files_changed = []
    successful_tasks = 0
    failed_tasks = 0

    for impl in implementations:
        if isinstance(impl, Exception):
            failed_tasks += 1
            print(f"  ✗ Task failed: {impl}")
        else:
            successful_tasks += 1
            all_files_changed.extend(impl.get("files_changed", []))

    # Create PR
    pr_number = None
    if all_files_changed:
        print("📤 CODER: Creating pull request...")
        plan = state.get("plan", {})
        pr_title = plan.get("summary", f"Implement issue #{issue_number}")
        pr_body = f"""## Implementation Summary

{plan.get('summary', 'Implementation complete')}

## Tasks Completed

{''.join(f"- {task.get('title')}\n" for task in tasks)}

## Files Changed

{''.join(f"- `{file}`\n" for file in set(all_files_changed))}

---
*Generated by AI Orchestration Platform*
"""

        pr_number = await create_pull_request(
            repo=repo, head=branch_name, base="main", title=pr_title, body=pr_body
        )
        print(f"✅ CODER: Created PR #{pr_number}")

    return {
        "files_changed": list(set(all_files_changed)),
        "branches_created": [branch_name],
        "prs_created": [pr_number] if pr_number else [],
        "current_agent": AgentRole.CODER,
        "retry_count": retry_count + 1,
        "agent_results": [
            AgentResult(
                agent=AgentRole.CODER,
                status=TaskStatus.COMPLETED if successful_tasks > 0 else TaskStatus.FAILED,
                output=f"Implemented {successful_tasks}/{len(tasks)} tasks",
                artifacts={
                    "files_changed": all_files_changed,
                    "branch": branch_name,
                    "pr": pr_number,
                },
                metadata={"successful": successful_tasks, "failed": failed_tasks},
                timestamp=datetime.now(),
            )
        ],
    }
