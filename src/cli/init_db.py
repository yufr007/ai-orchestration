"""Initialize database for orchestration platform."""

import asyncio
from pathlib import Path

from sqlalchemy import create_engine, text
from rich.console import Console

from src.config import get_settings


console = Console()


def init_database() -> None:
    """Initialize database with required tables."""
    settings = get_settings()
    
    console.print("\n[bold blue]📦 Initializing database...[/bold blue]\n")
    console.print(f"Database URL: [cyan]{settings.database_url}[/cyan]\n")
    
    # Create database engine
    engine = create_engine(settings.database_url)
    
    # Create tables for LangGraph checkpointing
    schema = """
    CREATE TABLE IF NOT EXISTS checkpoints (
        thread_id TEXT NOT NULL,
        checkpoint_id TEXT NOT NULL,
        parent_id TEXT,
        checkpoint BLOB NOT NULL,
        metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (thread_id, checkpoint_id)
    );
    
    CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id ON checkpoints(thread_id);
    CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at ON checkpoints(created_at);
    
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        repo TEXT NOT NULL,
        issue_number INTEGER,
        pr_number INTEGER,
        mode TEXT NOT NULL,
        status TEXT NOT NULL,
        result TEXT,
        error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        started_at TIMESTAMP,
        completed_at TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_jobs_repo ON jobs(repo);
    CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
    CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
    """
    
    try:
        with engine.connect() as conn:
            for statement in schema.split(";"):
                if statement.strip():
                    conn.execute(text(statement))
            conn.commit()
        
        console.print("[green]✅ Database initialized successfully![/green]\n")
    
    except Exception as e:
        console.print(f"[red]❌ Database initialization failed:[/red] {e}\n")
        raise
    
    finally:
        engine.dispose()


if __name__ == "__main__":
    init_database()
