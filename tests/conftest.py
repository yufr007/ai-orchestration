"""Pytest configuration and fixtures."""

import os
import pytest
from unittest.mock import Mock, AsyncMock

from src.config import Settings


@pytest.fixture
def settings():
    """Mock settings for testing."""
    return Settings(
        perplexity_api_key="test-perplexity-key",
        github_token="test-github-token",
        github_owner="test-owner",
        anthropic_api_key="test-anthropic-key",
        database_url="sqlite:///:memory:",
        environment="development",
    )


@pytest.fixture
def mock_github_client():
    """Mock GitHub client."""
    client = Mock()
    client.get_repo = Mock(return_value=Mock())
    return client


@pytest.fixture
def mock_perplexity_client():
    """Mock Perplexity client."""
    client = AsyncMock()
    client.query = AsyncMock(return_value="Mocked research result")
    return client


@pytest.fixture
def sample_issue():
    """Sample GitHub issue for testing."""
    return {
        "number": 123,
        "title": "Implement feature X",
        "body": "We need to implement feature X with the following requirements...",
        "state": "open",
        "labels": ["feature", "ai-implement"],
        "assignees": [],
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-06T00:00:00Z",
        "url": "https://github.com/test-owner/test-repo/issues/123",
    }


@pytest.fixture
def sample_plan():
    """Sample implementation plan."""
    return {
        "summary": "Implement feature X",
        "approach": "Use modular design with clean separation of concerns",
        "tasks": [
            {
                "id": 1,
                "title": "Create data model",
                "type": "feature",
                "files": ["src/models/feature_x.py"],
                "dependencies": [],
                "acceptance_criteria": ["Model defined with proper validation"],
                "estimated_complexity": "low",
            },
            {
                "id": 2,
                "title": "Implement API endpoint",
                "type": "feature",
                "files": ["src/api/feature_x.py"],
                "dependencies": [1],
                "acceptance_criteria": ["Endpoint returns correct response"],
                "estimated_complexity": "medium",
            },
        ],
        "risks": ["Integration complexity"],
        "research_notes": "Best practices suggest using...",
    }
