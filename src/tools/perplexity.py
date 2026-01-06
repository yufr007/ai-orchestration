"""Perplexity MCP integration for research capabilities."""

import asyncio
import json
import subprocess
from typing import Any

from src.config import get_settings


class PerplexityMCP:
    """Wrapper for Perplexity MCP server."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.server_process: subprocess.Popen | None = None

    async def start_server(self) -> None:
        """Start Perplexity MCP server if not already running."""
        if self.server_process is not None:
            return

        # Start MCP server as subprocess
        env = {
            "PERPLEXITY_API_KEY": self.settings.perplexity_api_key,
            "PERPLEXITY_MODEL": self.settings.perplexity_model,
        }

        # In production, use proper process management
        # For now, assume server is managed externally
        pass

    async def search(self, query: str, max_results: int = 5) -> dict[str, Any]:
        """Execute search via Perplexity MCP."""
        # This would use the MCP protocol to call the Perplexity server
        # For now, simulate with direct API call

        import httpx

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.perplexity_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.settings.perplexity_model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "Be precise and concise. Provide key facts and sources.",
                            },
                            {"role": "user", "content": query},
                        ],
                        "max_tokens": 1000,
                        "temperature": 0.2,
                        "return_citations": True,
                    },
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()

                # Extract content and citations
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                citations = data.get("citations", [])

                return {
                    "content": content,
                    "citations": citations,
                    "model": data.get("model"),
                }

            except Exception as e:
                return {"error": str(e), "content": "", "citations": []}

    async def stop_server(self) -> None:
        """Stop MCP server."""
        if self.server_process:
            self.server_process.terminate()
            self.server_process = None


# Singleton instance
_perplexity_mcp: PerplexityMCP | None = None


def get_perplexity_mcp() -> PerplexityMCP:
    """Get or create PerplexityMCP instance."""
    global _perplexity_mcp
    if _perplexity_mcp is None:
        _perplexity_mcp = PerplexityMCP()
    return _perplexity_mcp


async def research_with_perplexity(query: str) -> dict[str, Any]:
    """Research a topic using Perplexity.

    Args:
        query: Search query

    Returns:
        Dictionary with research results including content, citations, and key points
    """
    mcp = get_perplexity_mcp()
    result = await mcp.search(query)

    # Parse and structure the response
    content = result.get("content", "")
    citations = result.get("citations", [])

    # Extract key points (simple sentence splitting)
    sentences = [s.strip() for s in content.split(".") if s.strip()]
    key_points = sentences[:5]  # Top 5 sentences

    return {
        "query": query,
        "summary": content[:500],  # First 500 chars
        "key_points": key_points,
        "citations": citations,
        "full_content": content,
    }
