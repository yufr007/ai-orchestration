"""Application settings and configuration."""

import os
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    debug: bool = Field(default=False, description="Enable debug mode")

    # API Keys
    perplexity_api_key: str = Field(..., description="Perplexity API key")
    perplexity_model: str = Field(default="sonar", description="Perplexity model name")
    perplexity_timeout_ms: int = Field(default=600000, description="Perplexity timeout in ms")

    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")

    # GitHub
    github_token: str = Field(..., description="GitHub Personal Access Token")
    github_owner: str = Field(..., description="GitHub username or org")

    # Database
    database_url: str = Field(
        default="sqlite:///./orchestration.db", description="Database connection URL"
    )

    # Azure (Optional)
    azure_subscription_id: str | None = None
    azure_tenant_id: str | None = None
    azure_client_id: str | None = None
    azure_client_secret: str | None = None

    # Observability
    langsmith_api_key: str | None = None
    langsmith_project: str = "ai-orchestration"
    langchain_tracing_v2: bool = False

    # Rate Limiting
    max_concurrent_agents: int = 5
    max_perplexity_calls_per_hour: int = 100

    # Agent Configuration
    default_agent_model: str = "claude-3-5-sonnet-20241022"
    default_temperature: float = 0.2
    max_agent_iterations: int = 10

    @property
    def primary_llm_provider(self) -> Literal["anthropic", "openai"]:
        """Determine primary LLM provider based on available keys."""
        if self.anthropic_api_key:
            return "anthropic"
        elif self.openai_api_key:
            return "openai"
        raise ValueError("No LLM API key configured (Anthropic or OpenAI required)")

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
