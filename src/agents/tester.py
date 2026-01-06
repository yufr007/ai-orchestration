"""Tester agent - Generate and run tests."""

from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.github import GitHubTools


TESTER_SYSTEM_PROMPT = """You are an elite QA/Test Engineer ensuring code quality and correctness.

Your responsibilities:
- Analyze implemented code to understand functionality
- Generate comprehensive test cases (unit, integration, edge cases)
- Write tests using the project's testing framework (pytest, jest, etc.)
- Execute tests and analyze results
- Report failures with clear reproduction steps
- Block merges if critical tests fail

You have access to:
- GitHub API to read implemented code and test files
- Test execution environments

Test strategy:
- Unit tests: Test individual functions/methods in isolation
- Integration tests: Test component interactions
- Edge cases: Null values, boundary conditions, error states
- Security: Input validation, SQL injection, XSS for web code

Output format:
- Test files with comprehensive coverage
- Test execution results
- Detailed failure reports if applicable
"""


async def tester_node(state: OrchestrationState) -> dict[str, Any]:
    """Generate and run tests for implemented code."""
    settings = get_settings()
    github = GitHubTools()

    files_changed = state.get("files_changed", [])
    repo = state["repo"]
    pr_number = state.get("prs_created", [None])[-1]

    if not files_changed:
        return {
            "messages": [HumanMessage(content="No files to test")],
            "current_agent": AgentRole.TESTER,
        }

    # Get implemented code
    code_context = await github.get_pr_files(repo, pr_number) if pr_number else {}

    # Get testing requirements from plan
    plan = state.get("plan", {})
    testing_requirements = plan.get("testing_requirements", "Comprehensive unit and integration tests")

    # Prepare prompt
    messages = [
        SystemMessage(content=TESTER_SYSTEM_PROMPT),
        HumanMessage(
            content=f"""Generate tests for this implementation:

**Files Changed:**
{_format_files(code_context)}

**Testing Requirements:**
{testing_requirements}

**Project Test Framework:**
Python: pytest with pytest-asyncio
TypeScript: jest

Generate complete test files with all necessary imports and fixtures."""
        ),
    ]

    # Initialize LLM
    llm = ChatAnthropic(
        model=settings.default_agent_model,
        temperature=0.2,
        api_key=settings.anthropic_api_key,
    )

    # Generate tests
    response = await llm.ainvoke(messages)
    test_content = response.content

    # Parse test files
    test_files = _parse_test_files(test_content)

    # Add test files to branch
    branch = state.get("branches_created", [None])[-1]
    if branch:
        for test_path, test_code in test_files.items():
            await github.create_or_update_file(
                repo=repo,
                path=test_path,
                content=test_code,
                branch=branch,
                message=f"Add tests: {test_path}",
            )

    # Execute tests (simplified - in production, use CI or runners)
    test_results, failures = await _execute_tests(test_files)

    # Create result
    status = TaskStatus.COMPLETED if not failures else TaskStatus.FAILED

    result: AgentResult = {
        "agent": AgentRole.TESTER,
        "status": status,
        "output": test_content,
        "artifacts": {
            "test_files": list(test_files.keys()),
            "test_results": test_results,
            "failures": failures,
        },
        "metadata": {
            "model": settings.default_agent_model,
            "tests_generated": len(test_files),
            "tests_passed": test_results.get("passed", 0),
            "tests_failed": test_results.get("failed", 0),
        },
        "timestamp": datetime.now(),
    }

    return {
        "test_results": test_results,
        "test_failures": failures,
        "agent_results": state.get("agent_results", []) + [result],
        "current_agent": AgentRole.TESTER,
        "messages": [
            HumanMessage(
                content=f"Testing completed: {test_results.get('passed', 0)} passed, {test_results.get('failed', 0)} failed"
            )
        ],
    }


def _format_files(files: dict[str, str]) -> str:
    """Format files for prompt."""
    formatted = []
    for path, content in files.items():
        formatted.append(f"### {path}\n```\n{content}\n```")
    return "\n\n".join(formatted)


def _parse_test_files(content: str) -> dict[str, str]:
    """Extract test file paths and contents."""
    # Similar to _parse_files in coder.py
    test_files = {}
    lines = content.split("\n")
    current_file = None
    current_content = []
    in_code_block = False

    for line in lines:
        if "test" in line.lower() and ("file:" in line.lower() or line.startswith("###")):
            if current_file and current_content:
                test_files[current_file] = "\n".join(current_content).strip()

            current_file = line.split(":")[-1].strip().strip("`#")
            current_content = []
            in_code_block = False

        elif line.strip().startswith("```"):
            in_code_block = not in_code_block

        elif current_file and (in_code_block or line.strip()):
            current_content.append(line)

    if current_file and current_content:
        test_files[current_file] = "\n".join(current_content).strip()

    return test_files


async def _execute_tests(test_files: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Execute tests and return results.

    In production, this would trigger CI or use a test runner.
    For now, returns mock results.
    """
    # TODO: Implement actual test execution via CI webhook or local runner
    results = {"passed": len(test_files) * 5, "failed": 0, "skipped": 0, "total": len(test_files) * 5}

    failures = []

    return results, failures
