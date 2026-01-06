"""CLI command to run orchestration workflows."""

import asyncio
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.config import get_settings
from src.core.graph import create_orchestration_graph
from src.core.state import OrchestrationState


app = typer.Typer(
    name="orchestrate",
    help="AI Orchestration Platform CLI",
)

console = Console()


@app.command()
def run(
    repo: str = typer.Option(..., "--repo", "-r", help="Repository (owner/name)"),
    issue: int | None = typer.Option(None, "--issue", "-i", help="Issue number"),
    pr: int | None = typer.Option(None, "--pr", "-p", help="PR number"),
    spec: Path | None = typer.Option(None, "--spec", "-s", help="Specification file"),
    mode: str = typer.Option("autonomous", "--mode", "-m", help="Mode: autonomous, plan, review"),
    max_retries: int = typer.Option(3, "--max-retries", help="Maximum retry attempts"),
) -> None:
    """Run an orchestration workflow."""
    asyncio.run(run_workflow(repo, issue, pr, spec, mode, max_retries))


async def run_workflow(
    repo: str,
    issue_number: int | None,
    pr_number: int | None,
    spec_path: Path | None,
    mode: str,
    max_retries: int,
) -> None:
    """Run the orchestration workflow."""
    console.print(f"\n[bold blue]✨ AI Orchestration Platform[/bold blue]")
    console.print(f"Repository: [cyan]{repo}[/cyan]")
    console.print(f"Mode: [yellow]{mode}[/yellow]\n")
    
    # Load spec if provided
    spec_content = None
    if spec_path:
        if not spec_path.exists():
            console.print(f"[red]❌ Spec file not found: {spec_path}[/red]")
            raise typer.Exit(1)
        spec_content = spec_path.read_text()
    
    # Validate inputs
    if not issue_number and not pr_number and not spec_content:
        console.print("[red]❌ Must provide --issue, --pr, or --spec[/red]")
        raise typer.Exit(1)
    
    # Create initial state
    initial_state: OrchestrationState = {
        "repo": repo,
        "issue_number": issue_number,
        "pr_number": pr_number,
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
        "max_retries": max_retries,
        "started_at": datetime.now(),
        "completed_at": None,
        "error": None,
    }
    
    # Create and run graph
    console.print("[bold]🚀 Starting orchestration...[/bold]\n")
    
    graph = create_orchestration_graph()
    config = {"configurable": {"thread_id": f"cli-{datetime.now().timestamp()}"}}
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Running workflow...", total=None)
            
            final_state = None
            async for state in graph.astream(initial_state, config):
                # Update progress with current agent
                if "current_agent" in state and state["current_agent"]:
                    progress.update(task, description=f"Agent: {state['current_agent'].value}")
                final_state = state
        
        # Display results
        console.print("\n[bold green]✅ Orchestration completed![/bold green]\n")
        
        display_results(final_state)
    
    except Exception as e:
        console.print(f"\n[bold red]❌ Orchestration failed:[/bold red] {e}\n")
        raise typer.Exit(1)


def display_results(state: OrchestrationState) -> None:
    """Display orchestration results in a table."""
    # Agent results table
    table = Table(title="Agent Results")
    table.add_column("Agent", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Output", style="white")
    
    for result in state.get("agent_results", []):
        status_emoji = "✅" if result["status"] == "completed" else "❌"
        table.add_row(
            result["agent"].value,
            f"{status_emoji} {result['status']}",
            result["output"][:80] + "..." if len(result["output"]) > 80 else result["output"],
        )
    
    console.print(table)
    
    # Summary
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"Files changed: {len(state.get('files_changed', []))}")
    console.print(f"Branches created: {len(state.get('branches_created', []))}")
    console.print(f"PRs created: {len(state.get('prs_created', []))}")
    
    if state.get("prs_created"):
        for pr_num in state["prs_created"]:
            console.print(f"\n[bold blue]🔗 PR #{pr_num}:[/bold blue] {state['repo']}/pull/{pr_num}")


if __name__ == "__main__":
    app()
