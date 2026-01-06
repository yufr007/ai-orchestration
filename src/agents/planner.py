"""Planner agent - researches and creates implementation plans."""

import json
from typing import Any

from src.agents.base import BaseAgent
from src.core.state import OrchestrationState, AgentRole
from src.tools.perplexity import research_with_perplexity
from src.tools.github import get_issue_details, get_repository_context


class PlannerAgent(BaseAgent):
    """Plans implementation based on requirements using Perplexity research."""

    def __init__(self):
        super().__init__(role=AgentRole.PLANNER, temperature=0.3)

    def get_system_prompt(self) -> str:
        return """You are an elite Technical Lead / CTO responsible for planning software implementations.

Your role:
1. Analyze requirements deeply (issues, specs, or descriptions)
2. Research best practices, patterns, and relevant documentation using Perplexity
3. Break down work into clear, actionable tasks
4. Define acceptance criteria and technical approach
5. Identify risks and dependencies
6. Specify which files need to be created/modified

Output a structured JSON plan with:
{
  "summary": "Brief overview of the work",
  "approach": "Technical approach and architecture decisions",
  "tasks": [
    {
      "id": 1,
      "title": "Task description",
      "type": "feature|bugfix|refactor|test|docs",
      "files": ["path/to/file.py"],
      "dependencies": [task_ids],
      "acceptance_criteria": ["criteria1", "criteria2"],
      "estimated_complexity": "low|medium|high"
    }
  ],
  "risks": ["potential issue 1", "potential issue 2"],
  "research_notes": "Key findings from research"
}

Be specific, actionable, and production-focused."""

    async def execute(self, state: OrchestrationState) -> dict[str, Any]:
        """Execute planning workflow."""
        repo = state["repo"]
        issue_number = state.get("issue_number")
        spec_content = state.get("spec_content")

        # Gather requirements
        if issue_number:
            issue = await get_issue_details(repo, issue_number)
            requirements = f"Issue #{issue_number}: {issue['title']}\n\n{issue['body']}"
        elif spec_content:
            requirements = spec_content
        else:
            return {
                "output": "No requirements provided (no issue or spec)",
                "artifacts": {},
                "metadata": {"status": "failed"},
            }

        # Get repository context
        repo_context = await get_repository_context(repo)

        # Research relevant patterns and best practices
        research_query = f"""Based on these requirements: {requirements[:500]}...
        
What are the best practices, patterns, and implementation approaches for this in Python?"""

        research_results = await research_with_perplexity(research_query)

        # Generate plan using LLM
        user_message = f"""Create a detailed implementation plan.

Requirements:
{requirements}

Repository Context:
- Language: {repo_context.get('language', 'Unknown')}
- Framework: {repo_context.get('framework', 'Unknown')}
- Structure: {repo_context.get('structure', 'Unknown')}

Research Findings:
{research_results}

Provide a complete JSON plan following the specified schema."""

        plan_json = await self._call_llm(self.get_system_prompt(), user_message)

        # Parse plan
        try:
            # Extract JSON from markdown code blocks if present
            if "```json" in plan_json:
                plan_json = plan_json.split("```json")[1].split("```")[0].strip()
            elif "```" in plan_json:
                plan_json = plan_json.split("```")[1].split("```")[0].strip()

            plan = json.loads(plan_json)
        except json.JSONDecodeError:
            self.logger.error("Failed to parse plan JSON", raw_response=plan_json)
            # Fallback: create basic plan
            plan = {
                "summary": "Implementation plan",
                "approach": plan_json,
                "tasks": [
                    {
                        "id": 1,
                        "title": "Implement requirements",
                        "type": "feature",
                        "files": [],
                        "dependencies": [],
                        "acceptance_criteria": ["Meets requirements"],
                        "estimated_complexity": "medium",
                    }
                ],
                "risks": [],
                "research_notes": research_results,
            }

        return {
            "output": f"Created plan with {len(plan['tasks'])} tasks",
            "plan": plan,
            "tasks": plan["tasks"],
            "artifacts": {
                "plan_json": plan,
                "research_results": research_results,
            },
            "metadata": {
                "requirements_length": len(requirements),
                "task_count": len(plan["tasks"]),
                "research_query": research_query,
            },
        }


async def planner_node(state: OrchestrationState) -> dict[str, Any]:
    """LangGraph node for planner agent."""
    agent = PlannerAgent()
    return await agent.invoke(state)
