"""Reviewer Agent - Code review and quality gates."""

from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.github import get_pr_details, add_pr_review_comment


REVIEWER_SYSTEM_PROMPT = """You are an elite Senior Engineer performing code review.

Your responsibilities:
1. Ensure code quality, maintainability, and best practices
2. Check for security vulnerabilities and performance issues
3. Verify test coverage and documentation
4. Ensure consistency with project standards
5. Provide constructive, actionable feedback

Review Checklist:
- Code correctness and logic
- Error handling and edge cases
- Type safety and null checks
- Performance and scalability
- Security (SQL injection, XSS, secrets, etc.)
- Test coverage and quality
- Documentation and comments
- Code style and conventions
- DRY principle and code duplication
- Separation of concerns

Output Format:
{
  "decision": "approve" | "request_changes" | "comment",
  "summary": "Overall assessment",
  "comments": [
    {
      "file": "path/to/file.py",
      "line": 42,
      "severity": "critical" | "major" | "minor" | "nit",
      "message": "Detailed feedback",
      "suggestion": "Recommended fix"
    }
  ],
  "strengths": ["Good aspect 1"],
  "concerns": ["Issue 1"]
}

Be thorough but constructive. Focus on critical issues first.
"""


async def reviewer_node(state: OrchestrationState) -> dict[str, Any]:
    """Reviewer agent: Code review and quality gates."""
    settings = get_settings()
    
    print("\n🔍 REVIEWER: Starting code review...")
    
    # Get PR details
    pr_number = state.get("prs_created", [None])[-1] or state.get("pr_number")
    if not pr_number:
        print("⚠️  No PR to review")
        return {"approval_status": "approved", "review_comments": []}
    
    print(f"📝 Reviewing PR #{pr_number}...")
    
    # Initialize LLM
    llm = ChatAnthropic(
        model=settings.default_agent_model,
        temperature=0.3,
        api_key=settings.anthropic_api_key,
    )
    
    # Get PR details with diff
    pr_data = await get_pr_details(
        repo=state["repo"],
        pr_number=pr_number,
        include_diff=True,
    )
    
    # Perform review
    messages = [
        SystemMessage(content=REVIEWER_SYSTEM_PROMPT),
        HumanMessage(content=f"""Review the following pull request:

{pr_data}

Provide a comprehensive code review following the checklist.
Return your review as JSON in the specified format."""),
    ]
    
    response = await llm.ainvoke(messages)
    
    # Parse review
    import json
    review_text = response.content
    if "```json" in review_text:
        review_text = review_text.split("```json")[1].split("```")[0].strip()
    elif "```" in review_text:
        review_text = review_text.split("```")[1].split("```")[0].strip()
    
    try:
        review = json.loads(review_text)
    except json.JSONDecodeError:
        # Fallback: basic review structure
        review = {
            "decision": "comment",
            "summary": review_text[:200],
            "comments": [],
        }
    
    decision = review.get("decision", "comment")
    comments = review.get("comments", [])
    
    print(f"💬 Decision: {decision.upper()}")
    print(f"📝 {len(comments)} comments")
    
    # Post review comments to PR (if not in plan mode)
    if state.get("mode") != "plan" and comments:
        print("📤 Posting review comments...")
        for comment in comments[:5]:  # Limit to 5 comments to avoid spam
            try:
                await add_pr_review_comment(
                    repo=state["repo"],
                    pr_number=pr_number,
                    body=f"**[{comment.get('severity', 'comment').upper()}]** {comment.get('message')}\n\n{comment.get('suggestion', '')}",
                    path=comment.get("file"),
                    line=comment.get("line"),
                )
                print(f"  ✅ Comment on {comment.get('file')}:{comment.get('line')}")
            except Exception as e:
                print(f"  ⚠️  Could not post comment: {e}")
    
    # Determine approval status
    approval_status = "approved" if decision == "approve" else "changes_requested" if decision == "request_changes" else "commented"
    
    # Create agent result
    agent_result: AgentResult = {
        "agent": AgentRole.REVIEWER,
        "status": TaskStatus.COMPLETED,
        "output": review.get("summary", "Review completed"),
        "artifacts": {
            "decision": decision,
            "comments": comments,
            "review": review,
        },
        "metadata": {
            "pr_number": pr_number,
            "comments_count": len(comments),
            "decision": decision,
        },
        "timestamp": datetime.now(),
    }
    
    return {
        "review_comments": comments,
        "approval_status": approval_status,
        "agent_results": [*state.get("agent_results", []), agent_result],
        "current_agent": AgentRole.REVIEWER,
    }
