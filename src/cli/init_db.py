"""Database initialization script."""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from rich.console import Console

from src.config import get_settings

console = Console()
settings = get_settings()


DATABASE_SCHEMA = """
-- Orchestration jobs table
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    repo TEXT NOT NULL,
    issue_number INTEGER,
    pr_number INTEGER,
    spec_content TEXT,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    error TEXT,
    result JSON
);

-- Agent execution results
CREATE TABLE IF NOT EXISTS agent_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    agent TEXT NOT NULL,
    status TEXT NOT NULL,
    output TEXT,
    artifacts JSON,
    metadata JSON,
    timestamp TIMESTAMP NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

-- Workflow checkpoints (used by LangGraph)
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    checkpoint BLOB NOT NULL,
    metadata JSON,
    created_at TIMESTAMP NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_repo ON jobs(repo);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_agent_results_job ON agent_results(job_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_thread ON checkpoints(thread_id);
"""


def init_database() -> None:
    """Initialize the database schema."""
    console.print("\n[bold cyan]💾 Initializing Database...[/bold cyan]\n")

    try:
        # Create engine
        console.print(f"Database URL: [yellow]{settings.database_url}[/yellow]")
        engine = create_engine(settings.database_url)

        # Execute schema
        with engine.connect() as conn:
            for statement in DATABASE_SCHEMA.split(";"):
                statement = statement.strip()
                if statement:
                    console.print(f"  Executing: {statement[:50]}...")
                    conn.execute(text(statement))
            conn.commit()

        console.print("\n[bold green]✅ Database initialized successfully![/bold green]\n")

    except Exception as e:
        console.print(f"\n[bold red]❌ Error initializing database:[/bold red]")
        console.print(f"[red]{e}[/red]\n")
        sys.exit(1)


if __name__ == "__main__":
    init_database()
