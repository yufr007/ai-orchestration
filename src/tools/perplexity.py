"""Perplexity MCP integration."""

import asyncio
import json
from typing import Any

import httpx
import structlog

from src.config import get_settings

logger = structlog.get_logger()


class PerplexityTool:
    """Tool for accessing Perplexity AI via MCP server."""

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.perplexity_api_key
        self.model = self.settings.perplexity_model
        self.timeout = self.settings.perplexity_timeout_ms / 1000
        self.base_url = "https://api.perplexity.ai"

    async def search(self, query: str, search_recency_filter: str = "month") -> dict[str, Any]:
        """Perform search using Perplexity API.

        Args:
            query: Search query
            search_recency_filter: Time filter (hour, day, week, month, year)

        Returns:
            Search results with content and citations
        """
        logger.info("Perplexity search", query=query[:100])

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": query}],
            "search_recency_filter": search_recency_filter,
            "return_citations": True,
            "return_images": False,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions", headers=headers, json=payload
                )
                response.raise_for_status()
                data = response.json()

                # Extract content and citations
                content = data["choices"][0]["message"]["content"]
                citations = data.get("citations", [])

                logger.info("Perplexity search successful", citations_count=len(citations))

                return {"content": content, "citations": citations, "query": query}

            except httpx.HTTPStatusError as e:
                logger.error("Perplexity API error", status=e.response.status_code, error=str(e))
                raise
            except Exception as e:
                logger.error("Perplexity search failed", error=str(e))
                raise

    async def research(self, queries: list[str]) -> list[dict[str, Any]]:
        """Perform multiple searches in parallel.

        Args:
            queries: List of search queries

        Returns:
            List of search results
        """
        tasks = [self.search(query) for query in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_results = [r for r in results if isinstance(r, dict)]
        return valid_results
