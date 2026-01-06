"""Reviewer agent - Code review with quality gates."""

from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.github import get_pr_diff, add_pr_review_comment


REVIEWER_SYSTEM_PROMPT = """You are an elite Staff Engineer performing code reviews.

Your responsibilities:
1. Review code for correctness, maintainability, and best practices
2. Check for security vulnerabilities and performance issues
3. Ensure consistent style and proper documentation
4. Verify tests cover edge cases
5. Provide constructive, actionable feedback

Review Checklist:
- Code Quality: DRY, SOLID principles, proper abstractions
- Security: Input validation, SQL injection, XSS, secrets
- Performance: Time complexity, memory usage, database queries
- Error Handling: Proper exceptions, logging, user feedback
- Testing: Coverage, edge cases, mocks
- Documentation: Docstrings, comments, README updates
- Style: Consistent formatting, naming conventions

Provide feedback in this format:
{
  "decision": "approve|request_changes|comment",
  "summary": "Overall assessment",
  "comments": [
    {
      "file": "path/to/file.py",
      "line": 42,
      "severity": "critical|major|minor|suggestion",
      "category": "security|performance|style|documentation",
      "issue": "Description of issue",
      "suggestion": "How to fix it"
    }
  ],
  "positives": ["Good practice 1", "Good practice 2"],
  "requires_changes": true/false
}

Be thorough but fair. Recognize good practices as well as issues.
"""


async def reviewer_node(state: OrchestrationState) -> dict[str, Any]:
    """Reviewer agent node - perform code review."""
    settings = get_settings()
    repo = state["repo"]
    prs_created = state.get("prs_created", [])
    pr_number = state.get("pr_number") or (prs_created[0] if prs_created else None)

    if not pr_number:
        agent_result: AgentResult = {
            "agent": AgentRole.REVIEWER,
            "status": TaskStatus.SKIPPED,
            "output": "No PR to review",
            "artifacts": {},
            "metadata": {},
            "timestamp": datetime.now(),
        }
        return {
            "agent_results": state.get("agent_results", []) + [agent_result],
            "current_agent": AgentRole.REVIEWER,
            "approval_status": "skipped",
        }

    llm = ChatAnthropic(
        model=settings.default_agent_model,
        temperature=0.2,
        api_key=settings.anthropic_api_key,
    )

    # Get PR diff
    try:
        pr_diff = await get_pr_diff(repo, pr_number)
    except Exception as e:
        pr_diff = f"Error getting diff: {e}"

    # Build review context
    context = f"""Pull Request #{pr_number}

Changes:
{pr_diff[:10000]}  # Limit context size

Perform a thorough code review covering security, performance, maintainability, and testing.
"""

    messages = [
        SystemMessage(content=REVIEWER_SYSTEM_PROMPT),
        HumanMessage(content=context),
    ]

    response = await llm.ainvoke(messages)

    # Parse response
    import json

    try:
        review = json.loads(response.content)
    except json.JSONDecodeError:
        content = response.content
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            review = json.loads(content[json_start:json_end].strip())
        else:
            # Fallback
            review = {
                "decision": "comment",
                "summary": "Review completed",
                "comments": [],
                "positives": [],
                "requires_changes": False,
            }

    # Post review comments to PR
    review_comments = []
    for comment in review.get("comments", []):
        try:
            await add_pr_review_comment(
                repo=repo,
                pr_number=pr_number,
                body=f"**{comment['severity'].upper()}** ({comment['category']})\n\n"
                f"{comment['issue']}\n\n"
                f"**Suggestion:** {comment['suggestion']}",
                path=comment.get("file"),
                line=comment.get("line"),
            )
            review_comments.append(comment)
        except Exception:
            pass

    # Determine approval status
    approval_status = "approved" if review["decision"] == "approve" else "changes_requested"

    agent_result: AgentResult = {
        "agent": AgentRole.REVIEWER,
        "status": TaskStatus.COMPLETED,
        "output": review["summary"],
        "artifacts": {"review": review},
        "metadata": {
            "comments_count": len(review_comments),
            "critical_issues": sum(
                1 for c in review_comments if c.get("severity") == "critical"
            ),
        },
        "timestamp": datetime.now(),
    }

    return {
        "review_comments": review_comments,
        "approval_status": approval_status,
        "agent_results": state.get("agent_results", []) + [agent_result],
        "current_agent": AgentRole.REVIEWER,
    }
