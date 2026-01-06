"""Planner agent: Research requirements and decompose into tasks."""

from typing import Any

from src.agents.base import BaseAgent
from src.core.state import AgentRole, OrchestrationState
from src.tools.perplexity import PerplexityMCP
from src.tools.github import GitHubTools

PLANNER_SYSTEM_PROMPT = """You are an elite Software Architect and Tech Lead at a top Silicon Valley startup.

Your role:
1. Deeply understand requirements from GitHub issues or specifications
2. Research best practices, patterns, and similar implementations using Perplexity
3. Break down work into clear, actionable tasks for implementation team
4. Identify technical risks, dependencies, and architectural decisions
5. Specify test scenarios and acceptance criteria

You have access to:
- Perplexity: For researching patterns, libraries, best practices
- GitHub API: For reading issues, existing code, project structure

Output a structured plan in JSON format:
{
  "overview": "High-level summary",
  "research_findings": ["Key insights from research"],
  "architecture_decisions": [{"decision": "...", "rationale": "..."}],
  "tasks": [
    {
      "id": "task-1",
      "title": "Implement X",
      "description": "Detailed requirements",
      "files": ["path/to/file.py"],
      "dependencies": ["task-0"],
      "acceptance_criteria": ["..."],
      "estimated_complexity": "low|medium|high"
    }
  ],
  "test_scenarios": ["Scenario 1", "Scenario 2"],
  "risks": ["Risk 1", "Risk 2"]
}

Be thorough but concise. Focus on actionable technical details.
"""


class PlannerAgent(BaseAgent):
    """Agent responsible for research and task planning."""

    def __init__(self):
        super().__init__(AgentRole.PLANNER, PLANNER_SYSTEM_PROMPT)
        self.perplexity = PerplexityMCP()
        self.github = GitHubTools()

    async def execute(self, state: OrchestrationState) -> tuple[str, dict[str, Any]]:
        """Execute planning: research + task decomposition."""
        repo = state["repo"]
        issue_number = state.get("issue_number")
        spec_content = state.get("spec_content")

        # 1. Gather requirements
        if issue_number:
            issue = await self.github.get_issue(repo, issue_number)
            requirements = f"GitHub Issue #{issue_number}:\n{issue['title']}\n\n{issue['body']}"
        elif spec_content:
            requirements = f"Specification:\n{spec_content}"
        else:
            raise ValueError("Either issue_number or spec_content must be provided")

        # 2. Research with Perplexity
        research_queries = self._extract_research_queries(requirements)
        research_results = []
        for query in research_queries[:3]:  # Limit to 3 queries
            result = await self.perplexity.search(query)
            research_results.append(f"Query: {query}\nResults: {result}")

        # 3. Get repository context
        repo_structure = await self.github.get_repository_structure(repo)
        readme = await self.github.get_file_contents(repo, "README.md") or "No README"

        # 4. Generate plan with LLM
        user_message = f"""Requirements:
{requirements}

---
Research Findings:
{chr(10).join(research_results)}

---
Repository Structure:
{repo_structure}

README:
{readme[:2000]}...

---
Create a detailed implementation plan.
"""

        messages = self._format_messages(user_message)
        response = await self.llm.ainvoke(messages)

        plan_text = response.content

        # Parse JSON from response (extract from markdown if needed)
        import json
        import re

        json_match = re.search(r"```json\n(.*)\n```", plan_text, re.DOTALL)
        if json_match:
            plan_json = json.loads(json_match.group(1))
        else:
            # Try parsing entire response
            try:
                plan_json = json.loads(plan_text)
            except json.JSONDecodeError:
                # Fallback: create basic structure
                plan_json = {
                    "overview": "Failed to parse plan",
                    "tasks": [{"id": "task-1", "title": "Review plan manually"}],
                }

        return plan_text, {"plan": plan_json, "research": research_results}

    def _extract_research_queries(self, requirements: str) -> list[str]:
        """Extract key research queries from requirements."""
        # Simple heuristic: look for technology names, frameworks, patterns
        queries = []

        # Default query
        queries.append(f"Best practices for: {requirements[:100]}")

        # Look for specific technologies
        keywords = ["python", "typescript", "react", "fastapi", "docker", "kubernetes"]
        for keyword in keywords:
            if keyword.lower() in requirements.lower():
                queries.append(f"{keyword} implementation patterns examples")

        return queries[:3]


async def planner_node(state: OrchestrationState) -> OrchestrationState:
    """LangGraph node for planner agent."""
    agent = PlannerAgent()
    result = await agent.invoke(state)

    # Update state
    state["agent_results"].append(result)
    state["current_agent"] = AgentRole.PLANNER

    if result["status"] == "completed":
        plan_data = result["artifacts"].get("plan", {})
        state["plan"] = plan_data
        state["tasks"] = plan_data.get("tasks", [])

    return state
