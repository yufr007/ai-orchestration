"""Main CLI for running orchestration workflows."""

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
    help="AI Orchestration Platform - Elite multi-agent development team",
)
console = Console()


@app.command()
def run(
    repo: str = typer.Option(..., "--repo", "-r", help="Repository (owner/repo)"),
    issue: int | None = typer.Option(None, "--issue", "-i", help="GitHub issue number"),
    pr: int | None = typer.Option(None, "--pr", "-p", help="GitHub PR number"),
    spec: Path | None = typer.Option(None, "--spec", "-s", help="Path to specification file"),
    mode: str = typer.Option(
        "autonomous",
        "--mode",
        "-m",
        help="Mode: autonomous, plan, or review",
    ),
    max_retries: int = typer.Option(3, "--max-retries", help="Maximum retry attempts"),
    trace: bool = typer.Option(False, "--trace", help="Enable LangSmith tracing"),
) -> None:
    """Run an orchestration workflow.

    Examples:
        # Implement a GitHub issue
        orchestrate run --repo yufr007/vitaflow --issue 123

        # Plan from specification
        orchestrate run --repo yufr007/autom8 --spec specs/feature.md --mode plan

        # Review existing PR
        orchestrate run --repo yufr007/vitaflow --pr 45 --mode review
    """
    console.print("\n[bold cyan]🤖 AI Orchestration Platform[/bold cyan]\n")

    # Load spec if provided
    spec_content = None
    if spec:
        if not spec.exists():
            console.print(f"[red]❌ Spec file not found: {spec}[/red]")
            raise typer.Exit(1)
        spec_content = spec.read_text()
        console.print(f"[green]✅ Loaded spec from {spec}[/green]")

    # Validate inputs
    if not issue and not pr and not spec_content:
        console.print("[red]❌ Must provide --issue, --pr, or --spec[/red]")
        raise typer.Exit(1)

    # Enable tracing if requested
    if trace:
        settings = get_settings()
        if settings.langsmith_api_key:
            import os

            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            console.print("[green]✅ LangSmith tracing enabled[/green]\n")

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
        "max_retries": max_retries,
        "started_at": datetime.now(),
        "completed_at": None,
        "error": None,
    }

    # Run orchestration
    asyncio.run(run_orchestration(initial_state))


async def run_orchestration(state: OrchestrationState) -> None:
    """Execute the orchestration workflow."""
    console.print(f"[bold]Repository:[/bold] {state['repo']}")
    console.print(f"[bold]Mode:[/bold] {state['mode']}")
    if state.get("issue_number"):
        console.print(f"[bold]Issue:[/bold] #{state['issue_number']}")
    if state.get("pr_number"):
        console.print(f"[bold]PR:[/bold] #{state['pr_number']}")
    console.print()

    try:
        # Create graph
        graph = create_orchestration_graph()
        config = {"configurable": {"thread_id": "cli-" + datetime.now().strftime("%Y%m%d-%H%M%S")}}

        # Execute with progress tracking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Starting orchestration...", total=None)

            async for event in graph.astream(state, config):
                # Update progress based on current agent
                current_agent = event.get("current_agent")
                if current_agent:
                    progress.update(task, description=f"[cyan]Running {current_agent.value} agent...")

            progress.update(task, description="[green]✅ Orchestration complete")

        # Display results
        console.print("\n[bold green]✅ Workflow Complete![/bold green]\n")
        display_results(event)

    except Exception as e:
        console.print(f"\n[bold red]❌ Orchestration failed:[/bold red] {e}\n")
        raise typer.Exit(1)


def display_results(final_state: dict) -> None:
    """Display workflow results in a formatted table."""
    table = Table(title="Orchestration Results", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    # Add key metrics
    if final_state.get("plan"):
        table.add_row("Tasks Planned", str(len(final_state.get("tasks", []))))

    if final_state.get("files_changed"):
        table.add_row("Files Changed", str(len(final_state["files_changed"])))

    if final_state.get("prs_created"):
        for pr_num in final_state["prs_created"]:
            table.add_row("PR Created", f"#{pr_num}")

    if final_state.get("test_results"):
        test_results = final_state["test_results"]
        table.add_row(
            "Tests",
            f"{test_results.get('passed', 0)}/{test_results.get('total', 0)} passed",
        )

    if final_state.get("approval_status"):
        table.add_row("Review Status", final_state["approval_status"])

    console.print(table)


@app.command()
def version() -> None:
    """Show version information."""
    console.print("[bold]AI Orchestration Platform[/bold] v0.1.0")
    console.print("Built with LangGraph, Perplexity MCP, and GitHub integration")


if __name__ == "__main__":
    app()
