"""Base agent class with common functionality."""

from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from src.config import get_settings
from src.core.state import AgentRole, TaskStatus, AgentResult
import structlog

logger = structlog.get_logger()


class BaseAgent:
    """Base class for all agents with common LLM and logging setup."""

    def __init__(
        self,
        role: AgentRole,
        system_prompt: str,
        temperature: float | None = None,
        model: str | None = None,
    ) -> None:
        self.role = role
        self.system_prompt = system_prompt
        self.settings = get_settings()
        self.logger = logger.bind(agent=role.value)

        # Initialize LLM
        temperature = temperature or self.settings.default_temperature
        model = model or self.settings.default_agent_model

        if self.settings.primary_llm_provider == "anthropic":
            self.llm: BaseChatModel = ChatAnthropic(
                api_key=self.settings.anthropic_api_key,
                model=model,
                temperature=temperature,
            )
        else:
            self.llm: BaseChatModel = ChatOpenAI(
                api_key=self.settings.openai_api_key,
                model=model,
                temperature=temperature,
            )

        self.logger.info(f"Initialized {role.value} agent", model=model, temperature=temperature)

    def create_result(
        self,
        status: TaskStatus,
        output: str,
        artifacts: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Create a standardized agent result."""
        return AgentResult(
            agent=self.role,
            status=status,
            output=output,
            artifacts=artifacts or {},
            metadata=metadata or {},
            timestamp=datetime.now(),
        )

    async def invoke_llm(self, user_message: str, context: dict[str, Any] | None = None) -> str:
        """Invoke the LLM with system prompt and user message."""
        messages = [SystemMessage(content=self.system_prompt)]

        # Add context if provided
        if context:
            context_str = "\n\n## Current Context:\n" + "\n".join(
                f"**{k}**: {v}" for k, v in context.items()
            )
            messages.append(HumanMessage(content=context_str))

        messages.append(HumanMessage(content=user_message))

        self.logger.debug("Invoking LLM", messages_count=len(messages))
        response = await self.llm.ainvoke(messages)
        return response.content

    def log_start(self, task: str) -> None:
        """Log agent task start."""
        self.logger.info(f"{self.role.value} starting", task=task)

    def log_complete(self, task: str, status: TaskStatus) -> None:
        """Log agent task completion."""
        self.logger.info(f"{self.role.value} completed", task=task, status=status.value)

    def log_error(self, task: str, error: Exception) -> None:
        """Log agent error."""
        self.logger.error(f"{self.role.value} failed", task=task, error=str(error), exc_info=True)
