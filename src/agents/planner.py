"""Planner Agent - Research and task decomposition using Perplexity MCP."""

from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.perplexity import perplexity_research
from src.tools.github import get_issue_details, get_pr_details


PLANNER_SYSTEM_PROMPT = """You are an elite Technical Lead and Product Manager responsible for planning software development work.

Your responsibilities:
1. Understand requirements deeply through research and issue/spec analysis
2. Research best practices, existing patterns, and architectural decisions
3. Break down work into granular, implementable tasks
4. Identify dependencies, risks, and technical constraints
5. Create a detailed execution plan for the engineering team

For each task, specify:
- Clear objective and acceptance criteria
- Files to create/modify with rationale
- Dependencies on other tasks
- Estimated complexity (low/medium/high)
- Testing requirements

Output Format:
{
  "summary": "Brief overview of the work",
  "research_findings": ["Key insight 1", "Key insight 2"],
  "architecture_decisions": ["Decision 1 with rationale"],
  "tasks": [
    {
      "id": "task_1",
      "title": "Task title",
      "description": "Detailed description",
      "files": ["path/to/file.py"],
      "dependencies": [],
      "complexity": "medium",
      "acceptance_criteria": ["Criteria 1", "Criteria 2"],
      "tests_required": ["Test type 1"]
    }
  ],
  "risks": ["Identified risk 1"],
  "estimated_effort": "2-3 hours"
}

Be thorough, precise, and production-focused."""


async def planner_node(state: OrchestrationState) -> dict[str, Any]:
    """Planner agent: Research and create execution plan."""
    settings = get_settings()
    
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
        print(f"📋 Fetching issue #{state['issue_number']}...")
        issue_data = await get_issue_details(
            repo=state["repo"],
            issue_number=state["issue_number"],
        )
        context_parts.append(f"### GitHub Issue\n{issue_data}")
    
    # Get PR details if in review mode
    if state.get("pr_number"):
        print(f"🔍 Fetching PR #{state['pr_number']}...")
        pr_data = await get_pr_details(
            repo=state["repo"],
            pr_number=state["pr_number"],
        )
        context_parts.append(f"### Pull Request\n{pr_data}")
    
    # Include spec if provided
    if state.get("spec_content"):
        context_parts.append(f"### Specification\n{state['spec_content']}")
    
    # Research best practices using Perplexity
    print("🔬 Researching best practices and patterns...")
    research_queries = [
        f"Best practices for implementing {state.get('spec_content', 'this feature')[:100]}",
        f"Common pitfalls and solutions for {state.get('spec_content', 'similar work')[:100]}",
        "Production-grade code patterns and testing strategies",
    ]
    
    research_results = []
    for query in research_queries[:2]:  # Limit to 2 queries to manage costs
        result = await perplexity_research(query)
        research_results.append(result)
    
    context_parts.append("### Research Findings\n" + "\n\n".join(research_results))
    
    # Construct full context
    full_context = "\n\n".join(context_parts)
    
    # Generate plan
    print("📝 Generating execution plan...")
    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=f"""Create a detailed execution plan for the following work:

{full_context}

Repository: {state['repo']}
Mode: {state.get('mode', 'autonomous')}

Provide a comprehensive plan in the specified JSON format."""),
    ]
    
    response = await llm.ainvoke(messages)
    plan_text = response.content
    
    # Parse plan (in production, use structured output or json.loads)
    import json
    try:
        # Try to extract JSON from markdown code blocks
        if "```json" in plan_text:
            plan_text = plan_text.split("```json")[1].split("```")[0].strip()
        elif "```" in plan_text:
            plan_text = plan_text.split("```")[1].split("```")[0].strip()
        
        plan = json.loads(plan_text)
    except json.JSONDecodeError:
        # Fallback: treat as plain text plan
        plan = {
            "summary": "Plan generated (parsing error, using raw text)",
            "tasks": [{"id": "task_1", "description": plan_text}],
        }
    
    print(f"✅ Plan created with {len(plan.get('tasks', []))} tasks")
    
    # Create agent result
    agent_result: AgentResult = {
        "agent": AgentRole.PLANNER,
        "status": TaskStatus.COMPLETED,
        "output": plan_text,
        "artifacts": {"plan": plan},
        "metadata": {
            "research_queries": research_queries[:2],
            "tasks_count": len(plan.get("tasks", [])),
        },
        "timestamp": datetime.now(),
    }
    
    return {
        "plan": plan,
        "tasks": plan.get("tasks", []),
        "agent_results": [*state.get("agent_results", []), agent_result],
        "current_agent": AgentRole.PLANNER,
    }
