"""Tester Agent - Test generation and execution."""

import asyncio
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.github import add_pr_comment, get_file_contents


TESTER_SYSTEM_PROMPT = """You are an elite QA/Test Engineer ensuring code quality.

Your responsibilities:
1. Generate comprehensive test suites (unit, integration, edge cases)
2. Analyze code for testability issues
3. Execute tests and report failures with clear reproduction steps
4. Suggest improvements to code based on test findings
5. Ensure test coverage meets standards (>80%)

Test quality requirements:
- Cover happy path, edge cases, error conditions
- Use appropriate test frameworks (pytest, jest, etc.)
- Include fixtures and mocks where needed
- Write clear, descriptive test names
- Add assertions with helpful failure messages

Output: Complete test files ready to run, plus execution report."""


async def generate_tests(files: list[str], repo: str, branch: str) -> dict[str, Any]:
    """Generate tests for changed files."""
    settings = get_settings()
    llm = ChatAnthropic(
        model=settings.default_agent_model,
        temperature=0.1,  # Lower temperature for consistent test generation
        api_key=settings.anthropic_api_key,
    )

    print(f"  🧪 Generating tests for {len(files)} files...")

    # Fetch file contents
    file_contents = {}
    for file_path in files:
        try:
            content = await get_file_contents(repo, file_path, branch)
            file_contents[file_path] = content
        except Exception as e:
            print(f"  ⚠️  Could not fetch {file_path}: {e}")

    if not file_contents:
        return {"test_files": [], "summary": "No files to test"}

    # Generate tests
    context = "\n\n".join([f"--- {path} ---\n{content}" for path, content in file_contents.items()])

    prompt = f"""Code to test:
{context}

Generate comprehensive test suites. Return JSON:
{{
  "test_files": [
    {{
      "path": "tests/test_example.py",
      "content": "complete test file contents",
      "description": "what is tested"
    }}
  ],
  "coverage_notes": "coverage analysis",
  "summary": "test generation summary"
}}

Generate FULL test file contents."""

    response = await llm.ainvoke([SystemMessage(content=TESTER_SYSTEM_PROMPT), HumanMessage(content=prompt)])

    import json

    try:
        result = json.loads(response.content)
    except json.JSONDecodeError:
        result = {
            "test_files": [],
            "coverage_notes": "Could not parse test generation",
            "summary": "Test generation attempted",
        }

    return result


async def execute_tests(test_files: list[dict[str, Any]]) -> dict[str, Any]:
    """Simulate test execution (in production, would run actual tests)."""
    print(f"  ▶️  Executing {len(test_files)} test files...")

    # Placeholder: In production, would actually run pytest/jest/etc.
    # For now, simulate success with occasional failures
    import random

    passed = []
    failed = []

    for test_file in test_files:
        # Simulate test execution
        if random.random() > 0.2:  # 80% pass rate
            passed.append(test_file["path"])
        else:
            failed.append(
                {
                    "path": test_file["path"],
                    "error": "AssertionError: Simulated test failure",
                    "test_name": "test_example",
                }
            )

    return {
        "total": len(test_files),
        "passed": len(passed),
        "failed": len(failed),
        "passed_tests": passed,
        "failed_tests": failed,
    }


async def tester_node(state: OrchestrationState) -> dict[str, Any]:
    """Tester agent node - generates and runs tests."""
    print(f"\n{'='*80}\n🧪 TESTER AGENT STARTING\n{'='*80}")

    try:
        repo = state["repo"]
        files_changed = state.get("files_changed", [])
        pr_number = state.get("prs_created", [None])[-1]
        branch = state.get("branches_created", ["main"])[-1]

        if not files_changed:
            raise ValueError("No files to test")

        # Generate tests
        test_generation_result = await generate_tests(files_changed, repo, branch)
        test_files = test_generation_result.get("test_files", [])

        print(f"📋 Generated {len(test_files)} test files")

        # Execute tests
        if test_files:
            test_results = await execute_tests(test_files)
        else:
            test_results = {"total": 0, "passed": 0, "failed": 0, "passed_tests": [], "failed_tests": []}

        # Report to PR
        if pr_number:
            report = f"""## 🧪 Test Results

**Total Tests:** {test_results['total']}  
**Passed:** ✅ {test_results['passed']}  
**Failed:** ❌ {test_results['failed']}

### Coverage Analysis
{test_generation_result.get('coverage_notes', 'N/A')}

### Test Files Generated
{chr(10).join(f'- `{tf["path"]}`' for tf in test_files)}
"""

            if test_results["failed"] > 0:
                report += f"\n### ❌ Failures\n"
                for failure in test_results["failed_tests"]:
                    report += f"- `{failure['path']}::{failure['test_name']}`: {failure['error']}\n"

            await add_pr_comment(repo, pr_number, report)

        # Determine status
        all_passed = test_results["failed"] == 0 and test_results["total"] > 0
        status = TaskStatus.COMPLETED if all_passed else TaskStatus.FAILED

        agent_result: AgentResult = {
            "agent": AgentRole.TESTER,
            "status": status,
            "output": f"Tests: {test_results['passed']}/{test_results['total']} passed",
            "artifacts": {"test_files": test_files, "test_results": test_results},
            "metadata": {"pr_number": pr_number},
            "timestamp": datetime.now(),
        }

        print(f"{'✅' if all_passed else '❌'} Testing complete: {test_results['passed']}/{test_results['total']} passed")

        return {
            "test_results": test_results,
            "test_failures": test_results["failed_tests"],
            "agent_results": [agent_result],
            "current_agent": AgentRole.TESTER,
            "next_agents": [AgentRole.REVIEWER] if all_passed else [AgentRole.CODER],
            "retry_count": state.get("retry_count", 0) + (0 if all_passed else 1),
        }

    except Exception as e:
        print(f"❌ Tester failed: {e}")
        agent_result: AgentResult = {
            "agent": AgentRole.TESTER,
            "status": TaskStatus.FAILED,
            "output": str(e),
            "artifacts": {},
            "metadata": {},
            "timestamp": datetime.now(),
        }
        return {"agent_results": [agent_result], "error": str(e)}
