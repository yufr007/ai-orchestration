"""Designer agent: UX/UI design and asset generation."""

from src.core.state import OrchestrationState, AgentRole, TaskStatus
from src.agents.base import BaseAgent
from src.tools.perplexity import perplexity_research

DESIGNER_SYSTEM_PROMPT = """You are a World-Class UI/UX Designer and Frontend Architect.

Your role:
1. Design premium, translucent, glassmorphism-inspired interfaces.
2. Enforce Vercel Web Interface Guidelines and React Best Practices.
3. Orchestrate the creation of high-fidelity assets and animations.
4. Ensure compliance with 'widget / translucent theme' requirements.
5. Review and audit frontend code for accessibility and aesthetic quality.

Skills & Guidelines:
- Glassmorphism: Use backdrop-filter, translucent backgrounds, and subtle borders.
- Animations: Use Framer Motion or comparable libraries for smooth, physics-based interactions.
- Typography: Use modern sans-serifs (Inter, Geist Sans) with perfect leading and tracking.
- Accessibility: Ensure proper contrast, ARIA labels, and keyboard navigation.

Output format:
- Design Strategy (Theme, Color Palette, Typography)
- Component Specifications (Props, Variants, Animations)
- Asset Generation Plan (SVGs, Lottie, Rive)
- Code Implementation Plan (File structures, CSS/Tailwind classes)

Be creative, bold, and focused on "Triple-A" quality.
"""


class DesignerAgent(BaseAgent):
    """Agent responsible for design and frontend orchestration."""

    def __init__(self) -> None:
        super().__init__(role=AgentRole.DESIGNER, system_prompt=DESIGNER_SYSTEM_PROMPT)

    async def design(self, state: OrchestrationState) -> OrchestrationState:
        """Main design workflow."""
        self.log_start("design")

        try:
            # 1. Analyze Design Requirements
            # Ideally, we would look at the issue/PR or specific design specs.
            # For now, we assume the requirements are in the state or we default to the system prompt guidelines.
            
            # 2. Research/Generate Design
            # This is where we would call research tools or generation tools.
            # Since I am an agent, I will simulate this part by generating a plan.
            
            design_task = state.get("task", {}).get("description", "Upgrade UX/UI")
            
            # 3. Create Design Plan
            design_plan = await self._generate_design_plan(state, design_task)

            # 4. Update State
            state["design_plan"] = design_plan
            state["agent_results"].append(
                self.create_result(
                    status=TaskStatus.COMPLETED,
                    output=design_plan.get("summary", "Design plan completed"),
                    artifacts={"design_plan": design_plan},
                )
            )

            self.log_complete("design", TaskStatus.COMPLETED)
            return state

        except Exception as e:
            self.log_error("design", e)
            state["error"] = str(e)
            state["agent_results"].append(
                self.create_result(
                    status=TaskStatus.FAILED,
                    output=f"Design failed: {str(e)}",
                    metadata={"error_type": type(e).__name__},
                )
            )
            return state

    async def _generate_design_plan(self, state: OrchestrationState, task_description: str) -> dict:
        """Generate detailed design plan using LLM."""
        
        # In a real scenario, we might use Perplexity to research trends
        # research = await perplexity_research("Modern glassmorphism dashboard trends 2026")
        
        user_message = f"""Generate a detailed design implementation plan.

## Task
{task_description}

## Context
- Project: {state.get("repo")}
- Goal: Premium assets, translucent theme, widget-based layout.

Generate a complete design specification including:
1. Color Palette (Tailwind classes)
2. Typography
3. Animation Strategy (Framer Motion variants)
4. Component Breakdown
"""

        plan_text = await self.invoke_llm(user_message)

        return {
            "summary": plan_text[:200],
            "full_plan": plan_text,
        }

async def designer_node(state: OrchestrationState) -> OrchestrationState:
    """LangGraph node for designer agent."""
    agent = DesignerAgent()
    return await agent.design(state)
