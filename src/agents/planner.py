"""Planner agent - Research and task decomposition using Perplexity MCP."""

from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentResult, AgentRole, OrchestrationState, TaskStatus
from src.tools.perplexity import PerplexityMCP
from src.tools.github import GitHubTools


PLANNER_SYSTEM_PROMPT = """You are an elite CTO/Tech Lead for an autonomous software development team.

Your role:
- Analyze GitHub issues or specifications to understand requirements
- Research similar implementations and best practices using Perplexity
- Break down work into concrete, parallelizable tasks
- Define acceptance criteria and testing requirements
- Set architectural constraints and quality standards

You have access to:
- Perplexity search for research (latest patterns, libraries, examples)
- GitHub API to read issues, analyze codebase, check existing patterns

Output a structured plan with:
1. **Context**: Summary of the requirement and research findings
2. **Architecture**: Key decisions, patterns to follow, files to modify/create
3. **Tasks**: Ordered list of implementation tasks with clear inputs/outputs
4. **Acceptance Criteria**: How to validate success
5. **Testing Requirements**: Unit tests, integration tests, edge cases

Be specific about file paths, function names, and implementation approaches.
Consider scalability, maintainability, and security from the start.
"""


async def planner_node(state: OrchestrationState) -> dict[str, Any]:
    """Plan the work by researching and decomposing into tasks."""
    settings = get_settings()

    # Initialize tools
    perplexity = PerplexityMCP()
    github = GitHubTools()

    # Get context from GitHub issue or spec
    context = ""
    if state.get("issue_number"):
        issue = await github.get_issue(state["repo"], state["issue_number"])
        context = f"GitHub Issue #{issue['number']}: {issue['title']}\n\n{issue['body']}"
    elif state.get("spec_content"):
        context = f"Specification:\n{state['spec_content']}"
    else:
        context = "No specific requirement provided - analyzing repository"

    # Research similar implementations
    research_query = f"Best practices and implementation patterns for: {context[:200]}"
    research_results = await perplexity.search(research_query)

    # Analyze existing codebase
    repo_structure = await github.get_repo_structure(state["repo"])
    existing_patterns = await github.analyze_code_patterns(state["repo"])

    # Build prompt for planning
    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(
            content=f"""Plan the implementation for this requirement:

{context}

**Research Results:**
{research_results}

**Current Repository Structure:**
{repo_structure}

**Existing Patterns:**
{existing_patterns}

Provide a detailed implementation plan."""
        ),
    ]

    # Initialize LLM
    llm = ChatAnthropic(
        model=settings.default_agent_model,
        temperature=0.3,
        api_key=settings.anthropic_api_key,
    )

    # Get plan from LLM
    response = await llm.ainvoke(messages)
    plan_content = response.content

    # Parse plan into structured format
    plan = _parse_plan(plan_content)
    tasks = _extract_tasks(plan)

    # Create agent result
    result: AgentResult = {
        "agent": AgentRole.PLANNER,
        "status": TaskStatus.COMPLETED,
        "output": plan_content,
        "artifacts": {"plan": plan, "tasks": tasks, "research": research_results},
        "metadata": {"model": settings.default_agent_model, "temperature": 0.3},
        "timestamp": datetime.now(),
    }

    return {
        "plan": plan,
        "tasks": tasks,
        "agent_results": [result],
        "current_agent": AgentRole.PLANNER,
        "messages": [HumanMessage(content=f"Plan completed: {len(tasks)} tasks identified")],
    }


def _parse_plan(content: str) -> dict[str, Any]:
    """Parse LLM output into structured plan."""
    # Simple parsing - in production, use more robust extraction
    return {
        "raw_content": content,
        "context": _extract_section(content, "Context"),
        "architecture": _extract_section(content, "Architecture"),
        "acceptance_criteria": _extract_section(content, "Acceptance Criteria"),
        "testing_requirements": _extract_section(content, "Testing Requirements"),
    }


def _extract_tasks(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract individual tasks from plan."""
    # Parse task list from raw content
    raw = plan.get("raw_content", "")
    tasks = []

    # Simple task extraction - look for numbered lists or task markers
    lines = raw.split("\n")
    current_task = None

    for line in lines:
        line = line.strip()
        # Detect task lines (e.g., "1. Create file...", "- Implement...")
        if line and (line[0].isdigit() or line.startswith("-") or line.startswith("*")):
            if current_task:
                tasks.append(current_task)
            current_task = {
                "description": line.lstrip("0123456789.-* "),
                "status": "pending",
                "assignee": "coder",
            }
        elif current_task and line:
            # Continuation of current task
            current_task["description"] += " " + line

    if current_task:
        tasks.append(current_task)

    return tasks


def _extract_section(content: str, section_name: str) -> str:
    """Extract a specific section from the plan."""
    lines = content.split("\n")
    in_section = False
    section_content = []

    for line in lines:
        if section_name.lower() in line.lower() and ("**" in line or "##" in line):
            in_section = True
            continue
        elif in_section and line.strip().startswith(("**", "##")):
            # Next section started
            break
        elif in_section:
            section_content.append(line)

    return "\n".join(section_content).strip()
