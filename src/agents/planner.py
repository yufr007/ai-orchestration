"""Planner agent - Research and task breakdown."""

import asyncio
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.perplexity_mcp import perplexity_research
from src.tools.github_tools import get_issue_details, get_file_tree


PLANNER_SYSTEM_PROMPT = """You are an elite Tech Lead / Architect at a Silicon Valley startup.

Your role:
- Analyze requirements from issues, specs, or PRs
- Research best practices and design patterns using Perplexity
- Break down work into concrete, implementable tasks
- Define success criteria and testing strategy
- Identify dependencies and risks

Output a structured plan with:
1. Overview and objectives
2. Research findings (technologies, patterns, examples)
3. Task breakdown with priorities
4. File changes required
5. Testing approach
6. Definition of done

Be specific. Each task should be clear enough for a junior engineer to execute.
"""


async def planner_node(state: OrchestrationState) -> dict[str, Any]:
    """Planner agent: Research requirements and create implementation plan."""
    settings = get_settings()
    started_at = datetime.now()

    try:
        # Initialize LLM
        llm = ChatAnthropic(
            model=settings.default_agent_model,
            temperature=0.3,  # Higher for creative planning
            api_key=settings.anthropic_api_key,
        )

        # Gather context
        context_parts = []

        # Get issue/PR details if specified
        if state.get("issue_number"):
            issue = await get_issue_details(state["repo"], state["issue_number"])
            context_parts.append(f"## Issue #{state['issue_number']}\n\n{issue}")

        # Add spec content if provided
        if state.get("spec_content"):
            context_parts.append(f"## Specification\n\n{state['spec_content']}")

        # Get repository structure for context
        file_tree = await get_file_tree(state["repo"])
        context_parts.append(f"## Repository Structure\n\n{file_tree}")

        context = "\n\n".join(context_parts)

        # Research phase: Use Perplexity for best practices
        research_query = f"""Best practices and modern patterns for implementing:
{context[:500]}  # Truncate for query

Focus on: architecture patterns, testing strategies, error handling, performance.
"""

        research_results = await perplexity_research(research_query)

        # Planning phase: Generate structured plan
        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(
                content=f"""Create a detailed implementation plan.

# Context
{context}

# Research Findings
{research_results}

# Instructions
Provide:
1. High-level approach and architecture decisions
2. Detailed task breakdown (be specific about files and changes)
3. Testing strategy
4. Success criteria
5. Potential risks and mitigations

Format as structured markdown.
"""
            ),
        ]

        response = await llm.ainvoke(messages)
        plan_content = response.content

        # Parse tasks from plan (simplified - production would use structured output)
        tasks = parse_tasks_from_plan(plan_content)

        # Create agent result
        agent_result: AgentResult = {
            "agent": AgentRole.PLANNER,
            "status": TaskStatus.COMPLETED,
            "output": plan_content,
            "artifacts": {
                "research": research_results,
                "tasks": tasks,
            },
            "metadata": {
                "research_query": research_query,
                "task_count": len(tasks),
            },
            "timestamp": datetime.now(),
        }

        # Update state
        return {
            "plan": {"content": plan_content, "research": research_results},
            "tasks": tasks,
            "agent_results": state.get("agent_results", []) + [agent_result],
            "current_agent": AgentRole.PLANNER,
            "next_agents": [AgentRole.CODER] if tasks else [],
        }

    except Exception as e:
        # Error handling
        agent_result: AgentResult = {
            "agent": AgentRole.PLANNER,
            "status": TaskStatus.FAILED,
            "output": f"Planning failed: {str(e)}",
            "artifacts": {},
            "metadata": {"error": str(e)},
            "timestamp": datetime.now(),
        }

        return {
            "agent_results": state.get("agent_results", []) + [agent_result],
            "error": str(e),
            "current_agent": AgentRole.PLANNER,
            "next_agents": [],
        }


def parse_tasks_from_plan(plan: str) -> list[dict[str, Any]]:
    """Extract structured tasks from plan text.

    In production, use structured output or better parsing.
    This is a simplified implementation.
    """
    tasks = []
    lines = plan.split("\n")

    current_task = None
    for line in lines:
        # Look for task markers (numbers, bullets, etc.)
        line = line.strip()
        if not line:
            continue

        # Simple heuristic: lines starting with numbers or bullets
        if line[0].isdigit() or line.startswith("-") or line.startswith("*"):
            if current_task:
                tasks.append(current_task)

            # Extract task description
            desc = line.lstrip("0123456789.-* ").strip()
            if desc:
                current_task = {
                    "description": desc,
                    "status": "pending",
                    "priority": len(tasks) + 1,
                }

    if current_task:
        tasks.append(current_task)

    return tasks if tasks else [{"description": "Implement requirements", "status": "pending", "priority": 1}]
