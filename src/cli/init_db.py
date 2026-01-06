"""Database initialization script."""

import asyncio
from pathlib import Path

from sqlalchemy import create_engine, text
from rich.console import Console

from src.config import get_settings

console = Console()


def init_database() -> None:
    """Initialize the database with required schema."""
    settings = get_settings()
    
    console.print("[cyan]Initializing database...[/cyan]")
    console.print(f"Database URL: {settings.database_url}\n")
    
    # Create engine
    engine = create_engine(settings.database_url)
    
    # Create schema
    schema_sql = """
    -- Jobs table
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        repo TEXT NOT NULL,
        issue_number INTEGER,
        pr_number INTEGER,
        mode TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        completed_at TIMESTAMP,
        error TEXT
    );
    
    -- Agent results table
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
    
    -- Checkpoints table (for LangGraph)
    CREATE TABLE IF NOT EXISTS checkpoints (
        thread_id TEXT NOT NULL,
        checkpoint_id TEXT NOT NULL,
        parent_id TEXT,
        checkpoint BLOB NOT NULL,
        metadata JSON,
        PRIMARY KEY (thread_id, checkpoint_id)
    );
    
    -- Create indexes
    CREATE INDEX IF NOT EXISTS idx_jobs_repo ON jobs(repo);
    CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
    CREATE INDEX IF NOT EXISTS idx_agent_results_job_id ON agent_results(job_id);
    CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id ON checkpoints(thread_id);
    """
    
    try:
        with engine.connect() as conn:
            # Execute schema
            for statement in schema_sql.split(";"):
                if statement.strip():
                    conn.execute(text(statement))
            conn.commit()
        
        console.print("[green]✓[/green] Database initialized successfully\n")
        
        # Display tables
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                    if "sqlite" in settings.database_url
                    else "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
                )
            )
            tables = [row[0] for row in result]
        
        console.print("Tables created:")
        for table in tables:
            console.print(f"  • {table}")
        
    except Exception as e:
        console.print(f"[red]Error initializing database: {e}[/red]")
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    init_database()
