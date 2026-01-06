"""Pytest configuration and fixtures."""

import pytest
from datetime import datetime

from src.core.state import OrchestrationState, AgentRole


@pytest.fixture
def mock_state() -> OrchestrationState:
    """Create a mock orchestration state for testing."""
    return {
        "repo": "test-user/test-repo",
        "issue_number": 123,
        "pr_number": None,
        "spec_content": "Test specification",
        "mode": "autonomous",
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


@pytest.fixture
def mock_plan() -> dict:
    """Create a mock execution plan."""
    return {
        "summary": "Test implementation",
        "tasks": [
            {
                "id": "task_1",
                "title": "Implement feature",
                "description": "Add new feature",
                "files": ["src/feature.py"],
                "complexity": "medium",
            }
        ],
    }
