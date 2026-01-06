"""Perplexity MCP integration for research and web search."""

import asyncio
import json
from typing import Any

import httpx
import structlog

from src.config import get_settings

logger = structlog.get_logger()


class PerplexityMCP:
    """Perplexity MCP client for research capabilities."""

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.perplexity_api_key
        self.model = self.settings.perplexity_model
        self.timeout = self.settings.perplexity_timeout_ms / 1000.0
        self.base_url = "https://api.perplexity.ai"

    async def query(self, prompt: str, system_prompt: str | None = None) -> str:
        """Execute a Perplexity query via API."""
        logger.info("Perplexity query", prompt_length=len(prompt))

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 2048,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions", json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()
                result = data["choices"][0]["message"]["content"]
                logger.info("Perplexity query completed", response_length=len(result))
                return result
            except httpx.HTTPError as e:
                logger.error("Perplexity API error", error=str(e))
                return f"Error querying Perplexity: {str(e)}"


# Singleton instance
_perplexity_client = None


def get_perplexity_client() -> PerplexityMCP:
    """Get or create Perplexity client singleton."""
    global _perplexity_client
    if _perplexity_client is None:
        _perplexity_client = PerplexityMCP()
    return _perplexity_client


async def research_with_perplexity(query: str, context: str | None = None) -> str:
    """Research a topic using Perplexity's web search capabilities.

    Args:
        query: The research question or topic
        context: Optional context to guide the research

    Returns:
        Research findings and insights
    """
    client = get_perplexity_client()

    system_prompt = """You are a research assistant helping software engineers.
    Provide concise, actionable insights focused on best practices, patterns, and implementation approaches.
    Include relevant examples and cite sources where applicable."""

    if context:
        query = f"{query}\n\nContext: {context}"

    return await client.query(query, system_prompt)


async def research_multiple_queries(queries: list[str]) -> dict[str, str]:
    """Execute multiple research queries in parallel.

    Args:
        queries: List of research questions

    Returns:
        Dictionary mapping queries to results
    """
    tasks = [research_with_perplexity(q) for q in queries]
    results = await asyncio.gather(*tasks)
    return dict(zip(queries, results))
