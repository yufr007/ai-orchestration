"""Pytest configuration and fixtures."""

import os
from typing import Any, Generator

import pytest
from unittest.mock import MagicMock, patch

from src.config import Settings


@pytest.fixture
def test_settings() -> Settings:
    """Provide test settings with mock API keys."""
    return Settings(
        perplexity_api_key="test_perplexity_key",
        anthropic_api_key="test_anthropic_key",
        github_token="test_github_token",
        github_owner="test_owner",
        database_url="sqlite:///:memory:",
        environment="development",
    )


@pytest.fixture
def mock_github_client() -> Generator[MagicMock, None, None]:
    """Mock GitHub client."""
    with patch("src.tools.github.get_github_client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def mock_perplexity_client() -> Generator[MagicMock, None, None]:
    """Mock Perplexity client."""
    with patch("src.tools.perplexity.get_perplexity_client") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def mock_llm() -> Generator[MagicMock, None, None]:
    """Mock LLM for testing agents."""
    with patch("langchain_anthropic.ChatAnthropic") as mock:
        llm = MagicMock()
        mock.return_value = llm
        yield llm
