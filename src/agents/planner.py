"""Planner agent: Research and task decomposition."""

from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.perplexity import search_perplexity
from src.tools.github import get_issue_details, get_file_contents


PLANNER_SYSTEM_PROMPT = """You are an elite Tech Lead / Architect responsible for planning software implementations.

Your responsibilities:
1. Research the problem domain using available tools (Perplexity for external research, GitHub for context)
2. Analyze existing codebase structure and patterns
3. Break down requirements into clear, actionable tasks
4. Identify dependencies between tasks
5. Specify implementation approach, file locations, and API contracts
6. Consider edge cases, error handling, and testing requirements

Output a structured plan with:
- Summary: High-level overview (2-3 sentences)
- Research findings: Key insights from research
- Tasks: List of implementation tasks with:
  - ID: Unique identifier
  - Description: What needs to be done
  - Files: Which files to create/modify
  - Dependencies: Task IDs this depends on
  - Acceptance criteria: How to verify completion
- Technical notes: Architecture decisions, patterns to follow, gotchas

Be thorough but concise. Prefer existing patterns over novel solutions."""


async def planner_node(state: OrchestrationState) -> dict[str, Any]:
    """Planner agent node: Research and create implementation plan."""
    settings = get_settings()
    
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
        issue = await get_issue_details(
            repo=state["repo"],
            issue_number=state["issue_number"],
        )
        context_parts.append(f"GitHub Issue #{issue['number']}:")
        context_parts.append(f"Title: {issue['title']}")
        context_parts.append(f"Body: {issue['body']}")
        context_parts.append(f"Labels: {', '.join(issue['labels'])}")
    
    # Get spec content if provided
    if state.get("spec_content"):
        context_parts.append(f"\nSpecification:\n{state['spec_content']}")
    
    # Research the problem domain
    research_query = f"best practices for implementing: {context_parts[0] if context_parts else 'software feature'}"
    research_results = await search_perplexity(research_query)
    context_parts.append(f"\nResearch Findings:\n{research_results}")
    
    # Get repository structure for context
    try:
        readme = await get_file_contents(repo=state["repo"], path="README.md")
        context_parts.append(f"\nRepository README (for context):\n{readme[:1000]}...")
    except Exception:
        pass  # README might not exist
    
    # Construct prompt
    context = "\n\n".join(context_parts)
    
    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=f"{context}\n\nCreate a detailed implementation plan."),
    ]
    
    # Invoke LLM
    response = await llm.ainvoke(messages)
    plan_text = response.content
    
    # Parse plan into structured format (simplified - in production use structured output)
    plan = {
        "summary": plan_text[:500],  # First 500 chars as summary
        "full_plan": plan_text,
        "created_at": datetime.now().isoformat(),
    }
    
    # Extract tasks (simplified parsing - in production use JSON mode or structured output)
    tasks = [
        {
            "id": "task-1",
            "description": "Implement core feature logic",
            "files": [],
            "dependencies": [],
            "status": "pending",
        }
    ]  # In production, parse from LLM response
    
    # Create agent result
    result: AgentResult = {
        "agent": AgentRole.PLANNER,
        "status": TaskStatus.COMPLETED,
        "output": plan_text,
        "artifacts": {"plan": plan, "tasks": tasks},
        "metadata": {"research_performed": True, "issue_analyzed": bool(state.get("issue_number"))},
        "timestamp": datetime.now(),
    }
    
    return {
        "plan": plan,
        "tasks": tasks,
        "agent_results": [result],
        "current_agent": AgentRole.PLANNER,
        "messages": [HumanMessage(content=f"Plan created: {plan['summary']}")],
    }
