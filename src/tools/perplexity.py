"""Perplexity MCP integration for research and web search."""

import asyncio
import json
from typing import Any

import httpx

from src.config import get_settings

settings = get_settings()


class PerplexityMCP:
    """Perplexity MCP client wrapper."""

    def __init__(self) -> None:
        self.api_key = settings.perplexity_api_key
        self.model = settings.perplexity_model
        self.timeout = settings.perplexity_timeout_ms / 1000
        self.base_url = "https://api.perplexity.ai"

    async def search(self, query: str, return_citations: bool = True) -> dict[str, Any]:
        """Execute a Perplexity search query.

        Args:
            query: Search query string
            return_citations: Include source citations

        Returns:
            Dictionary with answer and optional citations
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": query}],
                    "return_citations": return_citations,
                    "return_images": False,
                },
            )
            response.raise_for_status()
            data = response.json()

            return {
                "answer": data["choices"][0]["message"]["content"],
                "citations": data.get("citations", []),
                "usage": data.get("usage", {}),
            }

    async def research(self, topic: str, focus_areas: list[str] | None = None) -> str:
        """Perform deep research on a topic.

        Args:
            topic: Main research topic
            focus_areas: Specific areas to focus on

        Returns:
            Comprehensive research summary
        """
        queries = [topic]
        if focus_areas:
            queries.extend([f"{topic}: {area}" for area in focus_areas])

        # Execute searches in parallel
        results = await asyncio.gather(*[self.search(q) for q in queries], return_exceptions=True)

        # Combine results
        combined = []
        for query, result in zip(queries, results):
            if isinstance(result, Exception):
                combined.append(f"**{query}**: Error - {result}")
            else:
                answer = result.get("answer", "No answer")
                citations = result.get("citations", [])
                citations_text = (
                    "\n  Sources: " + ", ".join(citations[:3]) if citations else ""
                )
                combined.append(f"**{query}**:\n{answer}{citations_text}")

        return "\n\n".join(combined)


# Singleton instance
_perplexity_client: PerplexityMCP | None = None


def get_perplexity_client() -> PerplexityMCP:
    """Get or create Perplexity client singleton."""
    global _perplexity_client
    if _perplexity_client is None:
        _perplexity_client = PerplexityMCP()
    return _perplexity_client


async def perplexity_search(query: str) -> dict[str, Any]:
    """Execute a Perplexity search.

    Args:
        query: Search query

    Returns:
        Search results with answer and citations
    """
    client = get_perplexity_client()
    return await client.search(query)


async def perplexity_research(topic: str, focus_areas: list[str] | None = None) -> str:
    """Perform comprehensive research using Perplexity.

    Args:
        topic: Main research topic
        focus_areas: Optional list of specific areas to research

    Returns:
        Detailed research summary
    """
    client = get_perplexity_client()
    return await client.research(topic, focus_areas)
