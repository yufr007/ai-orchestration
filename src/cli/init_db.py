"""Initialize database for orchestration platform."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from sqlalchemy import create_engine, text

from src.config import get_settings


app = typer.Typer(name="init-db", help="Initialize orchestration database")
console = Console()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS orchestration_runs (
    id TEXT PRIMARY KEY,
    repo TEXT NOT NULL,
    issue_number INTEGER,
    pr_number INTEGER,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_executions (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    agent_role TEXT NOT NULL,
    status TEXT NOT NULL,
    output TEXT,
    artifacts TEXT,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES orchestration_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_runs_repo ON orchestration_runs(repo);
CREATE INDEX IF NOT EXISTS idx_runs_status ON orchestration_runs(status);
CREATE INDEX IF NOT EXISTS idx_executions_run ON agent_executions(run_id);
"""


@app.command()
def init() -> None:
    """Initialize the database schema."""
    console.print("\n[bold cyan]📦 Initializing Database[/bold cyan]\n")

    settings = get_settings()
    console.print(f"[bold]Database URL:[/bold] {settings.database_url}")

    try:
        # Create engine
        engine = create_engine(settings.database_url)

        # Execute schema
        with engine.connect() as conn:
            for statement in SCHEMA_SQL.split(";"):
                if statement.strip():
                    conn.execute(text(statement))
            conn.commit()

        console.print("\n[green]✅ Database initialized successfully![/green]\n")
        console.print("Tables created:")
        console.print("  - orchestration_runs")
        console.print("  - agent_executions")

    except Exception as e:
        console.print(f"\n[red]❌ Database initialization failed:[/red] {e}\n")
        raise typer.Exit(1)


@app.command()
def reset() -> None:
    """Reset the database (drop all tables)."""
    confirmed = typer.confirm(
        "This will delete all data. Are you sure?",
        abort=True,
    )

    if not confirmed:
        raise typer.Exit(0)

    console.print("\n[bold yellow]⚠️  Resetting Database[/bold yellow]\n")

    settings = get_settings()

    try:
        engine = create_engine(settings.database_url)

        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS agent_executions"))
            conn.execute(text("DROP TABLE IF EXISTS orchestration_runs"))
            conn.commit()

        console.print("[green]✅ Database reset complete[/green]\n")

        # Reinitialize
        init()

    except Exception as e:
        console.print(f"\n[red]❌ Database reset failed:[/red] {e}\n")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
