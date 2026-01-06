"""Database initialization script."""

import asyncio
from pathlib import Path

from sqlalchemy import create_engine, text
from rich.console import Console

from src.config import get_settings

console = Console()


def init_database() -> None:
    """Initialize database schema."""
    settings = get_settings()

    console.print("[bold blue]Initializing Database[/bold blue]\n")
    console.print(f"Database URL: {settings.database_url}")

    try:
        engine = create_engine(settings.database_url)

        # Create tables
        with engine.connect() as conn:
            # Jobs table
            conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    repo TEXT NOT NULL,
                    issue_number INTEGER,
                    pr_number INTEGER,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    result_json TEXT,
                    error TEXT
                )
            """
                )
            )

            # Checkpoints table (for LangGraph)
            conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    thread_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    parent_id TEXT,
                    checkpoint BLOB NOT NULL,
                    metadata TEXT,
                    PRIMARY KEY (thread_id, checkpoint_id)
                )
            """
                )
            )

            conn.commit()

        console.print("[green]✓[/green] Database initialized successfully")
        console.print("[green]✓[/green] Created tables: jobs, checkpoints")

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise


if __name__ == "__main__":
    init_database()
