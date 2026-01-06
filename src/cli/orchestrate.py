"""Main CLI for orchestration."""

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
    help="AI Orchestration Platform - Autonomous software development",
)
console = Console()


@app.command()
def run(
    repo: str = typer.Option(..., "--repo", "-r", help="Repository (owner/repo)"),
    issue: int | None = typer.Option(None, "--issue", "-i", help="Issue number"),
    pr: int | None = typer.Option(None, "--pr", "-p", help="PR number to review"),
    spec: Path | None = typer.Option(None, "--spec", "-s", help="Spec file path"),
    mode: str = typer.Option(
        "autonomous",
        "--mode",
        "-m",
        help="Mode: autonomous, plan, review",
    ),
    trace: bool = typer.Option(False, "--trace", help="Enable LangSmith tracing"),
) -> None:
    """Run orchestration workflow."""
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

    # Enable tracing if requested
    if trace and settings.langsmith_api_key:
        import os

        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        console.print("[green]✓[/green] LangSmith tracing enabled")

    # Load spec if provided
    spec_content = None
    if spec and spec.exists():
        spec_content = spec.read_text()
        console.print(f"[green]✓[/green] Loaded spec from {spec}")

    # Validate inputs
    if not issue and not pr and not spec_content:
        console.print("[red]Error:[/red] Must provide --issue, --pr, or --spec")
        raise typer.Exit(1)

    console.print(f"\n[bold blue]AI Orchestration Platform[/bold blue]")
    console.print(f"Repository: {repo}")
    console.print(f"Mode: {mode}")
    if issue:
        console.print(f"Issue: #{issue}")
    if pr:
        console.print(f"PR: #{pr}")
    console.print()

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

    # Create and run graph
    graph = create_orchestration_graph()
    config = {"configurable": {"thread_id": f"cli-{datetime.now().timestamp()}"}}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running orchestration...", total=None)

        try:
            result = await graph.ainvoke(initial_state, config=config)

            progress.update(task, completed=True, description="[green]✓ Complete[/green]")

            # Display results
            display_results(result)

        except Exception as e:
            progress.update(task, description=f"[red]✗ Failed: {e}[/red]")
            raise


def display_results(result: OrchestrationState) -> None:
    """Display orchestration results."""
    console.print("\n[bold green]Results[/bold green]\n")

    # Agent results table
    table = Table(title="Agent Execution")
    table.add_column("Agent", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Output", style="white")

    for agent_result in result.get("agent_results", []):
        status_emoji = "✓" if agent_result["status"] == "completed" else "✗"
        table.add_row(
            agent_result["agent"].value,
            f"{status_emoji} {agent_result['status'].value}",
            agent_result["output"][:100] + "..." if len(agent_result["output"]) > 100 else agent_result["output"],
        )

    console.print(table)

    # Plan summary
    if result.get("plan"):
        console.print("\n[bold]Plan Summary[/bold]")
        plan = result["plan"]
        console.print(f"Tasks: {len(plan.get('tasks', []))}")
        console.print(f"Complexity: {plan.get('estimated_complexity', 'unknown')}")

    # Implementation summary
    if result.get("files_changed"):
        console.print("\n[bold]Implementation[/bold]")
        console.print(f"Files changed: {len(result['files_changed'])}")
        for file in result["files_changed"][:5]:
            console.print(f"  • {file}")
        if len(result["files_changed"]) > 5:
            console.print(f"  ... and {len(result['files_changed']) - 5} more")

    # PR links
    if result.get("prs_created"):
        console.print("\n[bold]Pull Requests[/bold]")
        for pr_num in result["prs_created"]:
            pr_url = f"https://github.com/{result['repo']}/pull/{pr_num}"
            console.print(f"  • PR #{pr_num}: {pr_url}")

    # Test results
    if result.get("test_results"):
        test_res = result["test_results"]
        console.print("\n[bold]Testing[/bold]")
        console.print(
            f"Tests: {test_res.get('passed_tests', 0)}/{test_res.get('total_tests', 0)} passed"
        )
        console.print(f"Coverage: {test_res.get('coverage', 0)}%")

    console.print()


@app.command()
def init() -> None:
    """Initialize configuration and verify setup."""
    console.print("[bold blue]Initializing AI Orchestration Platform[/bold blue]\n")

    try:
        settings = get_settings()

        # Check required keys
        checks = [
            ("Perplexity API", bool(settings.perplexity_api_key)),
            ("GitHub Token", bool(settings.github_token)),
            (
                "LLM API",
                bool(settings.anthropic_api_key or settings.openai_api_key),
            ),
        ]

        for name, status in checks:
            symbol = "[green]✓[/green]" if status else "[red]✗[/red]"
            console.print(f"{symbol} {name}")

        if all(status for _, status in checks):
            console.print("\n[green]✓ Setup complete![/green]")
        else:
            console.print("\n[yellow]⚠ Some configurations missing. Check .env file.[/yellow]")

    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
