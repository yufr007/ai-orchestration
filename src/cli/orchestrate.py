"""Main CLI for orchestration operations."""

import asyncio
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.config import get_settings
from src.core import create_orchestration_graph, OrchestrationState

app = typer.Typer(
    name="orchestrate",
    help="AI Orchestration Platform - Elite multi-agent development team",
)
console = Console()
settings = get_settings()


@app.command()
def run(
    repo: str = typer.Option(..., "--repo", "-r", help="Repository (owner/repo)"),
    issue: Optional[int] = typer.Option(None, "--issue", "-i", help="Issue number to implement"),
    pr: Optional[int] = typer.Option(None, "--pr", "-p", help="PR number to review"),
    spec: Optional[str] = typer.Option(None, "--spec", "-s", help="Path to specification file"),
    mode: str = typer.Option(
        "autonomous",
        "--mode",
        "-m",
        help="Execution mode: autonomous, plan, review",
    ),
    trace: bool = typer.Option(False, "--trace", help="Enable LangSmith tracing"),
) -> None:
    """Run orchestration workflow.

    Examples:
        # Implement an issue
        orchestrate run --repo yufr007/vitaflow --issue 123

        # Plan only
        orchestrate run --repo yufr007/vitaflow --spec specs/feature.md --mode plan

        # Review PR
        orchestrate run --repo yufr007/vitaflow --pr 45 --mode review
    """
    # Validate inputs
    if not any([issue, pr, spec]):
        console.print("[red]Error: Must provide --issue, --pr, or --spec[/red]")
        raise typer.Exit(1)

    # Load spec content if provided
    spec_content = None
    if spec:
        try:
            with open(spec, "r") as f:
                spec_content = f.read()
        except FileNotFoundError:
            console.print(f"[red]Error: Spec file not found: {spec}[/red]")
            raise typer.Exit(1)

    # Enable tracing if requested
    if trace:
        import os

        os.environ["LANGCHAIN_TRACING_V2"] = "true"

    console.print("\n[bold cyan]✨ AI Orchestration Platform[/bold cyan]")
    console.print(f"Repository: [yellow]{repo}[/yellow]")
    if issue:
        console.print(f"Issue: [yellow]#{issue}[/yellow]")
    if pr:
        console.print(f"PR: [yellow]#{pr}[/yellow]")
    console.print(f"Mode: [yellow]{mode}[/yellow]\n")

    # Run orchestration
    asyncio.run(execute_orchestration(repo, issue, pr, spec_content, mode))


async def execute_orchestration(
    repo: str,
    issue_number: Optional[int],
    pr_number: Optional[int],
    spec_content: Optional[str],
    mode: str,
) -> None:
    """Execute the orchestration workflow."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing...", total=None)

        try:
            # Create workflow
            progress.update(task, description="Creating workflow graph...")
            graph = create_orchestration_graph()

            # Prepare state
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
                "started_at": datetime.now(),
                "completed_at": None,
                "error": None,
            }

            # Execute workflow
            progress.update(task, description="Executing workflow...")
            result = await graph.ainvoke(
                initial_state, {"configurable": {"thread_id": f"cli-{datetime.now().timestamp()}"}}
            )

            # Display results
            progress.stop()
            console.print("\n[bold green]✅ Orchestration Complete![/bold green]\n")

            # Display summary
            if result.get("plan"):
                console.print("[bold]Plan:[/bold]")
                console.print(f"  {result['plan'].get('summary', 'Created')}")
                console.print(f"  Tasks: {len(result.get('tasks', []))}\n")

            if result.get("files_changed"):
                console.print("[bold]Files Changed:[/bold]")
                for file in result["files_changed"]:
                    console.print(f"  • {file}")
                console.print()

            if result.get("prs_created"):
                console.print("[bold]Pull Requests:[/bold]")
                for pr in result["prs_created"]:
                    console.print(f"  • PR #{pr}")
                console.print()

            if result.get("test_results"):
                test_results = result["test_results"]
                status = "✅ PASSED" if test_results.get("passed") else "❌ FAILED"
                console.print(f"[bold]Tests:[/bold] {status}")
                console.print(f"  Generated: {test_results.get('tests_generated', 0)}\n")

            if result.get("approval_status"):
                console.print(f"[bold]Review:[/bold] {result['approval_status'].upper()}\n")

        except Exception as e:
            progress.stop()
            console.print(f"\n[bold red]❌ Error:[/bold red] {e}\n")
            raise typer.Exit(1)


@app.command()
def version() -> None:
    """Show version information."""
    console.print("[bold]AI Orchestration Platform[/bold]")
    console.print("Version: [cyan]0.1.0[/cyan]")
    console.print(f"Python: [cyan]{settings.default_agent_model}[/cyan]")


if __name__ == "__main__":
    app()
