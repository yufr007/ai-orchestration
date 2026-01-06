"""Main CLI for running orchestration workflows."""

import asyncio
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.config import get_settings
from src.core.graph import create_orchestration_graph
from src.core.state import OrchestrationState

app = typer.Typer(
    name="orchestrate",
    help="AI Orchestration Platform CLI",
    add_completion=False,
)

console = Console()


@app.command()
def run(
    repo: str = typer.Option(..., "--repo", "-r", help="Repository (owner/repo)"),
    issue: int | None = typer.Option(None, "--issue", "-i", help="GitHub issue number"),
    pr: int | None = typer.Option(None, "--pr", "-p", help="GitHub PR number"),
    spec: Path | None = typer.Option(None, "--spec", "-s", help="Specification file path"),
    mode: str = typer.Option(
        "autonomous", "--mode", "-m", help="Mode: autonomous, plan, or review"
    ),
) -> None:
    """Run an orchestration workflow."""
    console.print("\n[bold cyan]AI Orchestration Platform[/bold cyan]\n")
    
    # Load spec content if provided
    spec_content = None
    if spec:
        if not spec.exists():
            console.print(f"[red]Error: Spec file not found: {spec}[/red]")
            raise typer.Exit(1)
        spec_content = spec.read_text()
    
    # Create initial state
    state: OrchestrationState = {
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
    
    console.print(f"Repository: [bold]{repo}[/bold]")
    if issue:
        console.print(f"Issue: [bold]#{issue}[/bold]")
    if pr:
        console.print(f"PR: [bold]#{pr}[/bold]")
    console.print(f"Mode: [bold]{mode}[/bold]\n")
    
    # Run workflow
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running orchestration...", total=None)
        
        try:
            final_state = asyncio.run(run_workflow(state, progress, task))
            
            progress.update(task, description="[green]Complete!")
            
            # Display results
            display_results(final_state)
            
        except Exception as e:
            progress.update(task, description="[red]Failed!")
            console.print(f"\n[red]Error: {e}[/red]")
            raise typer.Exit(1)


async def run_workflow(
    state: OrchestrationState, progress: Progress, task_id: int
) -> OrchestrationState:
    """Run the orchestration workflow."""
    graph = create_orchestration_graph()
    
    config = {"configurable": {"thread_id": "cli-session"}}
    
    final_state = state
    
    async for event in graph.astream(state, config):
        # Update progress with current agent
        for node_name, node_state in event.items():
            if "current_agent" in node_state:
                agent = node_state["current_agent"]
                progress.update(task_id, description=f"Running {agent}...")
        
        final_state = event
    
    return final_state


def display_results(state: OrchestrationState) -> None:
    """Display workflow results."""
    console.print("\n[bold cyan]Results[/bold cyan]\n")
    
    # Agent results table
    if state.get("agent_results"):
        table = Table(title="Agent Execution")
        table.add_column("Agent", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Output", style="white")
        
        for result in state["agent_results"]:
            table.add_row(
                result["agent"],
                result["status"],
                result["output"][:100] + "..." if len(result["output"]) > 100 else result["output"],
            )
        
        console.print(table)
        console.print()
    
    # Artifacts
    if state.get("branches_created"):
        console.print(f"Branches created: {', '.join(state['branches_created'])}")
    
    if state.get("prs_created"):
        console.print(f"PRs created: {', '.join(f'#{pr}' for pr in state['prs_created'])}")
    
    if state.get("approval_status"):
        status_color = "green" if state["approval_status"] == "approved" else "yellow"
        console.print(f"\nReview status: [{status_color}]{state['approval_status']}[/{status_color}]")
    
    console.print()


@app.command()
def version() -> None:
    """Show version information."""
    console.print("[bold cyan]AI Orchestration Platform[/bold cyan]")
    console.print("Version: [bold]0.1.0[/bold]")


if __name__ == "__main__":
    app()
