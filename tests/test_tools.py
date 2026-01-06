"""Tests for tool integrations."""

import pytest
from unittest.mock import AsyncMock, patch, Mock

from src.tools.perplexity import research_with_perplexity
from src.tools.github import get_issue_details, create_branch


@pytest.mark.asyncio
async def test_perplexity_research():
    """Test Perplexity research tool."""
    with patch("src.tools.perplexity.get_perplexity_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.query = AsyncMock(return_value="Mocked research result")
        mock_get_client.return_value = mock_client

        result = await research_with_perplexity("Test query")

        assert result == "Mocked research result"
        mock_client.query.assert_called_once()


@pytest.mark.asyncio
async def test_github_get_issue_details(sample_issue):
    """Test GitHub issue retrieval."""
    with patch("src.tools.github.get_github_client") as mock_get_client:
        mock_client = Mock()
        mock_repo = Mock()
        mock_issue = Mock()

        # Configure mock issue
        mock_issue.number = sample_issue["number"]
        mock_issue.title = sample_issue["title"]
        mock_issue.body = sample_issue["body"]
        mock_issue.state = sample_issue["state"]
        mock_issue.labels = [Mock(name=label) for label in sample_issue["labels"]]
        mock_issue.assignees = []
        mock_issue.html_url = sample_issue["url"]

        from datetime import datetime

        mock_issue.created_at = datetime.fromisoformat(sample_issue["created_at"].replace("Z", "+00:00"))
        mock_issue.updated_at = datetime.fromisoformat(sample_issue["updated_at"].replace("Z", "+00:00"))

        mock_repo.get_issue.return_value = mock_issue
        mock_client.get_repo.return_value = mock_repo
        mock_get_client.return_value = mock_client

        result = await get_issue_details("test-owner/test-repo", 123)

        assert result["number"] == 123
        assert result["title"] == sample_issue["title"]
        assert "feature" in result["labels"]


@pytest.mark.asyncio
async def test_github_create_branch():
    """Test GitHub branch creation."""
    with patch("src.tools.github.get_github_client") as mock_get_client:
        mock_client = Mock()
        mock_repo = Mock()
        mock_ref = Mock()
        mock_ref.object.sha = "abc123"

        mock_repo.get_git_ref.return_value = mock_ref
        mock_repo.create_git_ref.return_value = Mock()
        mock_client.get_repo.return_value = mock_repo
        mock_get_client.return_value = mock_client

        result = await create_branch("test-owner/test-repo", "feature-branch", "main")

        assert result is True
        mock_repo.create_git_ref.assert_called_once()
