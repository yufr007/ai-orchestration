"""Perplexity MCP integration for research capabilities."""

import asyncio
import json
import os
from typing import Any

import httpx
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession

from src.config import get_settings


class PerplexityMCP:
    """Perplexity MCP client wrapper."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@perplexity-ai/mcp-server"],
            env={
                "PERPLEXITY_API_KEY": self.settings.perplexity_api_key,
                "PERPLEXITY_MODEL": self.settings.perplexity_model,
                "PERPLEXITY_TIMEOUT_MS": str(self.settings.perplexity_timeout_ms),
            },
        )

    async def research(self, query: str) -> str:
        """Perform research using Perplexity MCP server.

        Args:
            query: Research query

        Returns:
            Research results as formatted text
        """
        try:
            async with stdio_client(self.server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize session
                    await session.initialize()

                    # List available tools (for debugging)
                    tools = await session.list_tools()

                    # Call research tool (web_search or similar)
                    # Adjust tool name based on actual Perplexity MCP API
                    result = await session.call_tool(
                        "web_search", {"query": query, "model": self.settings.perplexity_model}
                    )

                    # Extract and format results
                    return self._format_results(result)

        except Exception as e:
            # Fallback to direct API if MCP fails
            return await self._fallback_api_call(query)

    async def _fallback_api_call(self, query: str) -> str:
        """Fallback to direct Perplexity API if MCP unavailable."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.perplexity_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.settings.perplexity_model,
                        "messages": [{"role": "user", "content": query}],
                    },
                    timeout=self.settings.perplexity_timeout_ms / 1000,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Research unavailable: {str(e)}"

    def _format_results(self, result: Any) -> str:
        """Format MCP tool result for consumption."""
        if isinstance(result, dict):
            if "content" in result:
                return result["content"]
            return json.dumps(result, indent=2)
        return str(result)


# Global instance
_perplexity_client: PerplexityMCP | None = None


def get_perplexity_client() -> PerplexityMCP:
    """Get or create global Perplexity MCP client."""
    global _perplexity_client
    if _perplexity_client is None:
        _perplexity_client = PerplexityMCP()
    return _perplexity_client


async def perplexity_research(query: str) -> str:
    """Convenience function for research.

    Args:
        query: Research query

    Returns:
        Research results
    """
    client = get_perplexity_client()
    return await client.research(query)
