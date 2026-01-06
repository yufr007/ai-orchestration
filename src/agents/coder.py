"""Coder agent - implements features and creates PRs."""

import asyncio
from typing import Any

from src.agents.base import BaseAgent
from src.core.state import OrchestrationState, AgentRole
from src.tools.github import (
    create_branch,
    get_file_contents,
    create_or_update_file,
    create_pull_request,
    list_repository_files,
)


class CoderAgent(BaseAgent):
    """Implements code changes based on plan."""

    def __init__(self):
        super().__init__(role=AgentRole.CODER, temperature=0.2)

    def get_system_prompt(self) -> str:
        return """You are an elite Staff Software Engineer implementing production-grade code.

Your responsibilities:
1. Implement tasks according to the plan with precision
2. Write clean, maintainable, well-documented code
3. Follow existing code patterns and conventions
4. Handle edge cases and errors gracefully
5. Add appropriate logging and type hints
6. Write self-explanatory code with minimal comments

Output format:
For each file, provide COMPLETE file content (not snippets or patches) as JSON:
{
  "files": [
    {
      "path": "src/module/file.py",
      "content": "<COMPLETE FILE CONTENT>",
      "action": "create|update",
      "message": "Brief description of changes"
    }
  ]
}

IMPORTANT:
- Provide FULL file content, not partial changes
- Maintain existing imports and structure if updating
- Ensure syntax correctness
- Follow Python/project conventions (Black formatting, type hints, docstrings)"""

    async def execute(self, state: OrchestrationState) -> dict[str, Any]:
        """Execute coding workflow."""
        repo = state["repo"]
        plan = state.get("plan")
        tasks = state.get("tasks", [])
        retry_count = state.get("retry_count", 0)

        if not tasks:
            return {
                "output": "No tasks to implement",
                "artifacts": {},
                "metadata": {"status": "skipped"},
            }

        # Create feature branch
        base_branch = "main"
        feature_branch = f"feat/ai-generated-{plan['summary'][:30].replace(' ', '-').lower()}"
        branch_created = await create_branch(repo, feature_branch, base_branch)

        if not branch_created:
            # Branch might already exist from retry
            self.logger.info(f"Branch {feature_branch} already exists, reusing")

        # Get existing files that need to be modified
        existing_files = {}
        for task in tasks:
            for file_path in task.get("files", []):
                if file_path not in existing_files:
                    content = await get_file_contents(repo, file_path, ref=feature_branch)
                    if content:
                        existing_files[file_path] = content

        # Generate implementation for all tasks
        tasks_description = "\n\n".join(
            [
                f"Task {t['id']}: {t['title']}\n"
                f"Type: {t['type']}\n"
                f"Files: {', '.join(t['files'])}\n"
                f"Acceptance: {', '.join(t['acceptance_criteria'])}"
                for t in tasks
            ]
        )

        user_message = f"""Implement the following tasks:

{tasks_description}

Plan Summary: {plan['summary']}
Approach: {plan['approach']}

Existing Files:
{self._format_existing_files(existing_files)}

Generate COMPLETE file content for all files that need to be created or modified.
Return JSON with the 'files' array as specified."""

        if retry_count > 0:
            # Include test failure information if retrying
            test_failures = state.get("test_failures", [])
            review_comments = state.get("review_comments", [])
            user_message += f"\n\nPrevious Issues (Retry #{retry_count}):\n"
            if test_failures:
                user_message += f"Test Failures: {test_failures}\n"
            if review_comments:
                user_message += f"Review Comments: {review_comments}\n"

        implementation_json = await self._call_llm(self.get_system_prompt(), user_message)

        # Parse implementation
        import json

        try:
            if "```json" in implementation_json:
                implementation_json = (
                    implementation_json.split("```json")[1].split("```")[0].strip()
                )
            elif "```" in implementation_json:
                implementation_json = implementation_json.split("```")[1].split("```")[0].strip()

            implementation = json.loads(implementation_json)
            files_to_commit = implementation.get("files", [])
        except json.JSONDecodeError:
            self.logger.error("Failed to parse implementation JSON")
            return {
                "output": "Failed to parse implementation",
                "artifacts": {"raw_response": implementation_json},
                "metadata": {"status": "failed"},
            }

        # Commit files to branch
        files_changed = []
        commit_tasks = []
        for file_spec in files_to_commit:
            path = file_spec["path"]
            content = file_spec["content"]
            message = file_spec.get("message", f"Implement {path}")

            commit_tasks.append(
                create_or_update_file(repo, path, content, message, branch=feature_branch)
            )
            files_changed.append(path)

        # Execute commits in parallel
        await asyncio.gather(*commit_tasks)

        # Create PR
        pr_title = f"[AI] {plan['summary']}"
        pr_body = f"""## Implementation Plan

{plan['approach']}

## Tasks Completed

{chr(10).join([f"- {t['title']}" for t in tasks])}

## Files Changed

{chr(10).join([f"- `{f}`" for f in files_changed])}

## Notes

{plan.get('research_notes', 'N/A')}

---
*Generated by AI Orchestration Platform*
"""

        pr_number = await create_pull_request(
            repo, feature_branch, base_branch, pr_title, pr_body
        )

        return {
            "output": f"Created PR #{pr_number} with {len(files_changed)} files",
            "files_changed": files_changed,
            "branches_created": state.get("branches_created", []) + [feature_branch],
            "prs_created": state.get("prs_created", []) + [pr_number],
            "retry_count": retry_count + 1,
            "artifacts": {
                "pr_number": pr_number,
                "pr_url": f"https://github.com/{repo}/pull/{pr_number}",
                "branch": feature_branch,
            },
            "metadata": {
                "files_count": len(files_changed),
                "tasks_implemented": len(tasks),
            },
        }

    def _format_existing_files(self, files: dict[str, str]) -> str:
        """Format existing file contents for context."""
        if not files:
            return "No existing files (all new files)"

        result = []
        for path, content in files.items():
            result.append(f"--- {path} ---\n{content[:1000]}...\n")
        return "\n".join(result)


async def coder_node(state: OrchestrationState) -> dict[str, Any]:
    """LangGraph node for coder agent."""
    agent = CoderAgent()
    return await agent.invoke(state)
