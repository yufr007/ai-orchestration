"""Reviewer agent: Code review and quality gates."""

from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.github import add_pr_comment, get_pr_details, get_pr_files


REVIEWER_SYSTEM_PROMPT = """You are an elite Senior Engineer performing code review.

Your responsibilities:
1. Review code changes for:
   - Correctness: Does it solve the problem?
   - Code quality: Clean, maintainable, follows best practices?
   - Performance: Efficient algorithms and data structures?
   - Security: No vulnerabilities, proper input validation?
   - Testing: Adequate test coverage?
   - Documentation: Clear docstrings and comments where needed?
2. Identify issues ranging from:
   - BLOCKING: Must fix before merge (bugs, security issues)
   - MAJOR: Should fix (performance, maintainability)
   - MINOR: Nice to have (style, optimization opportunities)
3. Provide specific, actionable feedback
4. Suggest improvements with code examples
5. Approve if ready, request changes if issues found

Output format:
```json
{
  "decision": "APPROVE" | "REQUEST_CHANGES" | "COMMENT",
  "summary": "Overall assessment",
  "comments": [
    {
      "file": "path/to/file.py",
      "line": 42,
      "severity": "BLOCKING" | "MAJOR" | "MINOR",
      "comment": "Specific issue and suggestion"
    }
  ]
}
```

Be thorough but fair. Recognize good work. Focus on substance over style."""


async def reviewer_node(state: OrchestrationState) -> dict[str, Any]:
    """Reviewer agent node: Perform code review on PR."""
    settings = get_settings()
    
    # Initialize LLM
    llm = ChatAnthropic(
        model=settings.default_agent_model,
        temperature=0.3,
        api_key=settings.anthropic_api_key,
    )
    
    # Get PR details
    pr_number = state.get("prs_created", [None])[-1] or state.get("pr_number")
    if not pr_number:
        return {
            "error": "No PR available for review",
            "agent_results": [
                {
                    "agent": AgentRole.REVIEWER,
                    "status": TaskStatus.FAILED,
                    "output": "No PR",
                    "artifacts": {},
                    "metadata": {},
                    "timestamp": datetime.now(),
                }
            ],
        }
    
    repo_parts = state["repo"].split("/")
    owner, repo_name = repo_parts[0], repo_parts[1]
    
    # Get PR details and files
    pr_details = await get_pr_details(owner=owner, repo=repo_name, pr_number=pr_number)
    pr_files = await get_pr_files(owner=owner, repo=repo_name, pr_number=pr_number)
    
    # Gather review context
    context_parts = []
    context_parts.append(f"PR #{pr_number}: {pr_details['title']}")
    context_parts.append(f"Description: {pr_details['body']}")
    context_parts.append(f"\nFiles changed: {len(pr_files)}")
    
    # Get test results if available
    test_results = state.get("test_results")
    if test_results:
        context_parts.append(
            f"\nTest Results: {test_results['passed']}/{test_results['total']} passed, "
            f"{test_results['coverage']}% coverage"
        )
    
    # Add file diffs (simplified - in production, get actual diffs)
    for file in pr_files[:3]:  # Limit to first 3 files
        context_parts.append(f"\n{file['filename']}: {file['additions']} additions, {file['deletions']} deletions")
    
    context = "\n".join(context_parts)
    
    messages = [
        SystemMessage(content=REVIEWER_SYSTEM_PROMPT),
        HumanMessage(content=f"{context}\n\nPerform a thorough code review and provide your decision."),
    ]
    
    # Invoke LLM
    response = await llm.ainvoke(messages)
    review_output = response.content
    
    # Parse review decision (simplified - in production use structured output)
    # For demo: assume approval if tests passed and no critical issues
    has_test_failures = state.get("test_failures", [])
    
    if has_test_failures:
        decision = "REQUEST_CHANGES"
        comments = [
            {
                "body": "Tests are failing. Please fix test failures before merging.",
                "severity": "BLOCKING",
            }
        ]
    else:
        decision = "APPROVE"
        comments = [
            {
                "body": f"LGTM! ✅\n\n{review_output[:500]}",
                "severity": "INFO",
            }
        ]
    
    # Add review comment to PR
    for comment in comments:
        await add_pr_comment(
            owner=owner,
            repo=repo_name,
            pr_number=pr_number,
            body=comment["body"],
        )
    
    # Create agent result
    result: AgentResult = {
        "agent": AgentRole.REVIEWER,
        "status": TaskStatus.COMPLETED,
        "output": review_output,
        "artifacts": {"decision": decision, "comments": comments},
        "metadata": {"pr_number": pr_number},
        "timestamp": datetime.now(),
    }
    
    return {
        "review_comments": comments,
        "approval_status": decision.lower(),
        "agent_results": [result],
        "current_agent": AgentRole.REVIEWER,
        "completed_at": datetime.now() if decision == "APPROVE" else None,
        "messages": [HumanMessage(content=f"Review: {decision}")],
    }
