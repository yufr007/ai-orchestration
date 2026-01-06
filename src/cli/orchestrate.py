"""CLI for running orchestration workflows."""

import asyncio
from datetime import datetime
from pathlib import Path

import typer
import structlog
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.config import get_settings
from src.core.graph import create_orchestration_graph
from src.core.state import OrchestrationState

app = typer.Typer(help="AI Orchestration CLI")
console = Console()
logger = structlog.get_logger()


@app.command()
def orchestrate(
    repo: str = typer.Option(..., "--repo", "-r", help="GitHub repository (owner/repo)"),
    issue: int | None = typer.Option(None, "--issue", "-i", help="Issue number to implement"),
    pr: int | None = typer.Option(None, "--pr", "-p", help="PR number to review"),
    spec: Path | None = typer.Option(None, "--spec", "-s", help="Path to specification file"),
    mode: str = typer.Option(
        "autonomous",
        "--mode",
        "-m",
        help="Execution mode (autonomous|plan|review)",
    ),
    trace: bool = typer.Option(False, "--trace", help="Enable LangSmith tracing"),
):
    """Run AI orchestration workflow."""
    console.print("\n[bold blue]🤖 AI Orchestration Platform[/bold blue]\n")

    # Load spec content if provided
    spec_content = None
    if spec:
        if not spec.exists():
            console.print(f"[red]Error: Spec file not found: {spec}[/red]")
            raise typer.Exit(1)
        spec_content = spec.read_text()

    # Validate inputs
    if not issue and not pr and not spec_content:
        console.print("[red]Error: Must provide --issue, --pr, or --spec[/red]")
        raise typer.Exit(1)

    # Enable tracing if requested
    if trace:
        import os

        os.environ["LANGCHAIN_TRACING_V2"] = "true"

    # Run orchestration
    asyncio.run(
        run_orchestration(
            repo=repo,
            issue_number=issue,
            pr_number=pr,
            spec_content=spec_content,
            mode=mode,
        )
    )


async def run_orchestration(
    repo: str,
    issue_number: int | None,
    pr_number: int | None,
    spec_content: str | None,
    mode: str,
):
    """Execute orchestration workflow."""
    console.print(f"[cyan]Repository:[/cyan] {repo}")
    console.print(f"[cyan]Mode:[/cyan] {mode}\n")

    # Create graph
    graph = create_orchestration_graph()

    # Prepare initial state
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
        "max_retries": 3,
        "started_at": datetime.utcnow(),
        "completed_at": None,
        "error": None,
    }

    # Execute with progress display
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Initializing...", total=None)

        async for state in graph.astream(initial_state):
            if state:
                current_node = list(state.keys())[0]
                node_state = state.get(current_node, {})
                current_agent = node_state.get("current_agent")

                if current_agent:
                    progress.update(task, description=f"[cyan]Running {current_agent}...")

        progress.update(task, description="[green]✅ Completed")

    # Display results
    final_state = node_state if state else initial_state
    display_results(final_state)


def display_results(state: OrchestrationState):
    """Display orchestration results."""
    console.print("\n[bold green]=== Results ===[/bold green]\n")

    # Plan
    if state.get("plan"):
        plan = state["plan"]
        console.print(f"[cyan]Plan:[/cyan] {plan.get('summary', 'N/A')}")
        console.print(f"[cyan]Tasks:[/cyan] {len(state.get('tasks', []))}")

    # PRs created
    if state.get("prs_created"):
        console.print(f"\n[cyan]PRs Created:[/cyan]")
        for pr_num in state["prs_created"]:
            pr_url = f"https://github.com/{state['repo']}/pull/{pr_num}"
            console.print(f"  - PR #{pr_num}: {pr_url}")

    # Test results
    if state.get("test_results"):
        results = state["test_results"]
        status = "✅" if results.get("passed") else "❌"
        console.print(f"\n[cyan]Tests:[/cyan] {status} {results.get('passed', 0)}/{results.get('total', 0)} passed")

    # Review
    if state.get("approval_status"):
        console.print(f"\n[cyan]Review:[/cyan] {state['approval_status']}")

    # Errors
    if state.get("error"):
        console.print(f"\n[red]Error:[/red] {state['error']}")

    console.print()


if __name__ == "__main__":
    app()
