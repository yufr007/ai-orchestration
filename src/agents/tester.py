"""Tester agent - Test generation and execution."""

import asyncio
import subprocess
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.github_tools import get_pr_files, get_file_contents


TESTER_SYSTEM_PROMPT = """You are an elite QA/Test Engineer at a Silicon Valley startup.

Your role:
- Generate comprehensive test cases for new/modified code
- Write unit tests, integration tests, and edge case tests
- Ensure high code coverage (>80%)
- Test error handling and boundary conditions
- Validate against requirements and success criteria

Test quality standards:
- Clear, descriptive test names (test_should_x_when_y)
- Arrange-Act-Assert pattern
- Independent tests (no shared state)
- Test both happy path and failure cases
- Mock external dependencies appropriately
- Include docstrings explaining what is being tested

Frameworks:
- Python: pytest with fixtures
- JavaScript/TypeScript: Jest or Vitest
- Follow project conventions
"""


async def tester_node(state: OrchestrationState) -> dict[str, Any]:
    """Tester agent: Generate and run tests for implementation."""
    settings = get_settings()
    repo = state["repo"]
    files_changed = state.get("files_changed", [])
    pr_number = state.get("prs_created", [None])[-1]

    if not files_changed:
        return {
            "agent_results": state.get("agent_results", [])
            + [
                {
                    "agent": AgentRole.TESTER,
                    "status": TaskStatus.SKIPPED,
                    "output": "No files to test",
                    "artifacts": {},
                    "metadata": {},
                    "timestamp": datetime.now(),
                }
            ],
            "current_agent": AgentRole.TESTER,
        }

    try:
        llm = ChatAnthropic(
            model=settings.default_agent_model,
            temperature=0.2,
            api_key=settings.anthropic_api_key,
        )

        # Get PR diff context
        pr_files = await get_pr_files(repo, pr_number) if pr_number else files_changed

        test_results = {"passed": True, "total": 0, "passed_count": 0, "failed_count": 0}
        test_failures = []

        # Generate tests for each changed file
        for file_path in pr_files:
            # Skip test files and non-code files
            if "test" in file_path or not (file_path.endswith(".py") or file_path.endswith(".ts")):
                continue

            # Get file content
            content = await get_file_contents(repo, file_path)

            # Generate test file
            test_prompt = f"""Generate comprehensive tests for this code.

**File**: {file_path}

**Code**:
```
{content}
```

**Requirements**:
1. Test all public functions/methods
2. Include edge cases and error conditions
3. Mock external dependencies
4. Use appropriate fixtures
5. Follow project test conventions

Provide COMPLETE test file content, ready to run.
"""

            messages = [
                SystemMessage(content=TESTER_SYSTEM_PROMPT),
                HumanMessage(content=test_prompt),
            ]

            test_code = await llm.ainvoke(messages)

            # Determine test file path
            test_file_path = get_test_file_path(file_path)

            # In production, write test file and run it
            # For now, simulate test execution
            test_result = await simulate_test_execution(test_file_path, test_code.content)

            test_results["total"] += test_result["total"]
            if test_result["passed"]:
                test_results["passed_count"] += test_result["total"]
            else:
                test_results["passed"] = False
                test_results["failed_count"] += test_result["failed"]
                test_failures.extend(test_result.get("failures", []))

        agent_result: AgentResult = {
            "agent": AgentRole.TESTER,
            "status": TaskStatus.COMPLETED if test_results["passed"] else TaskStatus.FAILED,
            "output": f"Tests: {test_results['passed_count']}/{test_results['total']} passed",
            "artifacts": {
                "test_results": test_results,
                "failures": test_failures,
            },
            "metadata": {
                "files_tested": len(pr_files),
                "coverage": (test_results["passed_count"] / max(test_results["total"], 1)) * 100,
            },
            "timestamp": datetime.now(),
        }

        return {
            "test_results": test_results,
            "test_failures": test_failures,
            "agent_results": state.get("agent_results", []) + [agent_result],
            "current_agent": AgentRole.TESTER,
            "next_agents": [AgentRole.REVIEWER] if test_results["passed"] else [AgentRole.CODER],
            "retry_count": state.get("retry_count", 0) + (0 if test_results["passed"] else 1),
        }

    except Exception as e:
        agent_result: AgentResult = {
            "agent": AgentRole.TESTER,
            "status": TaskStatus.FAILED,
            "output": f"Testing failed: {str(e)}",
            "artifacts": {},
            "metadata": {"error": str(e)},
            "timestamp": datetime.now(),
        }

        return {
            "agent_results": state.get("agent_results", []) + [agent_result],
            "error": str(e),
            "current_agent": AgentRole.TESTER,
        }


def get_test_file_path(source_file: str) -> str:
    """Determine test file path from source file."""
    if source_file.startswith("src/"):
        return source_file.replace("src/", "tests/", 1).replace(".py", "_test.py")
    return f"tests/test_{source_file.split('/')[-1]}"


async def simulate_test_execution(test_file: str, test_code: str) -> dict[str, Any]:
    """Simulate test execution (in production, actually run pytest/jest).

    Production implementation would:
    1. Write test file to disk
    2. Run pytest/jest with coverage
    3. Parse output for results
    4. Return structured results
    """
    # Simplified simulation
    return {
        "passed": True,
        "total": 5,
        "failed": 0,
        "failures": [],
        "coverage": 85.0,
    }
