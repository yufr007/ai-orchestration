"""Coder Agent - Implementation with parallel file operations."""

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


CODER_SYSTEM_PROMPT = """You are an elite Staff Engineer implementing production-grade code.

Your responsibilities:
1. Implement tasks according to the plan with enterprise standards
2. Write clean, maintainable, well-documented code
3. Follow project conventions and best practices
4. Handle edge cases and errors gracefully
5. Ensure backward compatibility

Code Quality Standards:
- Type hints for all functions (Python)
- Comprehensive docstrings
- Error handling with specific exceptions
- Input validation
- Logging for debugging
- No hardcoded values (use config)

Output Format:
For each file, provide:
{
  "path": "path/to/file.py",
  "content": "complete file content",
  "operation": "create" or "update",
  "description": "what this file does"
}

Return a JSON array of file operations.
"""


async def implement_task(llm: ChatAnthropic, task: dict[str, Any], repo: str) -> list[dict[str, Any]]:
    """Implement a single task and return file operations."""
    print(f"  ⚙️  Implementing: {task.get('title', task.get('id'))}")
    
    # Get existing file contents for files to modify
    file_contexts = []
    for file_path in task.get("files", []):
        try:
            content = await get_file_contents(repo=repo, path=file_path)
            file_contexts.append(f"### {file_path}\n```\n{content}\n```")
        except Exception:
            file_contexts.append(f"### {file_path}\n(New file - does not exist yet)")
    
    files_context = "\n\n".join(file_contexts) if file_contexts else "No existing files."
    
    # Generate implementation
    messages = [
        SystemMessage(content=CODER_SYSTEM_PROMPT),
        HumanMessage(content=f"""Implement the following task:

**Task**: {task.get('title', 'Untitled')}
**Description**: {task.get('description', '')}
**Acceptance Criteria**:
{chr(10).join('- ' + c for c in task.get('acceptance_criteria', []))}

**Existing Files**:
{files_context}

Provide complete file implementations as a JSON array."""),
    ]
    
    response = await llm.ainvoke(messages)
    
    # Parse file operations
    import json
    response_text = response.content
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()
    
    try:
        file_ops = json.loads(response_text)
        if not isinstance(file_ops, list):
            file_ops = [file_ops]
    except json.JSONDecodeError:
        # Fallback: single file from task
        file_ops = [{
            "path": task.get("files", ["unknown.py"])[0],
            "content": response_text,
            "operation": "create",
            "description": task.get("title", "Implementation"),
        }]
    
    return file_ops


async def coder_node(state: OrchestrationState) -> dict[str, Any]:
    """Coder agent: Implement tasks with parallel file operations."""
    settings = get_settings()
    
    print("\n👨‍💻 CODER: Starting implementation phase...")
    
    # Initialize LLM
    llm = ChatAnthropic(
        model=settings.default_agent_model,
        temperature=0.2,
        api_key=settings.anthropic_api_key,
    )
    
    tasks = state.get("tasks", [])
    if not tasks:
        print("⚠️  No tasks to implement")
        return {"error": "No tasks provided"}
    
    # Create feature branch
    branch_name = f"ai/feature-{state.get('issue_number', 'auto')}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    print(f"🌿 Creating branch: {branch_name}")
    
    try:
        await create_branch(
            repo=state["repo"],
            branch=branch_name,
            from_branch="main",
        )
    except Exception as e:
        print(f"⚠️  Branch creation failed (may already exist): {e}")
    
    # Implement tasks in parallel (up to max_concurrent)
    print(f"📦 Implementing {len(tasks)} tasks in parallel...")
    
    semaphore = asyncio.Semaphore(min(3, len(tasks)))  # Max 3 parallel
    
    async def implement_with_semaphore(task: dict[str, Any]) -> list[dict[str, Any]]:
        async with semaphore:
            return await implement_task(llm, task, state["repo"])
    
    task_results = await asyncio.gather(
        *[implement_with_semaphore(task) for task in tasks],
        return_exceptions=True,
    )
    
    # Collect all file operations
    all_file_ops: list[dict[str, Any]] = []
    for result in task_results:
        if isinstance(result, Exception):
            print(f"❌ Task failed: {result}")
            continue
        all_file_ops.extend(result)
    
    # Apply file operations to branch
    print(f"💾 Writing {len(all_file_ops)} files to branch...")
    files_changed = []
    
    for file_op in all_file_ops:
        try:
            await create_or_update_file(
                repo=state["repo"],
                path=file_op["path"],
                content=file_op["content"],
                branch=branch_name,
                message=f"Implement: {file_op.get('description', 'Update file')}",
            )
            files_changed.append(file_op["path"])
            print(f"  ✅ {file_op['path']}")
        except Exception as e:
            print(f"  ❌ {file_op['path']}: {e}")
    
    # Create pull request
    pr_number = None
    if files_changed and state.get("mode") != "plan":
        print("📬 Creating pull request...")
        plan = state.get("plan", {})
        pr_body = f"""## Summary
{plan.get('summary', 'AI-generated implementation')}

## Tasks Completed
{chr(10).join(f"- {task.get('title', task.get('id'))}" for task in tasks)}

## Files Changed
{chr(10).join(f"- `{f}`" for f in files_changed)}

---
*Generated by AI Orchestration Platform*
"""
        
        try:
            pr_data = await create_pull_request(
                repo=state["repo"],
                head=branch_name,
                base="main",
                title=f"AI: {plan.get('summary', 'Implementation')[:80]}",
                body=pr_body,
                draft=True,
            )
            pr_number = pr_data.get("number")
            print(f"✅ Pull request created: #{pr_number}")
        except Exception as e:
            print(f"❌ PR creation failed: {e}")
    
    # Create agent result
    agent_result: AgentResult = {
        "agent": AgentRole.CODER,
        "status": TaskStatus.COMPLETED if files_changed else TaskStatus.FAILED,
        "output": f"Implemented {len(files_changed)} files",
        "artifacts": {
            "branch": branch_name,
            "files": files_changed,
            "pr_number": pr_number,
        },
        "metadata": {
            "tasks_count": len(tasks),
            "files_changed_count": len(files_changed),
        },
        "timestamp": datetime.now(),
    }
    
    return {
        "files_changed": files_changed,
        "branches_created": [*state.get("branches_created", []), branch_name],
        "prs_created": [*state.get("prs_created", []), pr_number] if pr_number else state.get("prs_created", []),
        "agent_results": [*state.get("agent_results", []), agent_result],
        "current_agent": AgentRole.CODER,
        "retry_count": state.get("retry_count", 0),
    }
