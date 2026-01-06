"""Planner agent: Research and task decomposition using Perplexity MCP."""

import json
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.perplexity import perplexity_research
from src.tools.github import get_issue_details, get_pr_details

settings = get_settings()

PLANNER_SYSTEM_PROMPT = """You are an elite Tech Lead responsible for planning software implementations.

Your responsibilities:
1. Research the problem domain using Perplexity to gather best practices and patterns
2. Analyze the issue/spec to understand requirements and acceptance criteria
3. Break down the work into concrete, actionable tasks
4. Identify dependencies and suggest implementation order
5. Consider edge cases, error handling, and testing requirements
6. Propose architecture decisions when needed

Output a structured JSON plan with:
- summary: Brief overview of the implementation
- research_findings: Key insights from Perplexity research
- tasks: Array of tasks with {id, title, description, dependencies, estimated_complexity, files_to_modify}
- risks: Potential issues to watch for
- testing_strategy: How this should be tested

Be thorough but concise. Focus on actionable guidance for the implementation team."""


async def planner_node(state: OrchestrationState) -> dict[str, Any]:
    """Execute the planner agent to create implementation plan."""
    print("\n🎯 PLANNER: Starting planning phase...")

    # Initialize LLM
    llm = ChatAnthropic(
        model=settings.default_agent_model,
        temperature=0.3,
        api_key=settings.anthropic_api_key,
    )

    # Gather context
    context_parts = []

    # Get issue details if provided
    if state.get("issue_number"):
        issue = await get_issue_details(state["repo"], state["issue_number"])
        context_parts.append(f"**Issue #{state['issue_number']}:**\n{issue['title']}\n\n{issue['body']}")

    # Get PR details if provided
    if state.get("pr_number"):
        pr = await get_pr_details(state["repo"], state["pr_number"])
        context_parts.append(f"**PR #{state['pr_number']}:**\n{pr['title']}\n\n{pr['body']}")

    # Add spec content if provided
    if state.get("spec_content"):
        context_parts.append(f"**Specification:**\n{state['spec_content']}")

    context = "\n\n".join(context_parts)

    if not context:
        return {
            "error": "No input provided (issue, PR, or spec)",
            "agent_results": [
                AgentResult(
                    agent=AgentRole.PLANNER,
                    status=TaskStatus.FAILED,
                    output="No context available for planning",
                    artifacts={},
                    metadata={},
                    timestamp=datetime.now(),
                )
            ],
        }

    # Research using Perplexity
    print("🔍 PLANNER: Researching best practices...")
    research_query = f"Best practices and implementation patterns for: {context[:200]}..."
    research_results = await perplexity_research(research_query)

    # Create plan
    print("📝 PLANNER: Creating implementation plan...")
    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(
            content=f"""Context:
{context}

Research findings:
{research_results}

Create a detailed implementation plan in JSON format."""
        ),
    ]

    response = await llm.ainvoke(messages)
    plan_text = response.content

    # Parse plan (extract JSON from markdown if needed)
    try:
        if "```json" in plan_text:
            plan_text = plan_text.split("```json")[1].split("```")[0].strip()
        elif "```" in plan_text:
            plan_text = plan_text.split("```")[1].split("```")[0].strip()
        plan = json.loads(plan_text)
    except json.JSONDecodeError:
        print("⚠️  PLANNER: Failed to parse JSON, using raw text")
        plan = {"summary": plan_text, "tasks": [], "research_findings": research_results}

    print(f"✅ PLANNER: Created plan with {len(plan.get('tasks', []))} tasks")

    return {
        "plan": plan,
        "tasks": plan.get("tasks", []),
        "current_agent": AgentRole.PLANNER,
        "agent_results": [
            AgentResult(
                agent=AgentRole.PLANNER,
                status=TaskStatus.COMPLETED,
                output=plan.get("summary", "Plan created"),
                artifacts={"plan": plan, "research": research_results},
                metadata={"task_count": len(plan.get("tasks", []))},
                timestamp=datetime.now(),
            )
        ],
    }
