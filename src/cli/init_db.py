"""Database initialization script."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from sqlalchemy import create_engine, text

from src.config import get_settings

app = typer.Typer(name="init-db", help="Initialize database")
console = Console()


@app.command()
def init() -> None:
    """Initialize the database with required tables."""
    asyncio.run(_init_async())


async def _init_async() -> None:
    """Async database initialization."""
    settings = get_settings()

    console.print("[cyan]Initializing database...[/cyan]")
    console.print(f"Database URL: [dim]{settings.database_url}[/dim]\n")

    # Create engine
    engine = create_engine(settings.database_url)

    # Create tables
    with engine.connect() as conn:
        # LangGraph checkpointer tables
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

        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS checkpoint_writes (
                thread_id TEXT NOT NULL,
                checkpoint_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                idx INTEGER NOT NULL,
                channel TEXT NOT NULL,
                value BLOB,
                PRIMARY KEY (thread_id, checkpoint_id, task_id, idx)
            )
            """
            )
        )

        conn.commit()

    console.print("[green]✓ Database initialized successfully![/green]")
    console.print("\nTables created:")
    console.print("  • checkpoints")
    console.print("  • checkpoint_writes")


if __name__ == "__main__":
    app()
