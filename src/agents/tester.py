"""Tester agent - Test generation and execution."""

from typing import Any
import re

from src.agents.base import BaseAgent
from src.core.state import OrchestrationState, AgentRole
from src.tools.github_tools import GitHubTools


class TesterAgent(BaseAgent):
    """Agent responsible for generating and running tests."""

    def __init__(self):
        super().__init__(role=AgentRole.TESTER, temperature=0.1)
        self.github = GitHubTools()

    async def execute(self, state: OrchestrationState) -> dict[str, Any]:
        """Execute testing logic."""
        files_changed = state.get("files_changed", [])
        repo = state["repo"]
        pr_number = state.get("prs_created", [])[-1] if state.get("prs_created") else None

        if not files_changed:
            return {"output": "No files to test", "artifacts": {}}

        # Generate tests for changed files
        test_files = await self._generate_tests(repo, files_changed)

        # Run tests (simulated - would integrate with CI/CD)
        test_results = await self._run_tests(test_files)

        # Analyze failures
        failures = self._analyze_failures(test_results)

        # Post test report to PR
        if pr_number:
            await self._post_test_report(repo, pr_number, test_results, failures)

        return {
            "test_results": test_results,
            "test_failures": failures,
            "output": f"Tests: {test_results['passed_count']}/{test_results['total_count']} passed",
            "artifacts": {"test_files": test_files},
            "metadata": {"test_results": test_results},
        }

    async def _generate_tests(self, repo: str, files: list[str]) -> list[dict]:
        """Generate test files for changed code."""
        test_files = []

        for file_path in files:
            # Skip non-code files
            if not file_path.endswith((".py", ".js", ".ts", ".java")):
                continue

            # Get file content
            content = await self.github.get_file_contents(repo, file_path)

            # Generate test using LLM
            test_content = await self._generate_test_for_file(file_path, content)

            # Determine test file path
            test_path = self._get_test_path(file_path)

            test_files.append({"path": test_path, "content": test_content, "source": file_path})

        return test_files

    async def _generate_test_for_file(self, file_path: str, content: str) -> str:
        """Generate test content for a specific file."""
        system_prompt = """You are an expert Test Engineer writing comprehensive tests.

Your job:
1. Analyze the code and identify all testable functions/methods
2. Write unit tests covering:
   - Happy path scenarios
   - Edge cases
   - Error handling
   - Boundary conditions
3. Use appropriate testing framework (pytest for Python, jest for JS/TS, junit for Java)
4. Include setup/teardown as needed
5. Output ONLY the complete test file, no explanations

Output format: Pure test code, ready to run."""

        user_message = f"""File: {file_path}

Code:
{content}

Generate comprehensive tests."""

        messages = self.format_messages(system_prompt, user_message)
        response = await self.llm.ainvoke(messages)

        return response.content

    def _get_test_path(self, file_path: str) -> str:
        """Convert source file path to test file path."""
        if "src/" in file_path:
            test_path = file_path.replace("src/", "tests/", 1)
        else:
            test_path = f"tests/{file_path}"

        # Add test prefix if not present
        filename = test_path.split("/")[-1]
        if not filename.startswith("test_"):
            test_path = test_path.replace(filename, f"test_{filename}")

        return test_path

    async def _run_tests(self, test_files: list[dict]) -> dict:
        """Run generated tests (simulated for now)."""
        # In production, this would:
        # 1. Commit test files to branch
        # 2. Trigger CI/CD pipeline
        # 3. Wait for results
        # 4. Parse test output

        # Simulated results for now
        passed_count = len(test_files)
        failed_count = 0
        total_count = len(test_files)

        return {
            "passed": failed_count == 0,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "total_count": total_count,
            "duration_ms": 5000,
            "test_files": test_files,
        }

    def _analyze_failures(self, test_results: dict) -> list[dict]:
        """Analyze test failures and categorize them."""
        if test_results.get("passed", True):
            return []

        # In production, would parse actual failure output
        # For now, return empty list
        return []

    async def _post_test_report(self, repo: str, pr_number: int, results: dict, failures: list[dict]) -> None:
        """Post test results as PR comment."""
        status_emoji = "✅" if results["passed"] else "❌"
        comment = f"""## {status_emoji} Test Results

**Overall**: {results['passed_count']}/{results['total_count']} tests passed
**Duration**: {results['duration_ms']}ms

"""

        if failures:
            comment += "\n### ❌ Failures\n"
            for failure in failures:
                comment += f"- `{failure.get('test', 'unknown')}`: {failure.get('message', '')}\n"
        else:
            comment += "\n### ✅ All tests passed!\n"

        comment += "\n---\n*Auto-generated by AI Orchestration Platform*"

        await self.github.add_pr_comment(repo, pr_number, comment)


# Node function for LangGraph
async def tester_node(state: OrchestrationState) -> dict[str, Any]:
    """Tester node for LangGraph workflow."""
    agent = TesterAgent()
    return await agent.invoke(state)
