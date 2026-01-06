"""Planner agent - Research and task decomposition using Perplexity MCP."""

from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.perplexity import research_with_perplexity
from src.tools.github import get_issue_details, get_pr_details


PLANNER_SYSTEM_PROMPT = """You are an elite Tech Lead / CTO planning software implementations.

Your responsibilities:
1. Research best practices and patterns using Perplexity
2. Analyze requirements from GitHub issues or specs
3. Break down work into actionable, parallelizable tasks
4. Define file-level changes with clear acceptance criteria
5. Identify dependencies and execution order
6. Ensure plans follow production-grade standards

Output Format:
{
  "tasks": [
    {
      "id": "task-1",
      "title": "Brief description",
      "type": "create|update|delete|test",
      "files": ["path/to/file.py"],
      "dependencies": ["task-0"],
      "acceptance_criteria": ["Criterion 1", "Criterion 2"],
      "priority": 1
    }
  ],
  "research_findings": {
    "patterns": ["Pattern 1", "Pattern 2"],
    "risks": ["Risk 1"],
    "recommendations": ["Rec 1"]
  },
  "estimated_complexity": "low|medium|high"
}

Be thorough but concise. Think in terms of production systems that will be maintained long-term.
"""


async def planner_node(state: OrchestrationState) -> dict[str, Any]:
    """Planner agent node - research and create execution plan."""
    settings = get_settings()

    # Initialize LLM
    llm = ChatAnthropic(
        model=settings.default_agent_model,
        temperature=0.3,
        api_key=settings.anthropic_api_key,
    )

    # Gather context
    repo = state["repo"]
    issue_number = state.get("issue_number")
    spec_content = state.get("spec_content")

    context = {}

    # Get issue details if provided
    if issue_number:
        issue_data = await get_issue_details(repo, issue_number)
        context["issue"] = issue_data

    # Get PR details if in review mode
    pr_number = state.get("pr_number")
    if pr_number:
        pr_data = await get_pr_details(repo, pr_number)
        context["pr"] = pr_data

    # Research with Perplexity
    research_queries = []
    if issue_number and context.get("issue"):
        title = context["issue"].get("title", "")
        research_queries.append(f"Best practices for implementing: {title}")
        research_queries.append(f"Common pitfalls when implementing: {title}")

    research_findings = []
    if research_queries:
        for query in research_queries[:2]:  # Limit to 2 queries
            result = await research_with_perplexity(query)
            research_findings.append(result)

    # Build prompt
    user_content = f"""Repository: {repo}

"""

    if context.get("issue"):
        issue = context["issue"]
        user_content += f"""Issue #{issue_number}: {issue.get('title', '')}
{issue.get('body', '')}

"""

    if spec_content:
        user_content += f"""Specification:
{spec_content}

"""

    if research_findings:
        user_content += """Research Findings:
"""
        for i, finding in enumerate(research_findings, 1):
            user_content += f"""
{i}. {finding.get('summary', '')}
   Key points: {', '.join(finding.get('key_points', []))}
"""

    user_content += """\n\nCreate a detailed implementation plan with specific tasks, file changes, and acceptance criteria."""

    # Call LLM
    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ]

    response = await llm.ainvoke(messages)

    # Parse response (in production, use structured output)
    import json

    try:
        plan = json.loads(response.content)
    except json.JSONDecodeError:
        # Fallback: extract JSON from markdown code blocks
        content = response.content
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            plan = json.loads(content[json_start:json_end].strip())
        else:
            # Fallback plan
            plan = {
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Implement feature",
                        "type": "update",
                        "files": [],
                        "dependencies": [],
                        "acceptance_criteria": ["Feature works"],
                        "priority": 1,
                    }
                ],
                "research_findings": {},
                "estimated_complexity": "medium",
            }

    # Create agent result
    agent_result: AgentResult = {
        "agent": AgentRole.PLANNER,
        "status": TaskStatus.COMPLETED,
        "output": response.content,
        "artifacts": {"plan": plan, "research": research_findings},
        "metadata": {"queries_executed": len(research_queries)},
        "timestamp": datetime.now(),
    }

    # Update state
    return {
        "plan": plan,
        "tasks": plan.get("tasks", []),
        "agent_results": [agent_result],
        "current_agent": AgentRole.PLANNER,
        "messages": [response],
    }
