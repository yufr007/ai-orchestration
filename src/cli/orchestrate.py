"""Main CLI for running orchestration workflows."""

import asyncio
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
import structlog

from src.config import get_settings
from src.core.graph import create_orchestration_graph
from src.core.state import OrchestrationState
from src.tools.mcp_manager import MCPManager

app = typer.Typer(
    name="orchestrate",
    help="AI Orchestration Platform CLI",
    add_completion=False,
)

console = Console()
logger = structlog.get_logger()


@app.command()
def run(
    repo: str = typer.Option(..., "--repo", "-r", help="Repository (owner/name)"),
    issue: int | None = typer.Option(None, "--issue", "-i", help="Issue number"),
    pr: int | None = typer.Option(None, "--pr", "-p", help="PR number"),
    spec: Path | None = typer.Option(None, "--spec", "-s", help="Spec file path"),
    mode: str = typer.Option("autonomous", "--mode", "-m", help="Mode: autonomous, plan, review"),
    trace: bool = typer.Option(False, "--trace", help="Enable LangSmith tracing"),
) -> None:
    """Run an orchestration workflow."""
    asyncio.run(_run_async(repo, issue, pr, spec, mode, trace))


async def _run_async(
    repo: str,
    issue: int | None,
    pr: int | None,
    spec: Path | None,
    mode: str,
    trace: bool,
) -> None:
    """Async implementation of run command."""
    settings = get_settings()

    console.print("\n[bold cyan]AI Orchestration Platform[/bold cyan]")
    console.print(f"Repository: [green]{repo}[/green]")
    console.print(f"Mode: [yellow]{mode}[/yellow]\n")

    # Enable tracing if requested
    if trace and settings.langsmith_api_key:
        import os

        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        console.print("[dim]LangSmith tracing enabled[/dim]\n")

    # Start MCP servers
    console.print("[dim]Starting MCP servers...[/dim]")
    mcp_manager = MCPManager()
    try:
        await mcp_manager.start_all()
    except Exception as e:
        console.print(f"[red]Failed to start MCP servers: {e}[/red]")
        console.print("[yellow]Continuing without MCP servers (some features may be limited)[/yellow]\n")

    # Read spec file if provided
    spec_content = None
    if spec:
        spec_content = spec.read_text()

    # Create initial state
    initial_state: OrchestrationState = {
        "repo": repo,
        "issue_number": issue,
        "pr_number": pr,
        "spec_content": spec_content,
        "mode": mode,
        "messages": [],
        "plan": None,
        "tasks": [],
        "files_changed": [],
        "branches_created": [],
        "prs_created": [],
        "test_results": None,
        "test_failures": [],
        "review_comments": [],
        "approval_status": None,
        "agent_results": [],
        "current_agent": None,
        "next_agents": [],
        "retry_count": 0,
        "max_retries": 3,
        "started_at": datetime.now(),
        "completed_at": None,
        "error": None,
    }

    # Create graph
    graph = create_orchestration_graph()

    # Run workflow with progress
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Running orchestration...", total=None)

            config = {"configurable": {"thread_id": f"cli-{datetime.now().timestamp()}"}}
            final_state = await graph.ainvoke(initial_state, config)

            progress.update(task, completed=True)

        # Display results
        console.print("\n[bold green]✓ Orchestration completed![/bold green]\n")

        if final_state.get("plan"):
            console.print("[bold]Plan:[/bold]")
            console.print(f"  Tasks: {len(final_state.get('tasks', []))}")

        if final_state.get("files_changed"):
            console.print(f"\n[bold]Files changed:[/bold] {len(final_state['files_changed'])}")
            for file in final_state["files_changed"][:5]:
                console.print(f"  • {file}")

        if final_state.get("prs_created"):
            console.print(f"\n[bold]PRs created:[/bold]")
            for pr_num in final_state["prs_created"]:
                console.print(f"  • #{pr_num}: https://github.com/{repo}/pull/{pr_num}")

        if final_state.get("test_results"):
            results = final_state["test_results"]
            console.print(f"\n[bold]Tests:[/bold]")
            console.print(f"  Passed: [green]{results.get('passed', 0)}[/green]")
            console.print(f"  Failed: [red]{results.get('failed', 0)}[/red]")

        if final_state.get("approval_status"):
            status = final_state["approval_status"]
            color = "green" if status == "APPROVE" else "yellow"
            console.print(f"\n[bold]Review:[/bold] [{color}]{status}[/{color}]")

    except Exception as e:
        console.print(f"\n[bold red]✗ Orchestration failed![/bold red]")
        console.print(f"[red]{str(e)}[/red]")
        raise typer.Exit(1)

    finally:
        # Cleanup
        await mcp_manager.stop_all()


if __name__ == "__main__":
    app()
