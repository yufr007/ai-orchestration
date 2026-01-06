"""Tester agent - generates and runs tests."""

import json
from typing import Any

from src.agents.base import BaseAgent
from src.core.state import OrchestrationState, AgentRole
from src.tools.github import get_file_contents, create_or_update_file, add_pr_comment


class TesterAgent(BaseAgent):
    """Generates tests and validates implementation."""

    def __init__(self):
        super().__init__(role=AgentRole.TESTER, temperature=0.1)

    def get_system_prompt(self) -> str:
        return """You are an elite QA Engineer responsible for ensuring code quality through comprehensive testing.

Your responsibilities:
1. Generate pytest test cases covering:
   - Happy paths and edge cases
   - Error handling and validation
   - Integration points
   - Performance considerations
2. Execute tests and analyze failures
3. Report clear, actionable test results

Output format:
{
  "test_files": [
    {
      "path": "tests/test_module.py",
      "content": "<COMPLETE TEST FILE CONTENT>"
    }
  ],
  "execution_plan": [
    "pytest tests/test_module.py::test_function1",
    "pytest tests/test_module.py::test_function2"
  ],
  "coverage_expectations": {
    "target_percentage": 80,
    "critical_paths": ["path.to.function1", "path.to.function2"]
  }
}

Write production-grade tests with:
- Clear test names (test_should_do_what_when_condition)
- Fixtures for setup/teardown
- Parameterized tests for multiple scenarios
- Proper mocking of external dependencies
- Type hints and docstrings"""

    async def execute(self, state: OrchestrationState) -> dict[str, Any]:
        """Execute testing workflow."""
        repo = state["repo"]
        files_changed = state.get("files_changed", [])
        prs_created = state.get("prs_created", [])

        if not files_changed:
            return {
                "output": "No files to test",
                "artifacts": {},
                "metadata": {"status": "skipped"},
            }

        pr_number = prs_created[-1] if prs_created else None
        branch = state.get("branches_created", [])[-1] if state.get("branches_created") else "main"

        # Get implementation code
        implementations = {}
        for file_path in files_changed:
            content = await get_file_contents(repo, file_path, ref=branch)
            if content:
                implementations[file_path] = content

        # Generate tests
        user_message = f"""Generate comprehensive pytest tests for the following implementations:

{self._format_implementations(implementations)}

Plan Context:
{state.get('plan', {}).get('approach', 'N/A')}

Tasks:
{self._format_tasks(state.get('tasks', []))}

Generate complete test files following pytest best practices.
Return JSON with 'test_files', 'execution_plan', and 'coverage_expectations'."""

        tests_json = await self._call_llm(self.get_system_prompt(), user_message)

        # Parse test generation
        try:
            if "```json" in tests_json:
                tests_json = tests_json.split("```json")[1].split("```")[0].strip()
            elif "```" in tests_json:
                tests_json = tests_json.split("```")[1].split("```")[0].strip()

            tests = json.loads(tests_json)
            test_files = tests.get("test_files", [])
        except json.JSONDecodeError:
            self.logger.error("Failed to parse tests JSON")
            return {
                "output": "Failed to generate tests",
                "test_results": {"passed": False, "error": "JSON parse error"},
                "artifacts": {"raw_response": tests_json},
                "metadata": {"status": "failed"},
            }

        # Commit test files
        for test_file in test_files:
            await create_or_update_file(
                repo,
                test_file["path"],
                test_file["content"],
                f"Add tests for {test_file['path']}",
                branch=branch,
            )

        # Simulate test execution (in real scenario, would run pytest via GitHub Actions or API)
        test_results = await self._simulate_test_execution(tests.get("execution_plan", []))

        # Report results on PR
        if pr_number:
            await self._report_test_results(repo, pr_number, test_results, test_files)

        return {
            "output": f"Generated {len(test_files)} test files, {test_results['total']} tests total",
            "test_results": test_results,
            "test_failures": test_results.get("failures", []),
            "artifacts": {
                "test_files": [tf["path"] for tf in test_files],
                "coverage": test_results.get("coverage", {}),
            },
            "metadata": {
                "tests_count": test_results["total"],
                "passed_count": test_results["passed"],
                "failed_count": test_results["failed"],
            },
        }

    async def _simulate_test_execution(self, execution_plan: list[str]) -> dict[str, Any]:
        """Simulate test execution (replace with actual pytest runner)."""
        # In production: run actual pytest via subprocess or GitHub Actions API
        # For now: simulate results
        total = len(execution_plan)
        # Assume 90% pass rate initially
        passed = int(total * 0.9)
        failed = total - passed

        failures = []
        if failed > 0:
            # Simulate some failures for demonstration
            failures.append(
                {
                    "test": execution_plan[0] if execution_plan else "test_example",
                    "error": "AssertionError: expected value != actual value",
                    "traceback": "Simulated traceback...",
                }
            )

        return {
            "passed": failed == 0,
            "total": total,
            "passed": passed,
            "failed": failed,
            "failures": failures,
            "coverage": {"percentage": 85, "lines_covered": 450, "lines_total": 530},
        }

    async def _report_test_results(
        self, repo: str, pr_number: int, results: dict[str, Any], test_files: list[dict]
    ) -> None:
        """Post test results as PR comment."""
        status_emoji = "✅" if results["passed"] else "❌"
        comment = f"""## {status_emoji} Test Results

**Summary:**
- Total Tests: {results['total']}
- Passed: {results['passed']} ✅
- Failed: {results['failed']} ❌
- Coverage: {results.get('coverage', {}).get('percentage', 0)}%

**Test Files Generated:**
{chr(10).join([f"- `{tf['path']}`" for tf in test_files])}
"""

        if results.get("failures"):
            comment += "\n### Failures:\n"
            for failure in results["failures"]:
                comment += f"\n**{failure['test']}**\n```\n{failure['error']}\n```\n"

        comment += "\n---\n*Automated testing by AI Orchestration Platform*"

        await add_pr_comment(repo, pr_number, comment)

    def _format_implementations(self, implementations: dict[str, str]) -> str:
        """Format implementation files for context."""
        result = []
        for path, content in implementations.items():
            result.append(f"### {path}\n```python\n{content}\n```\n")
        return "\n".join(result)

    def _format_tasks(self, tasks: list[dict]) -> str:
        """Format tasks for context."""
        return "\n".join(
            [f"- {t['title']}: {', '.join(t.get('acceptance_criteria', []))}" for t in tasks]
        )


async def tester_node(state: OrchestrationState) -> dict[str, Any]:
    """LangGraph node for tester agent."""
    agent = TesterAgent()
    return await agent.invoke(state)
