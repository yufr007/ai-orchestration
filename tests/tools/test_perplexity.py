"""Tests for Perplexity integration."""

import pytest
from unittest.mock import AsyncMock, patch

from src.tools.perplexity import search_perplexity, research_topic


@pytest.mark.asyncio
async def test_search_perplexity() -> None:
    """Test Perplexity search."""
    with patch("src.tools.perplexity.get_perplexity_client") as mock_client:
        # Setup mock
        client = mock_client.return_value
        client.search = AsyncMock(return_value="Search results for Python best practices")
        
        # Execute
        result = await search_perplexity("Python best practices")
        
        # Verify
        assert "Search results" in result
        client.search.assert_called_once()


@pytest.mark.asyncio
async def test_research_topic() -> None:
    """Test deep research."""
    with patch("src.tools.perplexity.get_perplexity_client") as mock_client:
        # Setup mock
        client = mock_client.return_value
        client.research = AsyncMock(return_value={
            "topic": "machine learning",
            "depth": "standard",
            "queries": ["machine learning", "machine learning best practices"],
            "results": {},
            "summary": "Machine learning overview...",
        })
        
        # Execute
        result = await research_topic("machine learning")
        
        # Verify
        assert result["topic"] == "machine learning"
        assert result["depth"] == "standard"
        assert "summary" in result
