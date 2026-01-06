"""Planner Agent - Research and task decomposition using Perplexity MCP."""

from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.perplexity import perplexity_research
from src.tools.github import get_issue_details, get_repository_context


PLANNER_SYSTEM_PROMPT = """You are an elite Tech Lead / CTO for an AI development team.

Your role:
1. Analyze requirements from GitHub issues or spec documents
2. Research best practices and architectural patterns using Perplexity
3. Break down work into granular, actionable tasks
4. Define acceptance criteria and testing requirements
5. Identify dependencies and blockers
6. Estimate complexity and suggest file structure

Output a structured plan with:
- Executive summary
- Technical approach and architecture decisions
- Task breakdown with clear ownership (coder, tester, devops, security)
- Files to create/modify
- Testing strategy
- Risk assessment

Be specific, production-focused, and enterprise-grade. No placeholders or TODOs."""


async def planner_node(state: OrchestrationState) -> dict[str, Any]:
    """Planner agent node - creates execution plan from requirements."""
    settings = get_settings()
    print(f"\n{'='*80}\n🎯 PLANNER AGENT STARTING\n{'='*80}")

    try:
        # Extract input
        repo = state["repo"]
        issue_number = state.get("issue_number")
        spec_content = state.get("spec_content")

        # Gather context
        context_parts = []

        # Get repository context
        repo_context = await get_repository_context(repo)
        context_parts.append(f"Repository: {repo}")
        context_parts.append(f"Main language: {repo_context.get('language', 'Unknown')}")
        context_parts.append(f"Description: {repo_context.get('description', 'N/A')}")

        # Get issue details if provided
        if issue_number:
            issue_details = await get_issue_details(repo, issue_number)
            context_parts.append(f"\nIssue #{issue_number}: {issue_details['title']}")
            context_parts.append(f"Body:\n{issue_details['body']}")
            if issue_details.get("labels"):
                context_parts.append(f"Labels: {', '.join(issue_details['labels'])}")

        # Add spec content if provided
        if spec_content:
            context_parts.append(f"\nSpecification:\n{spec_content}")

        context = "\n".join(context_parts)

        # Research phase: Use Perplexity to gather best practices
        research_query = f"""Best practices and architecture patterns for: {issue_details.get('title', 'the task')} 
in {repo_context.get('language', 'Python')}. Focus on production-ready, enterprise-grade solutions."""

        print(f"🔍 Researching: {research_query[:100]}...")
        research_results = await perplexity_research(research_query)

        # Planning phase: Generate structured plan
        llm = ChatAnthropic(
            model=settings.default_agent_model,
            temperature=settings.default_temperature,
            api_key=settings.anthropic_api_key,
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=PLANNER_SYSTEM_PROMPT),
                HumanMessage(
                    content=f"""Context:
{context}

Research findings:
{research_results}

Create a detailed implementation plan following the structure in your system prompt.
Output as JSON with keys: summary, architecture, tasks, files, testing, risks."""
                ),
            ]
        )

        print("💭 Generating execution plan...")
        response = await llm.ainvoke(prompt.format_messages())

        # Parse plan (assuming structured JSON output)
        import json

        try:
            plan = json.loads(response.content)
        except json.JSONDecodeError:
            # Fallback: treat as text plan
            plan = {
                "summary": "Plan generated",
                "architecture": response.content[:500],
                "tasks": [{"id": 1, "description": "Implement based on analysis", "owner": "coder"}],
                "files": [],
                "testing": "Generate comprehensive tests",
                "risks": "Standard implementation risks",
            }

        # Format tasks for state
        tasks = [
            {
                "id": i,
                "description": task.get("description", ""),
                "owner": task.get("owner", "coder"),
                "status": "pending",
                "dependencies": task.get("dependencies", []),
            }
            for i, task in enumerate(plan.get("tasks", []), 1)
        ]

        # Create agent result
        agent_result: AgentResult = {
            "agent": AgentRole.PLANNER,
            "status": TaskStatus.COMPLETED,
            "output": response.content,
            "artifacts": {"plan": plan, "research": research_results},
            "metadata": {"repo": repo, "issue_number": issue_number},
            "timestamp": datetime.now(),
        }

        print(f"✅ Plan created with {len(tasks)} tasks")
        print(f"📋 Summary: {plan.get('summary', 'N/A')[:200]}...")

        return {
            "plan": plan,
            "tasks": tasks,
            "agent_results": [agent_result],
            "current_agent": AgentRole.PLANNER,
            "next_agents": [AgentRole.CODER],
        }

    except Exception as e:
        print(f"❌ Planner failed: {e}")
        agent_result: AgentResult = {
            "agent": AgentRole.PLANNER,
            "status": TaskStatus.FAILED,
            "output": str(e),
            "artifacts": {},
            "metadata": {},
            "timestamp": datetime.now(),
        }
        return {"agent_results": [agent_result], "error": str(e)}
