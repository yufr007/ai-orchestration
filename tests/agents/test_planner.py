"""Tests for planner agent."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.agents.planner import planner_node
from src.core.state import OrchestrationState, AgentRole, TaskStatus


@pytest.mark.asyncio
async def test_planner_node_with_issue(mock_github_client: MagicMock, mock_perplexity_client: MagicMock, mock_llm: MagicMock) -> None:
    """Test planner node with GitHub issue."""
    # Setup mocks
    mock_github_client.get_issue = AsyncMock(return_value={
        "number": 123,
        "title": "Implement feature X",
        "body": "Add feature X to the system",
        "labels": ["enhancement"],
    })
    
    mock_perplexity_client.search = AsyncMock(return_value="Best practices for feature X...")
    
    mock_response = MagicMock()
    mock_response.content = "Implementation plan: 1. Create module, 2. Add tests"
    mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
    
    # Create state
    state: OrchestrationState = {
        "repo": "owner/repo",
        "issue_number": 123,
        "pr_number": None,
        "spec_content": None,
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
    
    # Execute
    result = await planner_node(state)
    
    # Verify
    assert result["plan"] is not None
    assert result["tasks"] is not None
    assert len(result["agent_results"]) == 1
    assert result["agent_results"][0]["agent"] == AgentRole.PLANNER
    assert result["agent_results"][0]["status"] == TaskStatus.COMPLETED
