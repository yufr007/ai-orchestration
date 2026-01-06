"""Coder agent - Implements features with file operations and PR creation."""

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


CODER_SYSTEM_PROMPT = """You are an elite Staff Engineer implementing features to production-grade standards.

Your responsibilities:
1. Write clean, maintainable, well-documented code
2. Follow project conventions and best practices
3. Implement complete solutions (no TODOs or placeholder code)
4. Consider edge cases and error handling
5. Write code that passes linting and type checking

Guidelines:
- Use type hints for Python
- Add docstrings for all functions/classes
- Handle errors gracefully with proper logging
- Keep functions focused and testable
- Follow DRY principles
- Consider performance and scalability

When given a task, provide:
1. Complete file content (not diffs)
2. Explanation of approach
3. Any assumptions made
4. Testing considerations

Output Format:
{
  "files": [
    {
      "path": "src/module/file.py",
      "content": "complete file content here",
      "action": "create|update",
      "explanation": "Why this change was made"
    }
  ],
  "approach": "High-level explanation",
  "assumptions": ["Assumption 1"],
  "testing_notes": "How to test this"
}
"""


async def implement_task(task: dict[str, Any], repo: str, branch: str) -> dict[str, Any]:
    """Implement a single task using LLM."""
    settings = get_settings()

    llm = ChatAnthropic(
        model=settings.default_agent_model,
        temperature=0.2,
        api_key=settings.anthropic_api_key,
    )

    # Get existing file contents for updates
    existing_files = {}
    for file_path in task.get("files", []):
        try:
            content = await get_file_contents(repo, file_path, branch)
            existing_files[file_path] = content
        except Exception:
            # File doesn't exist yet (create case)
            existing_files[file_path] = None

    # Build context
    context = f"""Task: {task.get('title', '')}
Type: {task.get('type', '')}
Files to modify: {', '.join(task.get('files', []))}

Acceptance Criteria:
{chr(10).join(f"- {c}" for c in task.get('acceptance_criteria', []))}

"""

    if existing_files:
        context += "\nExisting Files:\n"
        for path, content in existing_files.items():
            if content:
                context += f"\n--- {path} ---\n{content[:1000]}...\n"
            else:
                context += f"\n--- {path} (new file) ---\n"

    context += "\nProvide complete implementation following production standards."

    messages = [
        SystemMessage(content=CODER_SYSTEM_PROMPT),
        HumanMessage(content=context),
    ]

    response = await llm.ainvoke(messages)

    # Parse response
    import json

    try:
        result = json.loads(response.content)
    except json.JSONDecodeError:
        # Extract JSON from markdown
        content = response.content
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            result = json.loads(content[json_start:json_end].strip())
        else:
            # Fallback
            result = {
                "files": [],
                "approach": "Implementation completed",
                "assumptions": [],
                "testing_notes": "Test manually",
            }

    return result


async def coder_node(state: OrchestrationState) -> dict[str, Any]:
    """Coder agent node - implement tasks in parallel."""
    settings = get_settings()
    repo = state["repo"]
    tasks = state.get("tasks", [])
    retry_count = state.get("retry_count", 0)

    if not tasks:
        return {
            "agent_results": [
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

    # Create feature branch
    issue_number = state.get("issue_number")
    branch_name = f"feature/issue-{issue_number}" if issue_number else "feature/auto-implement"
    if retry_count > 0:
        branch_name += f"-retry-{retry_count}"

    try:
        await create_branch(repo, branch_name)
    except Exception as e:
        # Branch might already exist
        pass

    # Implement tasks (respecting dependencies, parallel where possible)
    # For simplicity, implement sequentially for now
    all_files_changed = []
    implementation_results = []

    for task in tasks:
        try:
            impl_result = await implement_task(task, repo, branch_name)
            implementation_results.append(impl_result)

            # Commit files
            for file_data in impl_result.get("files", []):
                file_path = file_data["path"]
                file_content = file_data["content"]
                commit_msg = f"{task['type'].capitalize()}: {task['title']}"

                await create_or_update_file(
                    repo=repo,
                    path=file_path,
                    content=file_content,
                    branch=branch_name,
                    message=commit_msg,
                )

                all_files_changed.append(file_path)

        except Exception as e:
            # Log and continue
            implementation_results.append({"error": str(e), "task": task["id"]})

    # Create PR if files changed
    prs_created = state.get("prs_created", [])
    if all_files_changed:
        try:
            pr_number = await create_pull_request(
                repo=repo,
                head=branch_name,
                base="main",
                title=f"Implement: {state.get('plan', {}).get('tasks', [{}])[0].get('title', 'Feature')}",
                body="## Changes\n\n"
                + "\n".join(f"- {task['title']}" for task in tasks)
                + "\n\n## Files Changed\n\n"
                + "\n".join(f"- `{f}`" for f in all_files_changed),
            )
            prs_created.append(pr_number)
        except Exception as e:
            pr_number = None

    # Create agent result
    agent_result: AgentResult = {
        "agent": AgentRole.CODER,
        "status": TaskStatus.COMPLETED if all_files_changed else TaskStatus.FAILED,
        "output": f"Implemented {len(tasks)} tasks, changed {len(all_files_changed)} files",
        "artifacts": {"implementations": implementation_results, "branch": branch_name},
        "metadata": {"files_count": len(all_files_changed), "tasks_count": len(tasks)},
        "timestamp": datetime.now(),
    }

    return {
        "files_changed": all_files_changed,
        "branches_created": [branch_name],
        "prs_created": prs_created,
        "agent_results": state.get("agent_results", []) + [agent_result],
        "current_agent": AgentRole.CODER,
        "retry_count": retry_count,
    }
