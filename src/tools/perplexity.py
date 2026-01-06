"""Perplexity MCP integration for research and knowledge gathering."""

import asyncio
import json
import os
from typing import Any

import httpx
from src.config import get_settings


class PerplexityMCP:
    """Client for Perplexity MCP server."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key = self.settings.perplexity_api_key
        self.model = self.settings.perplexity_model
        self.timeout = self.settings.perplexity_timeout_ms / 1000.0
        self.base_url = "https://api.perplexity.ai"

    async def search(self, query: str, **kwargs: Any) -> str:
        """Execute a search query via Perplexity API.
        
        Args:
            query: Search query string
            **kwargs: Additional parameters (model, temperature, etc.)
        
        Returns:
            Search results as formatted string
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
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
                            "role": "system",
                            "content": "You are a helpful research assistant. Provide accurate, well-sourced information.",
                        },
                        {"role": "user", "content": query},
                    ],
                    "temperature": kwargs.get("temperature", 0.2),
                    "max_tokens": kwargs.get("max_tokens", 1000),
                },
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract content and citations
            content = data["choices"][0]["message"]["content"]
            
            # Check for citations in response
            citations = data.get("citations", [])
            if citations:
                content += "\n\nSources:\n"
                for i, citation in enumerate(citations, 1):
                    content += f"{i}. {citation}\n"
            
            return content

    async def research(self, topic: str, depth: str = "standard") -> dict[str, Any]:
        """Perform deep research on a topic.
        
        Args:
            topic: Research topic
            depth: Research depth ("quick", "standard", "deep")
        
        Returns:
            Structured research results
        """
        queries = []
        
        if depth == "quick":
            queries = [topic]
        elif depth == "standard":
            queries = [
                topic,
                f"{topic} best practices",
                f"{topic} common pitfalls",
            ]
        else:  # deep
            queries = [
                topic,
                f"{topic} best practices",
                f"{topic} common pitfalls",
                f"{topic} implementation guide",
                f"{topic} performance considerations",
            ]
        
        results = await asyncio.gather(*[self.search(q) for q in queries])
        
        return {
            "topic": topic,
            "depth": depth,
            "queries": queries,
            "results": dict(zip(queries, results)),
            "summary": results[0],  # First result as summary
        }


# Singleton instance
_perplexity_client: PerplexityMCP | None = None


def get_perplexity_client() -> PerplexityMCP:
    """Get or create Perplexity MCP client singleton."""
    global _perplexity_client
    if _perplexity_client is None:
        _perplexity_client = PerplexityMCP()
    return _perplexity_client


async def search_perplexity(query: str, **kwargs: Any) -> str:
    """Convenience function to search via Perplexity.
    
    Args:
        query: Search query
        **kwargs: Additional parameters
    
    Returns:
        Search results
    """
    client = get_perplexity_client()
    return await client.search(query, **kwargs)


async def research_topic(topic: str, depth: str = "standard") -> dict[str, Any]:
    """Convenience function to research a topic.
    
    Args:
        topic: Research topic
        depth: Research depth
    
    Returns:
        Structured research results
    """
    client = get_perplexity_client()
    return await client.research(topic, depth)
