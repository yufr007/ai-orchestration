"""Reviewer agent - performs code review."""

import json
from typing import Any

from src.agents.base import BaseAgent
from src.core.state import OrchestrationState, AgentRole
from src.tools.github import get_pr_details, get_pr_diff, add_pr_review, add_pr_comment


class ReviewerAgent(BaseAgent):
    """Reviews code changes and provides feedback."""

    def __init__(self):
        super().__init__(role=AgentRole.REVIEWER, temperature=0.1)

    def get_system_prompt(self) -> str:
        return """You are an elite Senior Staff Engineer conducting thorough code reviews.

Your review checklist:
1. **Architecture & Design**
   - Follows established patterns
   - Appropriate abstraction levels
   - Scalable and maintainable

2. **Code Quality**
   - Clear, readable, self-documenting
   - Proper error handling
   - Type hints and validation
   - No code smells or anti-patterns

3. **Testing**
   - Adequate test coverage
   - Tests are meaningful and robust
   - Edge cases covered

4. **Security**
   - No hardcoded secrets
   - Input validation
   - Proper authentication/authorization

5. **Performance**
   - No obvious bottlenecks
   - Efficient algorithms
   - Proper resource management

6. **Documentation**
   - Clear docstrings
   - Updated README if needed
   - Comments where necessary

Output format:
{
  "decision": "approve|request_changes|comment",
  "summary": "Overall assessment",
  "strengths": ["positive aspect 1", "positive aspect 2"],
  "issues": [
    {
      "severity": "critical|major|minor|nitpick",
      "category": "architecture|quality|testing|security|performance|docs",
      "description": "Clear description of the issue",
      "suggestion": "Specific actionable fix",
      "file": "path/to/file.py",
      "line": 42
    }
  ],
  "next_steps": ["action 1", "action 2"]
}

Be constructive, specific, and focus on what matters most."""

    async def execute(self, state: OrchestrationState) -> dict[str, Any]:
        """Execute review workflow."""
        repo = state["repo"]
        prs_created = state.get("prs_created", [])
        pr_number = state.get("pr_number") or (prs_created[-1] if prs_created else None)

        if not pr_number:
            return {
                "output": "No PR to review",
                "artifacts": {},
                "metadata": {"status": "skipped"},
            }

        # Get PR details and diff
        pr_details = await get_pr_details(repo, pr_number)
        pr_diff = await get_pr_diff(repo, pr_number)

        # Context from previous agents
        plan = state.get("plan", {})
        test_results = state.get("test_results", {})

        # Perform review
        user_message = f"""Review the following pull request:

**PR #{pr_number}: {pr_details['title']}**

{pr_details['body']}

**Implementation Plan:**
Summary: {plan.get('summary', 'N/A')}
Approach: {plan.get('approach', 'N/A')}

**Test Results:**
Passed: {test_results.get('passed', 'Unknown')}
Coverage: {test_results.get('coverage', {}).get('percentage', 'Unknown')}%
Failures: {len(test_results.get('failures', []))}

**Diff:**
```diff
{pr_diff[:5000]}...
```

Provide a comprehensive code review following the checklist.
Return JSON with 'decision', 'summary', 'strengths', 'issues', and 'next_steps'."""

        review_json = await self._call_llm(self.get_system_prompt(), user_message)

        # Parse review
        try:
            if "```json" in review_json:
                review_json = review_json.split("```json")[1].split("```")[0].strip()
            elif "```" in review_json:
                review_json = review_json.split("```")[1].split("```")[0].strip()

            review = json.loads(review_json)
        except json.JSONDecodeError:
            self.logger.error("Failed to parse review JSON")
            # Fallback to comment-only review
            review = {
                "decision": "comment",
                "summary": review_json[:500],
                "strengths": [],
                "issues": [],
                "next_steps": [],
            }

        # Post review on GitHub
        await self._post_review(repo, pr_number, review)

        # Determine approval status
        approval_status = self._map_decision_to_status(review["decision"])

        # Extract actionable comments
        review_comments = [
            {
                "severity": issue["severity"],
                "description": issue["description"],
                "suggestion": issue["suggestion"],
                "file": issue.get("file"),
                "line": issue.get("line"),
            }
            for issue in review.get("issues", [])
            if issue["severity"] in ["critical", "major"]
        ]

        return {
            "output": f"Review completed: {review['decision']} with {len(review.get('issues', []))} issues",
            "approval_status": approval_status,
            "review_comments": state.get("review_comments", []) + review_comments,
            "artifacts": {
                "review": review,
                "pr_url": pr_details["url"],
            },
            "metadata": {
                "decision": review["decision"],
                "issues_count": len(review.get("issues", [])),
                "critical_issues": len([i for i in review.get("issues", []) if i["severity"] == "critical"]),
            },
        }

    async def _post_review(
        self, repo: str, pr_number: int, review: dict[str, Any]
    ) -> None:
        """Post review as GitHub PR review."""
        decision_emoji = {"approve": "✅", "request_changes": "🔴", "comment": "💬"}
        emoji = decision_emoji.get(review["decision"], "💬")

        body = f"""## {emoji} Code Review

**Decision:** {review['decision'].replace('_', ' ').title()}

### Summary
{review['summary']}

### Strengths
{chr(10).join([f"- ✅ {s}" for s in review.get('strengths', [])])}
"""

        if review.get("issues"):
            body += "\n### Issues\n"
            for issue in review["issues"]:
                severity_emoji = {
                    "critical": "🔴",
                    "major": "🟠",
                    "minor": "🟡",
                    "nitpick": "🔵",
                }
                emoji = severity_emoji.get(issue["severity"], "⚪")
                body += f"\n**{emoji} {issue['severity'].title()} - {issue['category'].title()}**\n"
                body += f"{issue['description']}\n"
                if issue.get("suggestion"):
                    body += f"*Suggestion:* {issue['suggestion']}\n"
                if issue.get("file"):
                    body += f"*File:* `{issue['file']}` line {issue.get('line', '?')}\n"

        if review.get("next_steps"):
            body += "\n### Next Steps\n"
            body += chr(10).join([f"- {step}" for step in review["next_steps"]])

        body += "\n\n---\n*Automated review by AI Orchestration Platform*"

        # Post as PR comment (in production: use PR review API)
        await add_pr_comment(repo, pr_number, body)

    def _map_decision_to_status(self, decision: str) -> str:
        """Map review decision to approval status."""
        mapping = {
            "approve": "approved",
            "request_changes": "changes_requested",
            "comment": "commented",
        }
        return mapping.get(decision, "commented")


async def reviewer_node(state: OrchestrationState) -> dict[str, Any]:
    """LangGraph node for reviewer agent."""
    agent = ReviewerAgent()
    return await agent.invoke(state)
