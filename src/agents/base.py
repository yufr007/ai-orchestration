"""Base agent class with common functionality."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from src.config import get_settings
from src.core.state import OrchestrationState, AgentResult, AgentRole, TaskStatus
import structlog

logger = structlog.get_logger()


class BaseAgent(ABC):
    """Base class for all orchestration agents."""

    def __init__(self, role: AgentRole, temperature: float | None = None):
        self.role = role
        self.settings = get_settings()
        self.temperature = temperature or self.settings.default_temperature
        self.llm = self._create_llm()
        self.logger = logger.bind(agent=role.value)

    def _create_llm(self) -> BaseChatModel:
        """Create LLM instance based on configuration."""
        if self.settings.primary_llm_provider == "anthropic":
            return ChatAnthropic(
                model=self.settings.default_agent_model,
                temperature=self.temperature,
                api_key=self.settings.anthropic_api_key,
                max_tokens=4096,
            )
        else:
            return ChatOpenAI(
                model="gpt-4-turbo-preview",
                temperature=self.temperature,
                api_key=self.settings.openai_api_key,
            )

    @abstractmethod
    async def execute(self, state: OrchestrationState) -> dict[str, Any]:
        """Execute agent logic and return state updates."""
        pass

    async def invoke(self, state: OrchestrationState) -> dict[str, Any]:
        """Public method to invoke agent with error handling and result tracking."""
        self.logger.info(f"Starting {self.role.value} agent")
        started_at = datetime.utcnow()

        try:
            # Execute agent-specific logic
            updates = await self.execute(state)

            # Create success result
            result = AgentResult(
                agent=self.role,
                status=TaskStatus.COMPLETED,
                output=updates.get("output", ""),
                artifacts=updates.get("artifacts", {}),
                metadata={"started_at": started_at, "completed_at": datetime.utcnow()},
                timestamp=datetime.utcnow(),
            )

            # Add result to state
            agent_results = state.get("agent_results", []) + [result]
            updates["agent_results"] = agent_results
            updates["current_agent"] = self.role

            self.logger.info(f"Completed {self.role.value} agent", **updates.get("metadata", {}))
            return updates

        except Exception as e:
            # Create failure result
            self.logger.error(f"Failed {self.role.value} agent", error=str(e), exc_info=True)
            result = AgentResult(
                agent=self.role,
                status=TaskStatus.FAILED,
                output="",
                artifacts={},
                metadata={"error": str(e), "started_at": started_at},
                timestamp=datetime.utcnow(),
            )

            return {
                "agent_results": state.get("agent_results", []) + [result],
                "current_agent": self.role,
                "error": str(e),
            }

    def format_messages(self, system_prompt: str, user_message: str) -> list:
        """Format system and user messages for LLM."""
        return [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
