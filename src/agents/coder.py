"""Coder Agent - Parallel implementation with GitHub MCP integration."""

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


CODER_SYSTEM_PROMPT = """You are an elite Staff Software Engineer implementing production-grade code.

Principles:
- Write clean, maintainable, well-documented code
- Follow language-specific best practices and style guides
- Include comprehensive error handling
- Add type hints/annotations where applicable
- Write self-documenting code with clear naming
- Consider edge cases and performance
- Include docstrings and inline comments for complex logic

No placeholders, no TODOs, no incomplete implementations. Every file must be production-ready.

For each task:
1. Analyze requirements and existing code
2. Implement complete, working solution
3. Ensure proper imports and dependencies
4. Return FULL file contents (not diffs or snippets)"""


async def implement_task(task: dict[str, Any], repo: str, branch: str) -> dict[str, Any]:
    """Implement a single task."""
    settings = get_settings()
    llm = ChatAnthropic(
        model=settings.default_agent_model,
        temperature=settings.default_temperature,
        api_key=settings.anthropic_api_key,
    )

    task_desc = task["description"]
    print(f"  🔨 Implementing: {task_desc[:80]}...")

    # Get relevant existing files if any
    existing_code = ""
    files_to_check = task.get("files", [])
    for file_path in files_to_check:
        try:
            content = await get_file_contents(repo, file_path, branch)
            existing_code += f"\n--- {file_path} ---\n{content}\n"
        except Exception:
            pass  # File doesn't exist yet

    prompt = f"""Task: {task_desc}

Existing code context:
{existing_code if existing_code else 'No existing files'}

Implement this task completely. Return a JSON object with:
{{
  "files": [
    {{
      "path": "path/to/file.py",
      "content": "complete file contents",
      "message": "commit message"
    }}
  ],
  "summary": "what was implemented"
}}

Provide FULL file contents, not diffs."""

    response = await llm.ainvoke([SystemMessage(content=CODER_SYSTEM_PROMPT), HumanMessage(content=prompt)])

    # Parse response
    import json

    try:
        result = json.loads(response.content)
    except json.JSONDecodeError:
        # Fallback: treat as single file implementation
        result = {
            "files": [
                {
                    "path": task.get("files", ["implementation.py"])[0],
                    "content": response.content,
                    "message": f"Implement: {task_desc[:50]}",
                }
            ],
            "summary": task_desc,
        }

    return result


async def coder_node(state: OrchestrationState) -> dict[str, Any]:
    """Coder agent node - implements tasks in parallel."""
    settings = get_settings()
    print(f"\n{'='*80}\n💻 CODER AGENT STARTING\n{'='*80}")

    try:
        repo = state["repo"]
        tasks = state.get("tasks", [])
        retry_count = state.get("retry_count", 0)

        if not tasks:
            raise ValueError("No tasks to implement")

        # Create feature branch
        issue_number = state.get("issue_number", "feature")
        branch_name = f"ai/issue-{issue_number}-implementation"

        print(f"🌿 Creating branch: {branch_name}")
        await create_branch(repo, branch_name)

        # Implement tasks in parallel (limit concurrency)
        pending_tasks = [t for t in tasks if t.get("status") == "pending"]
        print(f"📝 Implementing {len(pending_tasks)} tasks...")

        semaphore = asyncio.Semaphore(settings.max_concurrent_agents)

        async def implement_with_limit(task: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                return await implement_task(task, repo, branch_name)

        implementations = await asyncio.gather(
            *[implement_with_limit(t) for t in pending_tasks], return_exceptions=True
        )

        # Commit all file changes
        files_changed = []
        for impl in implementations:
            if isinstance(impl, Exception):
                print(f"  ⚠️  Task failed: {impl}")
                continue

            for file_info in impl.get("files", []):
                file_path = file_info["path"]
                content = file_info["content"]
                message = file_info.get("message", f"Update {file_path}")

                print(f"  📄 Writing {file_path}...")
                await create_or_update_file(
                    repo=repo, path=file_path, content=content, message=message, branch=branch_name
                )
                files_changed.append(file_path)

        # Create pull request
        plan = state.get("plan", {})
        pr_title = f"AI Implementation: {plan.get('summary', 'Feature implementation')}"
        pr_body = f"""## 🤖 AI-Generated Implementation

### Summary
{plan.get('summary', 'Implementation based on issue requirements')}

### Architecture
{plan.get('architecture', 'N/A')[:500]}

### Files Changed
{chr(10).join(f'- `{f}`' for f in files_changed)}

### Testing
{plan.get('testing', 'Automated tests included')}

---
*Generated by AI Orchestration Platform*
*Review thoroughly before merging*
"""

        print(f"🔀 Creating pull request...")
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
                "files": files_changed,
            },
            "metadata": {"retry_count": retry_count},
            "timestamp": datetime.now(),
        }

        print(f"✅ Implementation complete: PR #{pr_number}")
        print(f"📊 Files changed: {len(files_changed)}")

        return {
            "files_changed": files_changed,
            "branches_created": [branch_name],
            "prs_created": [pr_number],
            "agent_results": [agent_result],
            "current_agent": AgentRole.CODER,
            "next_agents": [AgentRole.TESTER],
        }

    except Exception as e:
        print(f"❌ Coder failed: {e}")
        agent_result: AgentResult = {
            "agent": AgentRole.CODER,
            "status": TaskStatus.FAILED,
            "output": str(e),
            "artifacts": {},
            "metadata": {},
            "timestamp": datetime.now(),
        }
        return {"agent_results": [agent_result], "error": str(e)}
