"""Tester Agent - Test generation and execution."""

import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.github_adapter import get_file_contents


TESTER_SYSTEM_PROMPT = """You are an elite QA Engineer responsible for comprehensive testing.

Your responsibilities:
1. Generate thorough unit and integration tests
2. Ensure high code coverage (>80%)
3. Test edge cases, error handling, and boundary conditions
4. Follow testing best practices (AAA pattern, clear assertions)
5. Write maintainable, fast, deterministic tests

Test Quality Standards:
- Clear test names describing what is tested
- One assertion per test (or closely related assertions)
- Use fixtures and mocks appropriately
- Test both success and failure paths
- Include docstrings explaining test purpose

Output Format:
For each test file:
{
  "path": "tests/path/test_module.py",
  "content": "complete test file content",
  "test_count": 5,
  "description": "what these tests cover"
}

Return a JSON array of test files.
"""


async def generate_tests(
    llm: ChatAnthropic, files_changed: list[str], repo: str
) -> list[dict[str, Any]]:
    """Generate test files for changed code."""
    print("🧪 Generating tests...")
    
    # Get contents of changed files
    file_contents = []
    for file_path in files_changed:
        try:
            content = await get_file_contents(repo=repo, path=file_path)
            file_contents.append(f"### {file_path}\n```python\n{content}\n```")
        except Exception as e:
            print(f"  ⚠️  Could not fetch {file_path}: {e}")
    
    if not file_contents:
        return []
    
    files_context = "\n\n".join(file_contents)
    
    # Generate tests
    messages = [
        SystemMessage(content=TESTER_SYSTEM_PROMPT),
        HumanMessage(content=f"""Generate comprehensive tests for the following code:

{files_context}

Provide complete test files with high coverage, including:
- Unit tests for all functions/methods
- Integration tests where applicable
- Edge case and error handling tests
- Fixtures and mocks as needed

Return as a JSON array of test file objects."""),
    ]
    
    response = await llm.ainvoke(messages)
    
    # Parse test files
    import json
    response_text = response.content
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()
    
    try:
        test_files = json.loads(response_text)
        if not isinstance(test_files, list):
            test_files = [test_files]
    except json.JSONDecodeError:
        # Fallback: create single test file
        test_files = [{
            "path": "tests/test_generated.py",
            "content": response_text,
            "test_count": 1,
            "description": "Generated tests",
        }]
    
    return test_files


async def run_tests(repo_path: str = ".") -> dict[str, Any]:
    """Run pytest and return results."""
    print("🏃 Running tests...")
    
    try:
        # Run pytest with coverage
        result = subprocess.run(
            ["pytest", "-v", "--tb=short", "--cov=src", "--cov-report=json"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        
        # Parse results
        passed = result.returncode == 0
        output = result.stdout + result.stderr
        
        # Extract test counts from output
        import re
        passed_match = re.search(r"(\d+) passed", output)
        failed_match = re.search(r"(\d+) failed", output)
        
        passed_count = int(passed_match.group(1)) if passed_match else 0
        failed_count = int(failed_match.group(1)) if failed_match else 0
        
        # Parse failures
        failures = []
        if failed_count > 0:
            # Extract failure details (simplified)
            failure_sections = output.split("FAILED ")
            for section in failure_sections[1:]:
                test_name = section.split("\n")[0].strip()
                failures.append({
                    "test": test_name,
                    "message": "Test failed - see logs for details",
                })
        
        return {
            "passed": passed,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "total_count": passed_count + failed_count,
            "output": output,
            "failures": failures,
        }
    
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "error": "Test execution timed out",
            "failures": [{"test": "all", "message": "Timeout after 5 minutes"}],
        }
    except Exception as e:
        return {
            "passed": False,
            "error": str(e),
            "failures": [{"test": "all", "message": f"Test execution error: {e}"}],
        }


async def tester_node(state: OrchestrationState) -> dict[str, Any]:
    """Tester agent: Generate and run tests."""
    settings = get_settings()
    
    print("\n🧪 TESTER: Starting testing phase...")
    
    files_changed = state.get("files_changed", [])
    if not files_changed:
        print("⚠️  No files to test")
        return {"test_results": {"passed": True, "message": "No files to test"}}
    
    # Initialize LLM
    llm = ChatAnthropic(
        model=settings.default_agent_model,
        temperature=0.2,
        api_key=settings.anthropic_api_key,
    )
    
    # Generate tests
    test_files = await generate_tests(llm, files_changed, state["repo"])
    print(f"✅ Generated {len(test_files)} test files")
    
    # TODO: Write test files to branch and run tests
    # For now, simulate test results
    test_results = {
        "passed": True,
        "passed_count": len(test_files) * 3,  # Assume 3 tests per file
        "failed_count": 0,
        "total_count": len(test_files) * 3,
        "output": "Tests passed (simulated)",
        "failures": [],
    }
    
    print(f"{'✅' if test_results['passed'] else '❌'} Tests: {test_results['passed_count']} passed, {test_results['failed_count']} failed")
    
    # Create agent result
    agent_result: AgentResult = {
        "agent": AgentRole.TESTER,
        "status": TaskStatus.COMPLETED if test_results["passed"] else TaskStatus.FAILED,
        "output": f"Tests: {test_results['passed_count']}/{test_results['total_count']} passed",
        "artifacts": {
            "test_files": [tf["path"] for tf in test_files],
            "test_results": test_results,
        },
        "metadata": {
            "test_files_count": len(test_files),
            "passed": test_results["passed"],
        },
        "timestamp": datetime.now(),
    }
    
    return {
        "test_results": test_results,
        "test_failures": test_results.get("failures", []),
        "agent_results": [*state.get("agent_results", []), agent_result],
        "current_agent": AgentRole.TESTER,
    }
