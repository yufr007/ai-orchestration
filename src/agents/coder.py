"""Coder agent: Implement tasks in parallel and create PRs."""

import asyncio
from typing import Any

from src.agents.base import BaseAgent
from src.core.state import AgentRole, OrchestrationState, TaskStatus
from src.tools.github import GitHubTools

CODER_SYSTEM_PROMPT = """You are an elite Staff Software Engineer at a top Silicon Valley startup.

Your role:
1. Implement tasks according to the plan with production-grade quality
2. Write clean, maintainable, well-documented code
3. Follow project conventions and best practices
4. Create focused, reviewable changes

Code quality standards:
- Complete implementations (no TODOs, placeholders, or "..." ellipsis)
- Proper error handling and logging
- Type hints (Python) or types (TypeScript)
- Docstrings/comments for complex logic
- Follow existing code patterns in the repository

For each task, output:
1. File path
2. Complete file content (full file, not diffs)
3. Brief description of changes

Format your response as JSON:
{
  "task_id": "task-1",
  "files": [
    {
      "path": "src/module/file.py",
      "content": "<complete file content>",
      "description": "Added feature X with Y"
    }
  ],
  "summary": "Brief summary of implementation"
}
"""


class CoderAgent(BaseAgent):
    """Agent responsible for code implementation."""

    def __init__(self):
        super().__init__(AgentRole.CODER, CODER_SYSTEM_PROMPT)
        self.github = GitHubTools()

    async def execute(self, state: OrchestrationState) -> tuple[str, dict[str, Any]]:
        """Execute coding: implement tasks and create PR."""
        repo = state["repo"]
        tasks = state.get("tasks", [])
        plan = state.get("plan", {})
        retry_count = state.get("retry_count", 0)

        if not tasks:
            return "No tasks to implement", {}

        # Get review feedback if this is a retry
        review_feedback = None
        if retry_count > 0:
            review_comments = state.get("review_comments", [])
            test_failures = state.get("test_failures", [])
            review_feedback = {
                "comments": review_comments,
                "test_failures": test_failures,
            }

        # Create a branch for this implementation
        base_branch = await self.github.get_default_branch(repo)
        branch_name = f"ai/implement-{tasks[0]['id']}-{retry_count}"
        await self.github.create_branch(repo, branch_name, base_branch)

        # Implement tasks in parallel (up to 3 concurrent)
        semaphore = asyncio.Semaphore(3)
        implemented_files = []

        async def implement_task(task: dict) -> dict:
            async with semaphore:
                return await self._implement_single_task(repo, task, review_feedback)

        task_results = await asyncio.gather(*[implement_task(task) for task in tasks[:5]])

        # Push all files to branch
        all_files = []
        for result in task_results:
            if result.get("files"):
                all_files.extend(result["files"])
                implemented_files.extend([f["path"] for f in result["files"]])

        if all_files:
            await self.github.push_files(
                repo,
                branch_name,
                all_files,
                f"Implement: {plan.get('overview', 'AI-generated changes')}",
            )

            # Create PR
            pr_title = f"🤖 AI Implementation: {plan.get('overview', 'Changes')[:80]}"
            pr_body = self._create_pr_description(plan, tasks, task_results)

            pr_number = await self.github.create_pull_request(
                repo, branch_name, base_branch, pr_title, pr_body
            )

            return (
                f"Implemented {len(all_files)} files in PR #{pr_number}",
                {
                    "branch": branch_name,
                    "pr_number": pr_number,
                    "files": implemented_files,
                    "task_results": task_results,
                },
            )
        else:
            return "No files to implement", {}

    async def _implement_single_task(
        self, repo: str, task: dict, review_feedback: dict | None = None
    ) -> dict:
        """Implement a single task."""
        # Get existing file contents for context
        file_contexts = []
        for file_path in task.get("files", []):
            content = await self.github.get_file_contents(repo, file_path)
            if content:
                file_contexts.append(f"Existing {file_path}:\n{content}")

        # Build prompt
        user_message = f"""Task: {task['title']}
Description: {task['description']}

Acceptance Criteria:
{chr(10).join(f'- {c}' for c in task.get('acceptance_criteria', []))}

"""

        if file_contexts:
            user_message += f"\n---\nExisting Code Context:\n{chr(10).join(file_contexts)}\n"

        if review_feedback:
            user_message += f"\n---\nReview Feedback to Address:\n{review_feedback}\n"

        user_message += "\nGenerate complete, production-ready implementation."

        messages = self._format_messages(user_message)
        response = await self.llm.ainvoke(messages)

        # Parse JSON response
        import json
        import re

        response_text = response.content
        json_match = re.search(r"```json\n(.*)\n```", response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(1))
        else:
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                result = {"task_id": task["id"], "files": [], "summary": "Parse error"}

        return result

    def _create_pr_description(self, plan: dict, tasks: list, task_results: list) -> str:
        """Create PR description from plan and results."""
        description = f"## 🤖 AI-Generated Implementation\n\n"
        description += f"**Overview:** {plan.get('overview', 'N/A')}\n\n"

        description += "## 📋 Tasks Implemented\n\n"
        for task in tasks:
            description += f"- [{task.get('id')}] {task.get('title')}\n"

        description += "\n## 🏗️ Architecture Decisions\n\n"
        for decision in plan.get("architecture_decisions", []):
            description += f"- **{decision.get('decision')}**: {decision.get('rationale')}\n"

        description += "\n## ✅ Acceptance Criteria\n\n"
        for task in tasks:
            for criteria in task.get("acceptance_criteria", []):
                description += f"- [ ] {criteria}\n"

        description += "\n---\n*Generated by AI Orchestration Platform*"
        return description


async def coder_node(state: OrchestrationState) -> OrchestrationState:
    """LangGraph node for coder agent."""
    agent = CoderAgent()
    result = await agent.invoke(state)

    # Update state
    state["agent_results"].append(result)
    state["current_agent"] = AgentRole.CODER

    if result["status"] == TaskStatus.COMPLETED:
        artifacts = result["artifacts"]
        state["files_changed"].extend(artifacts.get("files", []))
        if artifacts.get("branch"):
            state["branches_created"].append(artifacts["branch"])
        if artifacts.get("pr_number"):
            state["prs_created"].append(artifacts["pr_number"])

    return state
