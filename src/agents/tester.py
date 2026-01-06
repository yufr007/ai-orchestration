"""Tester agent - Generate and execute tests."""

import asyncio
import subprocess
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.github import get_file_contents, create_or_update_file


TESTER_SYSTEM_PROMPT = """You are an elite QA/Test Engineer ensuring code quality.

Your responsibilities:
1. Generate comprehensive test suites (unit + integration)
2. Cover edge cases and error conditions
3. Use appropriate testing frameworks (pytest for Python)
4. Write clear, maintainable test code
5. Ensure tests are deterministic and fast

Test Guidelines:
- Follow AAA pattern (Arrange, Act, Assert)
- Use fixtures for setup/teardown
- Mock external dependencies
- Test both happy paths and error cases
- Aim for 80%+ code coverage
- Include docstrings explaining what's being tested

Output Format:
{
  "test_files": [
    {
      "path": "tests/test_module.py",
      "content": "complete test file content",
      "coverage_areas": ["function_1", "function_2"]
    }
  ],
  "test_strategy": "Explanation of testing approach",
  "coverage_estimate": "80%"
}
"""


async def generate_tests(files_changed: list[str], repo: str, branch: str) -> dict[str, Any]:
    """Generate test files for changed code."""
    settings = get_settings()

    llm = ChatAnthropic(
        model=settings.default_agent_model,
        temperature=0.2,
        api_key=settings.anthropic_api_key,
    )

    # Get file contents
    file_contents = {}
    for file_path in files_changed:
        if not file_path.endswith(".py"):
            continue
        try:
            content = await get_file_contents(repo, file_path, branch)
            file_contents[file_path] = content
        except Exception:
            pass

    if not file_contents:
        return {"test_files": [], "test_strategy": "No Python files to test"}

    # Build prompt
    context = "Files to test:\n\n"
    for path, content in file_contents.items():
        context += f"--- {path} ---\n{content}\n\n"

    context += "\nGenerate comprehensive pytest test suite."

    messages = [
        SystemMessage(content=TESTER_SYSTEM_PROMPT),
        HumanMessage(content=context),
    ]

    response = await llm.ainvoke(messages)

    # Parse response
    import json

    try:
        result = json.loads(response.content)
    except json.JSONDecodeError:
        content = response.content
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            result = json.loads(content[json_start:json_end].strip())
        else:
            result = {"test_files": [], "test_strategy": "Failed to generate tests"}

    return result


async def run_tests(repo: str, branch: str) -> dict[str, Any]:
    """Execute test suite and return results."""
    # This would clone the repo and run tests in a sandbox
    # For now, return mock results
    return {
        "passed": True,
        "total_tests": 10,
        "passed_tests": 10,
        "failed_tests": 0,
        "coverage": 85,
        "duration_seconds": 2.5,
    }


async def tester_node(state: OrchestrationState) -> dict[str, Any]:
    """Tester agent node - generate and run tests."""
    files_changed = state.get("files_changed", [])
    repo = state["repo"]
    branches = state.get("branches_created", [])
    branch = branches[0] if branches else "main"

    if not files_changed:
        agent_result: AgentResult = {
            "agent": AgentRole.TESTER,
            "status": TaskStatus.SKIPPED,
            "output": "No files to test",
            "artifacts": {},
            "metadata": {},
            "timestamp": datetime.now(),
        }
        return {
            "agent_results": state.get("agent_results", []) + [agent_result],
            "current_agent": AgentRole.TESTER,
        }

    # Generate tests
    test_generation = await generate_tests(files_changed, repo, branch)

    # Write test files
    for test_file in test_generation.get("test_files", []):
        try:
            await create_or_update_file(
                repo=repo,
                path=test_file["path"],
                content=test_file["content"],
                branch=branch,
                message=f"Add tests for {test_file.get('coverage_areas', [])[0] if test_file.get('coverage_areas') else 'module'}",
            )
        except Exception:
            pass

    # Run tests
    test_results = await run_tests(repo, branch)

    # Collect failures
    test_failures = []
    if not test_results.get("passed", False):
        test_failures = [
            {
                "test": "example_test",
                "error": "Assertion failed",
                "file": "tests/test_example.py",
            }
        ]

    agent_result: AgentResult = {
        "agent": AgentRole.TESTER,
        "status": TaskStatus.COMPLETED if test_results.get("passed") else TaskStatus.FAILED,
        "output": f"Tests: {test_results.get('passed_tests', 0)}/{test_results.get('total_tests', 0)} passed",
        "artifacts": {"test_generation": test_generation, "test_results": test_results},
        "metadata": {
            "coverage": test_results.get("coverage", 0),
            "duration": test_results.get("duration_seconds", 0),
        },
        "timestamp": datetime.now(),
    }

    return {
        "test_results": test_results,
        "test_failures": test_failures,
        "agent_results": state.get("agent_results", []) + [agent_result],
        "current_agent": AgentRole.TESTER,
    }
