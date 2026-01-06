"""LangGraph orchestration graph definition."""

from typing import Literal

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver

from src.agents.planner import planner_node
from src.agents.coder import coder_node
from src.agents.tester import tester_node
from src.agents.reviewer import reviewer_node
from src.config import get_settings
from src.core.state import OrchestrationState, AgentRole


def should_continue_to_coder(state: OrchestrationState) -> Literal["coder", "end"]:
    """Conditional edge: proceed to coder or end."""
    if state.get("mode") == "plan":
        return "end"
    if not state.get("plan") or not state.get("tasks"):
        return "end"
    return "coder"


def should_continue_to_tester(state: OrchestrationState) -> Literal["tester", "reviewer", "end"]:
    """Conditional edge: proceed to tester, reviewer, or end."""
    if not state.get("files_changed"):
        return "end"
    # If in review mode, skip testing and go straight to reviewer
    if state.get("mode") == "review":
        return "reviewer"
    return "tester"


def should_continue_after_testing(
    state: OrchestrationState,
) -> Literal["coder", "reviewer", "end"]:
    """Conditional edge: retry coding, proceed to review, or end."""
    test_results = state.get("test_results")
    test_failures = state.get("test_failures", [])

    if test_failures and state.get("retry_count", 0) < state.get("max_retries", 3):
        # Tests failed and we haven't exceeded retries - go back to coder
        return "coder"

    if test_results and test_results.get("passed", False):
        # Tests passed - proceed to reviewer
        return "reviewer"

    # Tests failed and exceeded retries - end with failure
    return "end"


def should_continue_after_review(state: OrchestrationState) -> Literal["coder", "end"]:
    """Conditional edge: implement review changes or end."""
    approval_status = state.get("approval_status")
    review_comments = state.get("review_comments", [])

    if approval_status == "changes_requested" and review_comments:
        if state.get("retry_count", 0) < state.get("max_retries", 3):
            return "coder"

    # Approved or max retries reached
    return "end"


def create_orchestration_graph() -> StateGraph:
    """Create the main orchestration graph with all agents and conditional routing."""
    settings = get_settings()

    # Initialize graph with state
    workflow = StateGraph(OrchestrationState)

    # Add agent nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("tester", tester_node)
    workflow.add_node("reviewer", reviewer_node)

    # Define edges
    workflow.set_entry_point("planner")

    # Planner -> Coder (conditional: only if not plan-only mode)
    workflow.add_conditional_edges("planner", should_continue_to_coder, {"coder": "coder", "end": END})

    # Coder -> Tester or Reviewer (conditional)
    workflow.add_conditional_edges(
        "coder",
        should_continue_to_tester,
        {"tester": "tester", "reviewer": "reviewer", "end": END},
    )

    # Tester -> Coder (retry) or Reviewer (success) or End (failure)
    workflow.add_conditional_edges(
        "tester",
        should_continue_after_testing,
        {"coder": "coder", "reviewer": "reviewer", "end": END},
    )

    # Reviewer -> Coder (changes requested) or End (approved)
    workflow.add_conditional_edges(
        "reviewer", should_continue_after_review, {"coder": "coder", "end": END}
    )

    # Compile with checkpointing for persistence
    checkpointer = SqliteSaver.from_conn_string(settings.database_url.replace("sqlite:///", ""))

    return workflow.compile(checkpointer=checkpointer)
