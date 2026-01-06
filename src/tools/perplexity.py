"""Perplexity MCP client for research and web search."""

import asyncio
import json
from typing import Any

import httpx

from src.config import get_settings


class PerplexityClient:
    """Client for Perplexity API via MCP server."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = "https://api.perplexity.ai"
        self.headers = {
            "Authorization": f"Bearer {self.settings.perplexity_api_key}",
            "Content-Type": "application/json",
        }

    async def search(self, query: str, model: str | None = None) -> dict[str, Any]:
        """Execute a Perplexity search.

        Args:
            query: Search query
            model: Model to use (defaults to settings.perplexity_model)

        Returns:
            Search results with citations
        """
        model = model or self.settings.perplexity_model

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful research assistant. Provide accurate, well-cited information.",
                },
                {"role": "user", "content": query},
            ],
        }

        async with httpx.AsyncClient(timeout=self.settings.perplexity_timeout_ms / 1000) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def research(self, query: str) -> str:
        """Perform research and return formatted results.

        Args:
            query: Research question

        Returns:
            Formatted research findings with citations
        """
        try:
            result = await self.search(query)
            content = result["choices"][0]["message"]["content"]
            citations = result.get("citations", [])

            # Format output
            output = f"{content}\n\n"
            if citations:
                output += "**Sources:**\n"
                for i, citation in enumerate(citations, 1):
                    output += f"{i}. {citation}\n"

            return output

        except Exception as e:
            return f"Research failed: {str(e)}"


# Global client instance
_client: PerplexityClient | None = None


def get_perplexity_client() -> PerplexityClient:
    """Get or create Perplexity client singleton."""
    global _client
    if _client is None:
        _client = PerplexityClient()
    return _client


async def perplexity_research(query: str) -> str:
    """Convenience function for research.

    Args:
        query: Research question

    Returns:
        Formatted research results
    """
    client = get_perplexity_client()
    return await client.research(query)
