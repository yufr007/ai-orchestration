"""Reviewer agent: Code review and quality gates."""

import asyncio
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.github import get_pr_diff, add_pr_review, get_file_contents

settings = get_settings()

REVIEWER_SYSTEM_PROMPT = """You are an elite Senior Engineer performing code review.

Your review criteria:
1. **Correctness**: Does the code do what it's supposed to?
2. **Design**: Is the solution well-architected and maintainable?
3. **Complexity**: Is the code unnecessarily complex?
4. **Tests**: Are there adequate tests?
5. **Naming**: Are variables, functions, and classes well-named?
6. **Comments**: Are complex sections documented?
7. **Style**: Does it follow project conventions?
8. **Security**: Are there security vulnerabilities?
9. **Performance**: Are there obvious performance issues?
10. **Error handling**: Are errors handled gracefully?

Provide constructive feedback:
- Highlight what's done well
- Suggest specific improvements with examples
- Identify potential bugs or edge cases
- Rate severity: CRITICAL (blocks merge), MAJOR (should fix), MINOR (nice to have)

Output structured review:
- overall_verdict: "APPROVE" | "REQUEST_CHANGES" | "COMMENT"
- summary: Brief overview of review
- strengths: What was done well
- issues: Array of {severity, file, line, description, suggestion}
"""


async def reviewer_node(state: OrchestrationState) -> dict[str, Any]:
    """Execute the reviewer agent to perform code review."""
    print("\n👀 REVIEWER: Starting code review phase...")

    repo = state["repo"]
    pr_number = state.get("prs_created", [None])[-1]
    files_changed = state.get("files_changed", [])

    if not pr_number:
        return {
            "approval_status": "no_pr",
            "agent_results": [
                AgentResult(
                    agent=AgentRole.REVIEWER,
                    status=TaskStatus.SKIPPED,
                    output="No PR to review",
                    artifacts={},
                    metadata={},
                    timestamp=datetime.now(),
                )
            ],
        }

    # Initialize LLM
    llm = ChatAnthropic(
        model=settings.default_agent_model,
        temperature=0.3,
        api_key=settings.anthropic_api_key,
    )

    # Get PR diff
    print(f"📥 REVIEWER: Fetching PR #{pr_number} diff...")
    pr_diff = await get_pr_diff(repo, pr_number)

    # Get full file contents for context
    branch = state.get("branches_created", [None])[-1]
    file_contents = await asyncio.gather(
        *[
            get_file_contents(repo, file, branch)
            for file in files_changed[:5]  # Limit to avoid token overflow
        ],
        return_exceptions=True,
    )

    files_context = "\n\n".join(
        f"**{file}:**\n```\n{content[:2000]}...\n```"
        for file, content in zip(files_changed, file_contents)
        if not isinstance(content, Exception)
    )

    # Perform review
    print("🔍 REVIEWER: Analyzing code quality...")
    messages = [
        SystemMessage(content=REVIEWER_SYSTEM_PROMPT),
        HumanMessage(
            content=f"""Review this pull request:

**Diff:**
```diff
{pr_diff[:8000]}...
```

**Full file context:**
{files_context}

Provide comprehensive code review in JSON format."""
        ),
    ]

    response = await llm.ainvoke(messages)
    review_text = response.content

    # Parse review (extract JSON if present)
    import json

    try:
        if "```json" in review_text:
            review_text = review_text.split("```json")[1].split("```")[0].strip()
        elif "```" in review_text:
            review_text = review_text.split("```")[1].split("```")[0].strip()
        review = json.loads(review_text)
    except json.JSONDecodeError:
        # Fallback to unstructured review
        review = {
            "overall_verdict": "COMMENT",
            "summary": review_text,
            "strengths": [],
            "issues": [],
        }

    # Extract review decision
    verdict = review.get("overall_verdict", "COMMENT").upper()
    approval_status = (
        "approved" if verdict == "APPROVE" else "changes_requested" if verdict == "REQUEST_CHANGES" else "commented"
    )

    # Format review comment
    issues = review.get("issues", [])
    critical_issues = [i for i in issues if i.get("severity") == "CRITICAL"]
    major_issues = [i for i in issues if i.get("severity") == "MAJOR"]
    minor_issues = [i for i in issues if i.get("severity") == "MINOR"]

    review_comment = f"""## 👀 Code Review

**Verdict:** {verdict}

### Summary
{review.get('summary', 'Review complete')}

### ✨ Strengths
{''.join(f"- {s}\n" for s in review.get('strengths', [])) or '- Implementation follows requirements'}

### 📋 Issues Found

{f"#### 🚨 Critical ({len(critical_issues)})\n" + ''.join(f"- **{i.get('file', 'general')}**: {i.get('description')}\n  *Suggestion:* {i.get('suggestion', 'Fix required')}\n" for i in critical_issues) if critical_issues else ''}

{f"#### ⚠️ Major ({len(major_issues)})\n" + ''.join(f"- **{i.get('file', 'general')}**: {i.get('description')}\n  *Suggestion:* {i.get('suggestion', 'Should fix')}\n" for i in major_issues) if major_issues else ''}

{f"#### ℹ️ Minor ({len(minor_issues)})\n" + ''.join(f"- **{i.get('file', 'general')}**: {i.get('description')}\n" for i in minor_issues) if minor_issues else ''}

{'### ✅ No issues found - Ready to merge!' if not issues else ''}

---
*Generated by AI Orchestration Platform - Reviewer Agent*
"""

    # Post review to PR
    print(f"💬 REVIEWER: Posting review ({verdict})...")
    await add_pr_review(repo, pr_number, review_comment, verdict)

    print(f"{'✅' if verdict == 'APPROVE' else '📝'} REVIEWER: Review complete - {verdict}")

    return {
        "approval_status": approval_status,
        "review_comments": issues,
        "current_agent": AgentRole.REVIEWER,
        "agent_results": [
            AgentResult(
                agent=AgentRole.REVIEWER,
                status=TaskStatus.COMPLETED,
                output=f"Review: {verdict}",
                artifacts={"review": review, "verdict": verdict},
                metadata={
                    "critical_issues": len(critical_issues),
                    "major_issues": len(major_issues),
                    "minor_issues": len(minor_issues),
                },
                timestamp=datetime.now(),
            )
        ],
    }
