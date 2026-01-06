"""Reviewer agent - Code review and quality gates."""

from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.github import GitHubTools


REVIEWER_SYSTEM_PROMPT = """You are an elite Senior Engineer performing thorough code reviews.

Your responsibilities:
- Review code for correctness, maintainability, and adherence to standards
- Check for security vulnerabilities and anti-patterns
- Ensure tests provide adequate coverage
- Verify documentation is clear and complete
- Provide constructive feedback with specific suggestions
- Approve when quality standards are met
- Request changes when issues are found

Review checklist:
1. **Correctness**: Does the code do what it's supposed to?
2. **Readability**: Is it easy to understand? Are names clear?
3. **Maintainability**: Can it be easily modified in the future?
4. **Performance**: Any obvious inefficiencies?
5. **Security**: Input validation, authentication, secrets handling?
6. **Testing**: Adequate test coverage? Edge cases handled?
7. **Documentation**: Docstrings, comments, README updates?
8. **Consistency**: Follows project conventions and patterns?

Output format:
- Overall assessment (APPROVE, REQUEST_CHANGES, COMMENT)
- Specific issues with file/line references
- Suggestions for improvement
- Required changes before approval
"""


async def reviewer_node(state: OrchestrationState) -> dict[str, Any]:
    """Review the PR and provide feedback."""
    settings = get_settings()
    github = GitHubTools()

    repo = state["repo"]
    pr_number = state.get("prs_created", [None])[-1]

    if not pr_number:
        return {
            "messages": [HumanMessage(content="No PR to review")],
            "current_agent": AgentRole.REVIEWER,
        }

    # Get PR details
    pr_diff = await github.get_pr_diff(repo, pr_number)
    pr_files = await github.get_pr_files(repo, pr_number)
    test_results = state.get("test_results", {})

    # Get plan for context
    plan = state.get("plan", {})
    acceptance_criteria = plan.get("acceptance_criteria", "Meets requirements")

    # Prepare review prompt
    messages = [
        SystemMessage(content=REVIEWER_SYSTEM_PROMPT),
        HumanMessage(
            content=f"""Review this pull request:

**PR #{pr_number}**

**Acceptance Criteria:**
{acceptance_criteria}

**Test Results:**
Passed: {test_results.get('passed', 'N/A')}
Failed: {test_results.get('failed', 'N/A')}

**Changes:**
{_format_diff(pr_diff)}

**Files:**
{_format_files(pr_files)}

Provide a comprehensive code review."""
        ),
    ]

    # Initialize LLM
    llm = ChatAnthropic(
        model=settings.default_agent_model,
        temperature=0.3,
        api_key=settings.anthropic_api_key,
    )

    # Get review
    response = await llm.ainvoke(messages)
    review_content = response.content

    # Parse review
    approval_status, comments = _parse_review(review_content)

    # Post review comments to GitHub
    if comments:
        for comment in comments:
            await github.add_review_comment(
                repo=repo,
                pr_number=pr_number,
                body=comment["body"],
                path=comment.get("path"),
                line=comment.get("line"),
            )

    # Submit review
    await github.submit_review(
        repo=repo,
        pr_number=pr_number,
        event=approval_status,
        body=review_content,
    )

    # Create result
    result: AgentResult = {
        "agent": AgentRole.REVIEWER,
        "status": TaskStatus.COMPLETED,
        "output": review_content,
        "artifacts": {
            "approval_status": approval_status,
            "comments": comments,
            "pr_number": pr_number,
        },
        "metadata": {
            "model": settings.default_agent_model,
            "comments_count": len(comments),
        },
        "timestamp": datetime.now(),
    }

    return {
        "review_comments": comments,
        "approval_status": approval_status,
        "agent_results": state.get("agent_results", []) + [result],
        "current_agent": AgentRole.REVIEWER,
        "messages": [
            HumanMessage(content=f"Review completed: {approval_status} with {len(comments)} comments")
        ],
    }


def _format_diff(diff: str) -> str:
    """Format diff for prompt (truncate if too long)."""
    if len(diff) > 4000:
        return diff[:4000] + "\n... (truncated)"
    return diff


def _format_files(files: dict[str, str]) -> str:
    """Format files for prompt."""
    formatted = []
    for path, content in files.items():
        # Truncate large files
        display_content = content if len(content) < 1000 else content[:1000] + "\n... (truncated)"
        formatted.append(f"### {path}\n```\n{display_content}\n```")
    return "\n\n".join(formatted)


def _parse_review(content: str) -> tuple[str, list[dict[str, Any]]]:
    """Parse review content to extract approval status and comments."""
    # Determine approval status
    content_lower = content.lower()
    if "approve" in content_lower and "request changes" not in content_lower:
        status = "APPROVE"
    elif "request changes" in content_lower or "must fix" in content_lower:
        status = "REQUEST_CHANGES"
    else:
        status = "COMMENT"

    # Extract specific comments (simplified)
    comments = []
    lines = content.split("\n")
    current_comment = {}

    for line in lines:
        # Look for file/line references
        if "file:" in line.lower() or "line:" in line.lower():
            if current_comment:
                comments.append(current_comment)
            current_comment = {"body": ""}

            # Extract file path
            if "file:" in line.lower():
                file_part = line.split("file:")[-1].strip()
                current_comment["path"] = file_part.split()[0].strip("`'\"")

            # Extract line number
            if "line:" in line.lower():
                line_part = line.split("line:")[-1].strip()
                try:
                    current_comment["line"] = int(line_part.split()[0])
                except ValueError:
                    pass

        elif current_comment and line.strip():
            current_comment["body"] += line + "\n"

    if current_comment:
        comments.append(current_comment)

    return status, comments
