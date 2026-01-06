"""Reviewer Agent - Code review and quality gates."""

from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.github import add_pr_review, get_pr_diff


REVIEWER_SYSTEM_PROMPT = """You are an elite Senior Engineering Manager performing code review.

Review criteria:
1. **Code Quality**: Clean, maintainable, follows best practices
2. **Architecture**: Proper separation of concerns, scalability
3. **Security**: No vulnerabilities, proper input validation
4. **Testing**: Adequate coverage, quality of tests
5. **Documentation**: Clear comments, docstrings, README updates
6. **Performance**: No obvious bottlenecks or inefficiencies
7. **Error Handling**: Comprehensive, proper logging
8. **Style**: Consistent formatting, naming conventions

Output structured review with:
- Overall assessment (APPROVE, REQUEST_CHANGES, COMMENT)
- Strengths (what's done well)
- Issues (must-fix problems)
- Suggestions (nice-to-haves)
- Security concerns (if any)
- Performance notes

Be thorough but constructive. Approve only production-ready code."""


async def reviewer_node(state: OrchestrationState) -> dict[str, Any]:
    """Reviewer agent node - performs code review."""
    settings = get_settings()
    print(f"\n{'='*80}\n👀 REVIEWER AGENT STARTING\n{'='*80}")

    try:
        repo = state["repo"]
        pr_number = state.get("prs_created", [None])[-1]

        if not pr_number:
            raise ValueError("No PR to review")

        # Get PR diff
        print(f"📄 Fetching PR #{pr_number} diff...")
        pr_diff = await get_pr_diff(repo, pr_number)

        # Perform review
        llm = ChatAnthropic(
            model=settings.default_agent_model,
            temperature=0.1,  # Low temperature for consistent reviews
            api_key=settings.anthropic_api_key,
        )

        plan = state.get("plan", {})
        test_results = state.get("test_results", {})

        prompt = f"""Review this pull request:

**Original Plan:**
{plan.get('summary', 'N/A')}

**Test Results:**
Passed: {test_results.get('passed', 0)}/{test_results.get('total', 0)}

**Code Changes:**
{pr_diff[:8000]}  # Limit diff size

Provide structured review as JSON:
{{
  "decision": "APPROVE" | "REQUEST_CHANGES" | "COMMENT",
  "summary": "overall assessment",
  "strengths": ["strength 1", "strength 2"],
  "issues": [
    {{"severity": "critical|major|minor", "description": "issue", "file": "path", "line": 10}}
  ],
  "suggestions": ["suggestion 1"],
  "security_concerns": ["concern 1"],
  "performance_notes": "performance analysis"
}}
"""

        print("🔍 Analyzing code...")
        response = await llm.ainvoke([SystemMessage(content=REVIEWER_SYSTEM_PROMPT), HumanMessage(content=prompt)])

        # Parse review
        import json

        try:
            review = json.loads(response.content)
        except json.JSONDecodeError:
            review = {
                "decision": "COMMENT",
                "summary": response.content[:500],
                "strengths": [],
                "issues": [],
                "suggestions": [],
                "security_concerns": [],
                "performance_notes": "Could not parse review",
            }

        # Format review comment
        review_body = f"""## 🤖 AI Code Review

### Decision: {review['decision']}

{review['summary']}

### ✅ Strengths
{chr(10).join(f'- {s}' for s in review.get('strengths', [])) if review.get('strengths') else '- None noted'}

### ⚠️ Issues
{chr(10).join(f'- **{i.get("severity", "unknown").upper()}**: {i.get("description", "")} (`{i.get("file", "unknown")}:{i.get("line", "?")}`)' for i in review.get('issues', [])) if review.get('issues') else '- None found'}

### 💡 Suggestions
{chr(10).join(f'- {s}' for s in review.get('suggestions', [])) if review.get('suggestions') else '- None'}

### 🔒 Security
{chr(10).join(f'- ⚠️ {c}' for c in review.get('security_concerns', [])) if review.get('security_concerns') else '- ✅ No concerns identified'}

### ⚡ Performance
{review.get('performance_notes', 'No specific notes')}

---
*Automated review - Human review still recommended before merge*
"""

        # Submit review to PR
        print(f"📝 Submitting review: {review['decision']}")
        await add_pr_review(
            repo=repo,
            pr_number=pr_number,
            body=review_body,
            event=review["decision"],
        )

        # Determine approval status
        approval_status = (
            "approved"
            if review["decision"] == "APPROVE"
            else "changes_requested" if review["decision"] == "REQUEST_CHANGES" else "commented"
        )

        agent_result: AgentResult = {
            "agent": AgentRole.REVIEWER,
            "status": TaskStatus.COMPLETED,
            "output": f"Review: {review['decision']}",
            "artifacts": {"review": review, "approval_status": approval_status},
            "metadata": {"pr_number": pr_number},
            "timestamp": datetime.now(),
        }

        print(f"✅ Review complete: {review['decision']}")
        print(f"   Issues: {len(review.get('issues', []))} | Suggestions: {len(review.get('suggestions', []))}")

        return {
            "review_comments": [review],
            "approval_status": approval_status,
            "agent_results": [agent_result],
            "current_agent": AgentRole.REVIEWER,
            "next_agents": [],
            "completed_at": datetime.now(),
        }

    except Exception as e:
        print(f"❌ Reviewer failed: {e}")
        agent_result: AgentResult = {
            "agent": AgentRole.REVIEWER,
            "status": TaskStatus.FAILED,
            "output": str(e),
            "artifacts": {},
            "metadata": {},
            "timestamp": datetime.now(),
        }
        return {"agent_results": [agent_result], "error": str(e)}
