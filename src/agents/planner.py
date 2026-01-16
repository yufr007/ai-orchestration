"""Planner agent: Research and task decomposition."""

from src.core.state import OrchestrationState, AgentRole, TaskStatus
from src.agents.base import BaseAgent
from src.tools.perplexity import perplexity_research
from src.tools.github_adapter import get_issue_details, get_pr_details

PLANNER_SYSTEM_PROMPT = """You are an elite Tech Lead / Architect for a Silicon Valley startup.

Your role:
1. Deeply understand requirements from issues, PRs, or specifications
2. Research technical approaches using Perplexity (latest frameworks, best practices, security)
3. Decompose work into granular, parallelizable tasks
4. Define clear acceptance criteria and test requirements
5. Identify dependencies, risks, and architecture decisions

Output format:
- Executive summary (2-3 sentences)
- Technical approach with justification
- Ordered task list with:
  * Task ID
  * Description
  * Estimated complexity (S/M/L/XL)
  * Dependencies
  * Files to modify/create
  * Test requirements
- Architecture decisions and rationale
- Security considerations
- Performance implications

Be proactive, thorough, and production-focused. No hand-waving.
"""


class PlannerAgent(BaseAgent):
    """Agent responsible for planning and task decomposition."""

    def __init__(self) -> None:
        super().__init__(role=AgentRole.PLANNER, system_prompt=PLANNER_SYSTEM_PROMPT)

    async def plan(self, state: OrchestrationState) -> OrchestrationState:
        """Main planning workflow."""
        self.log_start("plan")

        try:
            # 1. Gather requirements
            requirements = await self._gather_requirements(state)

            # 2. Research technical approach
            research_context = await self._research_approach(requirements)

            # 3. Generate plan
            plan = await self._generate_plan(requirements, research_context)

            # 4. Update state
            state["plan"] = plan
            state["tasks"] = plan.get("tasks", [])
            state["agent_results"].append(
                self.create_result(
                    status=TaskStatus.COMPLETED,
                    output=plan.get("summary", "Plan completed"),
                    artifacts={"plan": plan, "research": research_context},
                    metadata={"task_count": len(plan.get("tasks", []))},
                )
            )

            self.log_complete("plan", TaskStatus.COMPLETED)
            return state

        except Exception as e:
            self.log_error("plan", e)
            state["error"] = str(e)
            state["agent_results"].append(
                self.create_result(
                    status=TaskStatus.FAILED,
                    output=f"Planning failed: {str(e)}",
                    metadata={"error_type": type(e).__name__},
                )
            )
            return state

    async def _gather_requirements(self, state: OrchestrationState) -> dict:
        """Gather requirements from issue, PR, or spec."""
        requirements = {"source": "unknown", "content": ""}

        if state.get("issue_number"):
            issue = await get_issue_details(state["repo"], state["issue_number"])
            requirements["source"] = "issue"
            requirements["content"] = f"# {issue['title']}\n\n{issue['body']}"
            requirements["labels"] = issue.get("labels", [])

        elif state.get("pr_number"):
            pr = await get_pr_details(state["repo"], state["pr_number"])
            requirements["source"] = "pr"
            requirements["content"] = f"# {pr['title']}\n\n{pr['body']}"
            requirements["files_changed"] = pr.get("files", [])

        elif state.get("spec_content"):
            requirements["source"] = "spec"
            requirements["content"] = state["spec_content"]

        return requirements

    async def _research_approach(self, requirements: dict) -> str:
        """Research technical approach using Perplexity."""
        # Extract key technical terms for research
        content = requirements["content"]

        # Generate research query
        research_query = f"""Based on this software requirement, what are:
1. Best practices and modern approaches
2. Popular frameworks/libraries (with versions)
3. Security considerations
4. Performance optimization strategies

Requirement:
{content[:1000]}  # Limit length for API
"""

        # Use Perplexity for research
        research_result = await perplexity_research(research_query)
        return research_result

    async def _generate_plan(self, requirements: dict, research: str) -> dict:
        """Generate detailed plan using LLM."""
        user_message = f"""Generate a detailed implementation plan.

## Requirements
{requirements['content']}

## Research Findings
{research}

## Current State
- Repository: {self.settings.github_owner}/...
- Source: {requirements['source']}

Generate a complete plan following your system prompt format.
"""

        plan_text = await self.invoke_llm(user_message)

        # Parse plan into structured format
        # (In production, use structured output or JSON mode)
        return {
            "summary": plan_text[:200],
            "full_plan": plan_text,
            "tasks": self._extract_tasks(plan_text),
            "architecture_decisions": [],
            "security_notes": [],
        }

    def _extract_tasks(self, plan_text: str) -> list[dict]:
        """Extract tasks from plan text."""
        # Simple extraction - in production, use structured output
        tasks = []
        lines = plan_text.split("\n")

        for i, line in enumerate(lines):
            if line.strip().startswith(("- Task", "1.", "2.", "3.")):
                tasks.append(
                    {
                        "id": f"task_{len(tasks)+1}",
                        "description": line.strip(),
                        "status": "pending",
                        "complexity": "M",
                    }
                )

        return tasks if tasks else [{"id": "task_1", "description": "Implement feature", "status": "pending", "complexity": "M"}]


async def planner_node(state: OrchestrationState) -> OrchestrationState:
    """LangGraph node for planner agent."""
    agent = PlannerAgent()
    return await agent.plan(state)
