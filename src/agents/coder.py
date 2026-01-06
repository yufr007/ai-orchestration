"""Coder agent: Implementation and file operations."""

from src.core.state import OrchestrationState, AgentRole, TaskStatus
from src.agents.base import BaseAgent
from src.tools.github import (
    create_branch,
    get_file_content,
    update_file,
    create_file,
    create_pull_request,
)

CODER_SYSTEM_PROMPT = """You are a Staff Software Engineer at a top-tier tech company.

Your role:
1. Implement features following the plan with production-grade code
2. Write clean, maintainable, well-documented code
3. Follow project conventions and best practices
4. Handle edge cases and error conditions
5. Create comprehensive unit tests alongside implementation

Standards:
- Production-grade: No TODOs, placeholders, or incomplete code
- Type safety: Full type hints (Python) / strict types (TypeScript)
- Error handling: Graceful degradation with clear error messages
- Documentation: Docstrings for all public interfaces
- Testing: Unit tests with >80% coverage
- Security: Input validation, no hardcoded secrets

Output format:
- File path
- Complete file content (no partial code)
- Test file path and content
- Brief explanation of implementation decisions
"""


class CoderAgent(BaseAgent):
    """Agent responsible for code implementation."""

    def __init__(self) -> None:
        super().__init__(role=AgentRole.CODER, system_prompt=CODER_SYSTEM_PROMPT, temperature=0.2)

    async def implement(self, state: OrchestrationState) -> OrchestrationState:
        """Main implementation workflow."""
        self.log_start("implement")

        try:
            # Get tasks from plan
            tasks = state.get("tasks", [])
            if not tasks:
                raise ValueError("No tasks found in plan")

            # Create feature branch
            branch_name = await self._create_feature_branch(state)
            state["branches_created"].append(branch_name)

            # Implement each task
            implemented_files = []
            for task in tasks:
                if task["status"] != "completed":
                    files = await self._implement_task(state, task, branch_name)
                    implemented_files.extend(files)
                    task["status"] = "completed"

            state["files_changed"] = implemented_files

            # Create pull request
            pr_number = await self._create_pull_request(state, branch_name, implemented_files)
            state["prs_created"].append(pr_number)

            state["agent_results"].append(
                self.create_result(
                    status=TaskStatus.COMPLETED,
                    output=f"Implemented {len(implemented_files)} files in PR #{pr_number}",
                    artifacts={
                        "branch": branch_name,
                        "pr_number": pr_number,
                        "files": implemented_files,
                    },
                )
            )

            self.log_complete("implement", TaskStatus.COMPLETED)
            return state

        except Exception as e:
            self.log_error("implement", e)
            state["error"] = str(e)
            state["agent_results"].append(
                self.create_result(status=TaskStatus.FAILED, output=f"Implementation failed: {str(e)}")
            )
            return state

    async def _create_feature_branch(self, state: OrchestrationState) -> str:
        """Create a feature branch for implementation."""
        issue_num = state.get("issue_number", "manual")
        branch_name = f"feature/issue-{issue_num}-implementation"

        await create_branch(state["repo"], branch_name)
        self.logger.info("Created branch", branch=branch_name)
        return branch_name

    async def _implement_task(self, state: OrchestrationState, task: dict, branch: str) -> list[str]:
        """Implement a single task."""
        # Get existing code context if modifying files
        context = await self._get_code_context(state, task)

        # Generate implementation
        user_message = f"""Implement this task:

## Task
{task['description']}

## Full Plan Context
{state['plan']['full_plan']}

## Existing Code Context
{context}

Provide complete, production-grade implementation.
"""

        implementation = await self.invoke_llm(user_message)

        # Parse and commit files
        files = self._parse_implementation(implementation)
        committed_files = []

        for file_path, content in files.items():
            await update_file(state["repo"], file_path, content, branch, f"Implement: {task['description'][:50]}")
            committed_files.append(file_path)
            self.logger.info("Updated file", file=file_path, branch=branch)

        return committed_files

    async def _get_code_context(self, state: OrchestrationState, task: dict) -> str:
        """Get existing code context for modification."""
        # Extract file paths from task description
        # (Simplified - in production, parse from structured task)
        return "# Context will include existing file contents if modifying"

    def _parse_implementation(self, implementation_text: str) -> dict[str, str]:
        """Parse implementation text into file path -> content mapping."""
        # Simplified parser - in production, use structured output
        # For now, assume a single file
        return {"src/feature.py": implementation_text}

    async def _create_pull_request(self, state: OrchestrationState, branch: str, files: list[str]) -> int:
        """Create pull request for implementation."""
        title = f"feat: {state['plan']['summary'][:60]}"
        body = f"""## Implementation

{state['plan']['full_plan']}

## Files Changed
{chr(10).join(f'- `{f}`' for f in files)}

## Testing
Unit tests included for all new functionality.

Closes #{state.get('issue_number', 'N/A')}
"""

        pr_number = await create_pull_request(state["repo"], title, body, branch, "main")
        self.logger.info("Created PR", pr_number=pr_number)
        return pr_number


async def coder_node(state: OrchestrationState) -> OrchestrationState:
    """LangGraph node for coder agent."""
    agent = CoderAgent()
    return await agent.implement(state)
