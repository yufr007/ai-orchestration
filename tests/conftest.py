"""Pytest configuration and fixtures."""

import os
import pytest
from datetime import datetime

from src.config import Settings
from src.core.state import OrchestrationState


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings."""
    return Settings(
        environment="development",
        perplexity_api_key="test-key",
        github_token="test-token",
        github_owner="test-owner",
        anthropic_api_key="test-anthropic-key",
        database_url="sqlite:///:memory:",
    )


@pytest.fixture
def initial_state() -> OrchestrationState:
    """Create initial orchestration state."""
    return OrchestrationState(
        repo="test-owner/test-repo",
        issue_number=123,
        pr_number=None,
        spec_content=None,
        mode="autonomous",
        messages=[],
        plan=None,
        tasks=[],
        files_changed=[],
        branches_created=[],
        prs_created=[],
        test_results=None,
        test_failures=[],
        review_comments=[],
        approval_status=None,
        agent_results=[],
        current_agent=None,
        next_agents=[],
        retry_count=0,
        max_retries=3,
        started_at=datetime.now(),
        completed_at=None,
        error=None,
    )


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Mock environment variables for tests."""
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_OWNER", "test-owner")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
