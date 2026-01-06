"""Planner agent - Research and task decomposition."""

from typing import Any

from src.agents.base import BaseAgent
from src.core.state import OrchestrationState, AgentRole
from src.tools.perplexity import PerplexityTool
from src.tools.github_tools import GitHubTools


class PlannerAgent(BaseAgent):
    """Agent responsible for researching context and creating implementation plans."""

    def __init__(self):
        super().__init__(role=AgentRole.PLANNER, temperature=0.3)
        self.perplexity = PerplexityTool()
        self.github = GitHubTools()

    async def execute(self, state: OrchestrationState) -> dict[str, Any]:
        """Execute planning logic."""
        repo = state["repo"]
        issue_number = state.get("issue_number")
        spec_content = state.get("spec_content")

        # Gather context
        context = await self._gather_context(repo, issue_number, spec_content)

        # Research relevant patterns and best practices
        research = await self._research_approach(context)

        # Create implementation plan
        plan = await self._create_plan(context, research)

        # Decompose into tasks
        tasks = self._decompose_tasks(plan)

        return {
            "plan": plan,
            "tasks": tasks,
            "output": f"Created plan with {len(tasks)} tasks",
            "artifacts": {"context": context, "research": research},
            "metadata": {"issue_number": issue_number, "repo": repo},
        }

    async def _gather_context(self, repo: str, issue_number: int | None, spec_content: str | None) -> dict:
        """Gather all relevant context from GitHub and specs."""
        context = {"repo": repo}

        if issue_number:
            issue = await self.github.get_issue(repo, issue_number)
            context["issue"] = issue

        if spec_content:
            context["spec"] = spec_content
        else:
            # Try to find spec from issue body or labels
            if issue_number:
                context["spec"] = context.get("issue", {}).get("body", "")

        # Get repo structure
        repo_info = await self.github.get_repo_info(repo)
        context["repo_info"] = repo_info

        return context

    async def _research_approach(self, context: dict) -> dict:
        """Use Perplexity to research relevant patterns and approaches."""
        spec = context.get("spec", "")
        repo_info = context.get("repo_info", {})
        language = repo_info.get("language", "Python")

        # Extract key technologies from spec
        query = f"Best practices for implementing: {spec[:200]}... using {language}"

        research = await self.perplexity.search(query)
        return {"query": query, "results": research}

    async def _create_plan(self, context: dict, research: dict) -> dict:
        """Create detailed implementation plan using LLM."""
        system_prompt = """You are an elite Technical Lead planning software implementations.

Your job:
1. Analyze the requirements and context
2. Incorporate research findings and best practices
3. Create a detailed, step-by-step implementation plan
4. Identify risks, dependencies, and technical decisions
5. Estimate complexity and suggest file structure

Output a JSON plan with:
- overview: string summary
- architecture: key architectural decisions
- tasks: array of task objects with {id, title, description, files, dependencies, complexity}
- risks: array of identified risks
- testing_strategy: approach for testing"""

        user_message = f"""Context:
{context}

Research:
{research}

Create an implementation plan."""

        messages = self.format_messages(system_prompt, user_message)
        response = await self.llm.ainvoke(messages)

        # Parse LLM response (assuming JSON output)
        import json

        try:
            plan = json.loads(response.content)
        except json.JSONDecodeError:
            # Fallback: create basic plan
            plan = {
                "overview": response.content,
                "tasks": [],
                "architecture": {},
                "risks": [],
                "testing_strategy": "Unit tests + integration tests",
            }

        return plan

    def _decompose_tasks(self, plan: dict) -> list[dict]:
        """Extract and format tasks from plan."""
        tasks = plan.get("tasks", [])

        # Ensure each task has required fields
        for i, task in enumerate(tasks):
            task.setdefault("id", f"task-{i + 1}")
            task.setdefault("status", "pending")
            task.setdefault("dependencies", [])
            task.setdefault("files", [])
            task.setdefault("complexity", "medium")

        return tasks


# Node function for LangGraph
async def planner_node(state: OrchestrationState) -> dict[str, Any]:
    """Planner node for LangGraph workflow."""
    agent = PlannerAgent()
    return await agent.invoke(state)
