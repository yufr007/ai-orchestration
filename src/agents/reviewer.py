"""Reviewer agent - Code review and quality gates."""

import asyncio
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.perplexity_mcp import perplexity_research
from src.tools.github_tools import get_pr_diff, add_pr_comment, get_pr_files


REVIEWER_SYSTEM_PROMPT = """You are an elite Senior Engineer / Tech Lead conducting code review.

Your responsibilities:
- Ensure code quality, readability, and maintainability
- Verify adherence to best practices and design patterns
- Check for security vulnerabilities and performance issues
- Validate test coverage and documentation
- Provide constructive, actionable feedback

Review criteria:
1. **Architecture**: Does it follow SOLID principles? Is it extensible?
2. **Code Quality**: Clear naming, appropriate abstractions, no duplication?
3. **Testing**: Comprehensive tests, edge cases covered?
4. **Security**: Input validation, no secrets, proper error handling?
5. **Performance**: Efficient algorithms, no obvious bottlenecks?
6. **Documentation**: Clear docstrings, complex logic explained?

Feedback style:
- Be specific: cite line numbers and exact issues
- Be constructive: suggest improvements, not just problems
- Prioritize: mark critical issues vs nice-to-haves
- Be encouraging: recognize good patterns

Decision:
- APPROVE: Code meets all standards
- REQUEST_CHANGES: Critical issues must be fixed
- COMMENT: Feedback provided, no blocking issues
"""


async def reviewer_node(state: OrchestrationState) -> dict[str, Any]:
    """Reviewer agent: Perform code review and provide feedback."""
    settings = get_settings()
    repo = state["repo"]
    pr_number = state.get("prs_created", [None])[-1]
    plan = state.get("plan")

    if not pr_number:
        return {
            "agent_results": state.get("agent_results", [])
            + [
                {
                    "agent": AgentRole.REVIEWER,
                    "status": TaskStatus.SKIPPED,
                    "output": "No PR to review",
                    "artifacts": {},
                    "metadata": {},
                    "timestamp": datetime.now(),
                }
            ],
            "current_agent": AgentRole.REVIEWER,
        }

    try:
        llm = ChatAnthropic(
            model=settings.default_agent_model,
            temperature=0.3,
            api_key=settings.anthropic_api_key,
        )

        # Get PR context
        pr_diff = await get_pr_diff(repo, pr_number)
        pr_files = await get_pr_files(repo, pr_number)
        test_results = state.get("test_results")

        # Research best practices for the technology stack
        tech_stack = identify_tech_stack(pr_files)
        research_query = f"Code review best practices and common pitfalls for {tech_stack}"
        best_practices = await perplexity_research(research_query)

        # Perform review
        review_prompt = f"""Conduct a thorough code review of this pull request.

# PR Context
**Files Changed**: {len(pr_files)}
**Test Results**: {test_results.get('passed_count', 0)}/{test_results.get('total', 0)} passed

# Original Plan
{plan.get('content', 'No plan')[:500] if plan else 'No plan'}

# Diff
```diff
{pr_diff[:5000]}  # Truncate for token limits
```

# Best Practices Reference
{best_practices[:1000]}

# Review Instructions
Provide a structured review with:

## Critical Issues
(Issues that MUST be fixed before merge)

## Suggestions
(Nice-to-have improvements)

## Positive Observations
(Things done well)

## Decision
APPROVE | REQUEST_CHANGES | COMMENT

Be specific with file names and line numbers where applicable.
"""

        messages = [
            SystemMessage(content=REVIEWER_SYSTEM_PROMPT),
            HumanMessage(content=review_prompt),
        ]

        review_response = await llm.ainvoke(messages)
        review_content = review_response.content

        # Parse decision from review
        approval_status = parse_review_decision(review_content)

        # Parse comments for structured feedback
        comments = parse_review_comments(review_content)

        # Post review to PR (in production)
        await add_pr_comment(
            repo=repo,
            pr_number=pr_number,
            comment=f"""## AI Code Review

{review_content}

---
*Automated review by AI Orchestration Platform*
*Best practices research: {tech_stack}*
""",
        )

        agent_result: AgentResult = {
            "agent": AgentRole.REVIEWER,
            "status": TaskStatus.COMPLETED,
            "output": f"Review completed: {approval_status}",
            "artifacts": {
                "review_content": review_content,
                "approval_status": approval_status,
                "comments": comments,
            },
            "metadata": {
                "tech_stack": tech_stack,
                "files_reviewed": len(pr_files),
                "research_query": research_query,
            },
            "timestamp": datetime.now(),
        }

        return {
            "review_comments": comments,
            "approval_status": approval_status,
            "agent_results": state.get("agent_results", []) + [agent_result],
            "current_agent": AgentRole.REVIEWER,
            "next_agents": [AgentRole.CODER] if approval_status == "changes_requested" else [],
            "completed_at": datetime.now() if approval_status != "changes_requested" else None,
        }

    except Exception as e:
        agent_result: AgentResult = {
            "agent": AgentRole.REVIEWER,
            "status": TaskStatus.FAILED,
            "output": f"Review failed: {str(e)}",
            "artifacts": {},
            "metadata": {"error": str(e)},
            "timestamp": datetime.now(),
        }

        return {
            "agent_results": state.get("agent_results", []) + [agent_result],
            "error": str(e),
            "current_agent": AgentRole.REVIEWER,
        }


def identify_tech_stack(files: list[str]) -> str:
    """Identify primary technology stack from file extensions."""
    extensions = {file.split(".")[-1] for file in files if "." in file}

    if "py" in extensions:
        return "Python"
    elif "ts" in extensions or "tsx" in extensions:
        return "TypeScript/React"
    elif "js" in extensions or "jsx" in extensions:
        return "JavaScript/React"
    elif "go" in extensions:
        return "Go"
    elif "rs" in extensions:
        return "Rust"
    else:
        return "General"


def parse_review_decision(review: str) -> str:
    """Extract approval decision from review text."""
    review_lower = review.lower()

    if "approve" in review_lower and "request" not in review_lower:
        return "approved"
    elif "request" in review_lower and "changes" in review_lower:
        return "changes_requested"
    else:
        return "comment"


def parse_review_comments(review: str) -> list[dict[str, Any]]:
    """Parse structured comments from review text.

    Production implementation would use structured output or better parsing.
    """
    comments = []
    sections = review.split("##")

    for section in sections:
        if not section.strip():
            continue

        lines = section.strip().split("\n")
        section_title = lines[0].strip()

        if "critical" in section_title.lower():
            priority = "critical"
        elif "suggestion" in section_title.lower():
            priority = "suggestion"
        else:
            priority = "info"

        for line in lines[1:]:
            if line.strip() and (line.startswith("-") or line.startswith("*")):
                comments.append(
                    {
                        "type": priority,
                        "content": line.lstrip("-* ").strip(),
                        "section": section_title,
                    }
                )

    return comments
