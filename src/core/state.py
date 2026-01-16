"""State management for orchestration workflows."""

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, TypedDict

from langgraph.graph import add_messages


class AgentRole(str, Enum):
    """Available agent roles in the orchestration."""

    PLANNER = "planner"
    ARCHITECT = "architect"
    CODER = "coder"
    TESTER = "tester"
    REVIEWER = "reviewer"
    DEVOPS = "devops"
    SECURITY = "security"
    RELEASE_MANAGER = "release_manager"
    DESIGNER = "designer"


class TaskStatus(str, Enum):
    """Status of a task in the workflow."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class AgentResult(TypedDict):
    """Result from an agent execution."""

    agent: AgentRole
    status: TaskStatus
    output: str
    artifacts: dict[str, Any]
    metadata: dict[str, Any]
    timestamp: datetime


class OrchestrationState(TypedDict):
    """State shared across all agents in the orchestration."""

    # Input
    repo: str
    issue_number: int | None
    pr_number: int | None
    spec_content: str | None
    mode: str  # "autonomous", "plan", "review"

    # Messages
    messages: Annotated[list, add_messages]

    # Planning
    plan: dict[str, Any] | None
    tasks: list[dict[str, Any]]

    # Implementation
    files_changed: list[str]
    branches_created: list[str]
    prs_created: list[int]

    # Testing
    test_results: dict[str, Any] | None
    test_failures: list[dict[str, Any]]

    # Review
    review_comments: list[dict[str, Any]]
    approval_status: str | None

    # Agent Results
    agent_results: list[AgentResult]

    # Control Flow
    current_agent: AgentRole | None
    next_agents: list[AgentRole]
    retry_count: int
    max_retries: int

    # Metadata
    started_at: datetime
    completed_at: datetime | None
    error: str | None
