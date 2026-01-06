"""Integration tests for complete workflows."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.graph import create_orchestration_graph
from src.core.state import OrchestrationState


@pytest.mark.asyncio
@pytest.mark.integration
async def test_complete_workflow_plan_mode() -> None:
    """Test complete workflow in plan-only mode."""
    # This is a simplified integration test
    # In production, use live APIs with test repositories
    
    with patch("src.agents.planner.planner_node") as mock_planner:
        # Setup mocks
        mock_planner.return_value = {
            "plan": {"summary": "Test plan"},
            "tasks": [{"id": "task-1"}],
            "agent_results": [],
            "messages": [],
        }
        
        # Create state
        state: OrchestrationState = {
            "repo": "owner/repo",
            "issue_number": 123,
            "pr_number": None,
            "spec_content": None,
            "mode": "plan",
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
        graph = create_orchestration_graph()
        
        final_state = None
        async for event in graph.astream(state, {"configurable": {"thread_id": "test"}}):
            final_state = event
        
        # Verify
        # In plan mode, should only execute planner
        assert mock_planner.called
