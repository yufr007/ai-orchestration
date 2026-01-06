"""Base agent class with common functionality."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

from src.config import get_settings
from src.core.state import OrchestrationState, AgentRole, AgentResult, TaskStatus
import structlog

logger = structlog.get_logger()


class BaseAgent(ABC):
    """Base class for all orchestration agents."""

    def __init__(self, role: AgentRole, model: str | None = None, temperature: float | None = None):
        self.role = role
        self.settings = get_settings()
        self.model_name = model or self.settings.default_agent_model
        self.temperature = temperature if temperature is not None else self.settings.default_temperature
        self.llm = self._create_llm()
        self.logger = logger.bind(agent=role.value)

    def _create_llm(self) -> BaseChatModel:
        """Create LLM instance based on settings."""
        if self.settings.primary_llm_provider == "anthropic":
            return ChatAnthropic(
                api_key=self.settings.anthropic_api_key,
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=4096,
            )
        else:
            return ChatOpenAI(
                api_key=self.settings.openai_api_key,
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=4096,
            )

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        pass

    @abstractmethod
    async def execute(self, state: OrchestrationState) -> dict[str, Any]:
        """Execute the agent's task."""
        pass

    async def invoke(self, state: OrchestrationState) -> dict[str, Any]:
        """Main entry point for agent execution."""
        self.logger.info(f"Starting {self.role.value} agent", repo=state.get("repo"))
        started_at = datetime.utcnow()

        try:
            result = await self.execute(state)
            status = TaskStatus.COMPLETED
            error = None
            self.logger.info(f"Completed {self.role.value} agent")

        except Exception as e:
            self.logger.error(f"Error in {self.role.value} agent", error=str(e))
            result = {"error": str(e)}
            status = TaskStatus.FAILED
            error = str(e)

        # Create agent result
        agent_result = AgentResult(
            agent=self.role,
            status=status,
            output=result.get("output", ""),
            artifacts=result.get("artifacts", {}),
            metadata=result.get("metadata", {}),
            timestamp=datetime.utcnow(),
        )

        # Update state
        updates = {
            "current_agent": self.role,
            "agent_results": state.get("agent_results", []) + [agent_result],
        }

        if error:
            updates["error"] = error

        updates.update(result)
        return updates

    async def _call_llm(
        self, system_prompt: str, user_message: str, context: dict[str, Any] | None = None
    ) -> str:
        """Call LLM with system and user messages."""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        if context:
            context_msg = f"\n\nAdditional Context:\n{self._format_context(context)}"
            messages[-1].content += context_msg

        response = await self.llm.ainvoke(messages)
        return response.content

    def _format_context(self, context: dict[str, Any]) -> str:
        """Format context dictionary for LLM."""
        lines = []
        for key, value in context.items():
            if isinstance(value, (list, dict)):
                import json

                value = json.dumps(value, indent=2)
            lines.append(f"{key}: {value}")
        return "\n".join(lines)
