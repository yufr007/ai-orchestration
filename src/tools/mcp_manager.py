"""MCP server lifecycle management."""

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import structlog

from src.config import get_settings

logger = structlog.get_logger()


class MCPManager:
    """Manage MCP server processes and connections."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.servers: dict[str, subprocess.Popen] = {}
        self.config_path = Path.home() / ".config" / "mcp" / "servers.json"

    async def start_perplexity_server(self) -> None:
        """Start the Perplexity MCP server."""
        if "perplexity" in self.servers:
            logger.info("Perplexity MCP server already running")
            return

        try:
            # Start npx server
            process = subprocess.Popen(
                [
                    "npx",
                    "-y",
                    "@perplexity-ai/mcp-server",
                ],
                env={
                    **os.environ,
                    "PERPLEXITY_API_KEY": self.settings.perplexity_api_key,
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.servers["perplexity"] = process
            logger.info("Perplexity MCP server started", pid=process.pid)

            # Wait a bit for server to initialize
            await asyncio.sleep(2)

        except Exception as e:
            logger.error("Failed to start Perplexity MCP server", error=str(e))
            raise

    async def start_github_server(self) -> None:
        """Start the GitHub MCP server."""
        if "github" in self.servers:
            logger.info("GitHub MCP server already running")
            return

        try:
            # Start npx server
            process = subprocess.Popen(
                [
                    "npx",
                    "-y",
                    "@modelcontextprotocol/server-github",
                ],
                env={
                    **os.environ,
                    "GITHUB_PERSONAL_ACCESS_TOKEN": self.settings.github_token,
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.servers["github"] = process
            logger.info("GitHub MCP server started", pid=process.pid)

            await asyncio.sleep(2)

        except Exception as e:
            logger.error("Failed to start GitHub MCP server", error=str(e))
            raise

    async def start_all(self) -> None:
        """Start all configured MCP servers."""
        await self.start_perplexity_server()
        # GitHub operations use PyGithub directly for now
        # await self.start_github_server()

    async def stop_all(self) -> None:
        """Stop all running MCP servers."""
        for name, process in self.servers.items():
            try:
                process.terminate()
                await asyncio.sleep(1)
                if process.poll() is None:
                    process.kill()
                logger.info("MCP server stopped", server=name)
            except Exception as e:
                logger.error("Error stopping MCP server", server=name, error=str(e))

        self.servers.clear()

    def create_config(self) -> None:
        """Create MCP configuration file."""
        config = {
            "mcpServers": {
                "perplexity": {
                    "command": "npx",
                    "args": ["-y", "@perplexity-ai/mcp-server"],
                    "env": {"PERPLEXITY_API_KEY": self.settings.perplexity_api_key},
                },
                "github": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": self.settings.github_token},
                },
            }
        }

        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Write config
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)

        logger.info("MCP configuration created", path=str(self.config_path))
