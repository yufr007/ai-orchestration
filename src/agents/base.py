"""Base agent class with common functionality."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings
from src.core.state import AgentRole, AgentResult, OrchestrationState, TaskStatus
from src.utils.logging import get_logger


class BaseAgent(ABC):
    """Base class for all agents in the orchestration."""

    def __init__(self, role: AgentRole, system_prompt: str):
        self.role = role
        self.system_prompt = system_prompt
        self.settings = get_settings()
        self.logger = get_logger(f"agent.{role.value}")
        self.llm = self._create_llm()

    def _create_llm(self) -> BaseChatModel:
        """Create the appropriate LLM based on configuration."""
        if self.settings.primary_llm_provider == "anthropic":
            return ChatAnthropic(
                model=self.settings.default_agent_model,
                temperature=self.settings.default_temperature,
                anthropic_api_key=self.settings.anthropic_api_key,
            )
        else:
            return ChatOpenAI(
                model=self.settings.default_agent_model.replace("claude", "gpt-4"),
                temperature=self.settings.default_temperature,
                openai_api_key=self.settings.openai_api_key,
            )

    async def invoke(self, state: OrchestrationState) -> AgentResult:
        """Execute the agent and return a result."""
        self.logger.info(f"Starting {self.role.value} agent")
        start_time = datetime.now()

        try:
            output, artifacts = await self.execute(state)
            status = TaskStatus.COMPLETED
            error = None
        except Exception as e:
            self.logger.error(f"{self.role.value} failed: {e}", exc_info=True)
            output = f"Error: {str(e)}"
            artifacts = {}
            status = TaskStatus.FAILED
            error = str(e)

        result: AgentResult = {
            "agent": self.role,
            "status": status,
            "output": output,
            "artifacts": artifacts,
            "metadata": {
                "duration_seconds": (datetime.now() - start_time).total_seconds(),
                "error": error,
            },
            "timestamp": datetime.now(),
        }

        self.logger.info(f"{self.role.value} completed with status: {status.value}")
        return result

    @abstractmethod
    async def execute(self, state: OrchestrationState) -> tuple[str, dict[str, Any]]:
        """Execute agent logic. Returns (output_message, artifacts_dict)."""
        pass

    def _format_messages(self, user_message: str) -> list:
        """Format system and user messages for LLM."""
        return [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_message),
        ]
