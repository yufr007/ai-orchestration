"""Perplexity MCP integration for research and web search."""

import asyncio
import json
from typing import Any

import httpx

from src.config import get_settings


class PerplexityMCP:
    """Client for Perplexity MCP server."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.perplexity_api_key
        self.model = self.settings.perplexity_model
        self.timeout_ms = self.settings.perplexity_timeout_ms
        self.base_url = "https://api.perplexity.ai"

    async def search(self, query: str, **kwargs: Any) -> str:
        """Perform a search using Perplexity API.

        Args:
            query: Search query
            **kwargs: Additional parameters (model, max_tokens, etc.)

        Returns:
            Search results as formatted string
        """
        async with httpx.AsyncClient(timeout=self.timeout_ms / 1000) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": [
                        {
                            "role": "user",
                            "content": query,
                        }
                    ],
                    "max_tokens": kwargs.get("max_tokens"),
                    "temperature": kwargs.get("temperature", 0.2),
                    "search_domain_filter": kwargs.get("domain_filter", []),
                    "return_images": kwargs.get("return_images", False),
                    "return_related_questions": kwargs.get("return_related", False),
                    "search_recency_filter": kwargs.get("recency_filter"),
                },
            )

            response.raise_for_status()
            data = response.json()

            # Extract content and citations
            content = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])

            # Format results
            result = content
            if citations:
                result += "\n\n**Sources:**\n"
                for i, citation in enumerate(citations, 1):
                    result += f"{i}. {citation}\n"

            return result

    async def research(
        self,
        topic: str,
        focus: str | None = None,
        depth: str = "balanced",
    ) -> dict[str, Any]:
        """Conduct structured research on a topic.

        Args:
            topic: Main research topic
            focus: Specific aspect to focus on
            depth: Research depth (quick, balanced, deep)

        Returns:
            Structured research results with summary, findings, sources
        """
        # Build research query
        query = f"Research: {topic}"
        if focus:
            query += f" with focus on {focus}"

        # Adjust parameters based on depth
        params = {
            "quick": {"max_tokens": 512, "temperature": 0.3},
            "balanced": {"max_tokens": 1024, "temperature": 0.2},
            "deep": {"max_tokens": 2048, "temperature": 0.1},
        }[depth]

        results = await self.search(query, **params, return_related=True)

        return {
            "topic": topic,
            "focus": focus,
            "depth": depth,
            "findings": results,
            "timestamp": asyncio.get_event_loop().time(),
        }

    async def compare(
        self,
        options: list[str],
        criteria: list[str] | None = None,
    ) -> dict[str, Any]:
        """Compare multiple options based on criteria.

        Args:
            options: List of options to compare
            criteria: Comparison criteria

        Returns:
            Structured comparison results
        """
        query = f"Compare: {', '.join(options)}"
        if criteria:
            query += f" based on: {', '.join(criteria)}"

        results = await self.search(query, max_tokens=1536)

        return {
            "options": options,
            "criteria": criteria,
            "comparison": results,
        }
