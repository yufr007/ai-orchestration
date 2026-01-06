"""Tests for GitHub integration."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.tools.github import (
    get_issue_details,
    get_file_contents,
    create_branch,
    create_pull_request,
)


@pytest.mark.asyncio
async def test_get_issue_details() -> None:
    """Test getting issue details."""
    with patch("src.tools.github.get_github_client") as mock_client:
        # Setup mock
        client = MagicMock()
        mock_client.return_value = client
        client.get_issue = AsyncMock(return_value={
            "number": 123,
            "title": "Test issue",
            "body": "Test body",
            "state": "open",
            "labels": ["bug"],
        })
        
        # Execute
        result = await get_issue_details("owner/repo", 123)
        
        # Verify
        assert result["number"] == 123
        assert result["title"] == "Test issue"
        assert "bug" in result["labels"]


@pytest.mark.asyncio
async def test_create_pull_request() -> None:
    """Test creating a pull request."""
    with patch("src.tools.github.get_github_client") as mock_client:
        # Setup mock
        client = MagicMock()
        mock_client.return_value = client
        client.create_pull_request = AsyncMock(return_value={
            "number": 456,
            "title": "Test PR",
            "body": "Test PR body",
            "state": "open",
            "html_url": "https://github.com/owner/repo/pull/456",
        })
        
        # Execute
        result = await create_pull_request(
            owner="owner",
            repo="repo",
            title="Test PR",
            body="Test PR body",
            head="feature-branch",
            base="main",
        )
        
        # Verify
        assert result["number"] == 456
        assert result["title"] == "Test PR"
        assert "html_url" in result
