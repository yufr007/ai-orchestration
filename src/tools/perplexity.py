"""Perplexity MCP integration for research and knowledge retrieval."""

import asyncio
import json
from typing import Any

from src.config import get_settings


class PerplexityMCPClient:
    """Client for Perplexity MCP server."""
    
    def __init__(self) -> None:
        self.settings = get_settings()
        self.process: asyncio.subprocess.Process | None = None
    
    async def start(self) -> None:
        """Start the Perplexity MCP server."""
        if self.process:
            return
        
        # Start MCP server
        self.process = await asyncio.create_subprocess_exec(
            "npx",
            "@perplexity-ai/mcp-server",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                "PERPLEXITY_API_KEY": self.settings.perplexity_api_key,
                "PERPLEXITY_MODEL": self.settings.perplexity_model,
            },
        )
    
    async def stop(self) -> None:
        """Stop the Perplexity MCP server."""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            self.process = None
    
    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call a tool via MCP protocol."""
        if not self.process or not self.process.stdin or not self.process.stdout:
            await self.start()
        
        # Construct MCP request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        
        # Send request
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()
        
        # Read response
        response_line = await self.process.stdout.readline()
        response = json.loads(response_line.decode())
        
        if "error" in response:
            raise Exception(f"MCP Error: {response['error']}")
        
        return response.get("result")
    
    async def search_web(self, query: str) -> str:
        """Search the web using Perplexity."""
        result = await self.call_tool(
            "search_web",
            {"queries": [query]},
        )
        
        # Extract content from results
        if isinstance(result, list) and len(result) > 0:
            return result[0].get("content", "")
        return str(result)


# Global client instance
_client: PerplexityMCPClient | None = None


async def get_perplexity_client() -> PerplexityMCPClient:
    """Get or create the global Perplexity MCP client."""
    global _client
    if _client is None:
        _client = PerplexityMCPClient()
        await _client.start()
    return _client


async def perplexity_research(query: str, max_results: int = 3) -> str:
    """Research a topic using Perplexity's web search.
    
    Args:
        query: Search query
        max_results: Maximum number of results to return
    
    Returns:
        Combined research findings as text
    """
    client = await get_perplexity_client()
    
    try:
        result = await client.search_web(query)
        return result
    except Exception as e:
        print(f"Perplexity research failed: {e}")
        return f"Research failed for query: {query}"


async def shutdown_perplexity() -> None:
    """Shutdown the Perplexity MCP client."""
    global _client
    if _client:
        await _client.stop()
        _client = None
