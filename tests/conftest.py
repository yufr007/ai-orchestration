"""Pytest configuration and fixtures."""

import pytest
from unittest.mock import Mock, AsyncMock

from src.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Mock settings for testing."""
    return Settings(
        perplexity_api_key="test-key",
        perplexity_model="sonar",
        anthropic_api_key="test-anthropic-key",
        github_token="test-github-token",
        github_owner="test-owner",
        database_url="sqlite:///:memory:",
        environment="development",
    )


@pytest.fixture
def mock_github_client():
    """Mock GitHub client."""
    client = Mock()
    repo = Mock()
    client.get_repo.return_value = repo
    return client


@pytest.fixture
def mock_perplexity_mcp():
    """Mock Perplexity MCP."""
    mcp = AsyncMock()
    mcp.search.return_value = {
        "content": "Test research content",
        "citations": [],
    }
    return mcp


@pytest.fixture
def sample_orchestration_state():
    """Sample orchestration state for testing."""
    from datetime import datetime
    from src.core.state import OrchestrationState

    return OrchestrationState(
        repo="test/repo",
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
