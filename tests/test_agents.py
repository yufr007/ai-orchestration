"""Tests for agent implementations."""

import pytest
from unittest.mock import AsyncMock, patch

from src.agents.planner import PlannerAgent
from src.agents.coder import CoderAgent
from src.core.state import OrchestrationState, AgentRole


@pytest.mark.asyncio
async def test_planner_agent_creates_plan(sample_issue, sample_plan):
    """Test that planner agent creates a valid plan."""
    state: OrchestrationState = {
        "repo": "test-owner/test-repo",
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
        "started_at": None,
        "completed_at": None,
        "error": None,
    }

    agent = PlannerAgent()

    with patch("src.tools.github.get_issue_details", return_value=sample_issue):
        with patch("src.tools.github.get_repository_context", return_value={"language": "Python"}):
            with patch("src.tools.perplexity.research_with_perplexity", return_value="Research results"):
                with patch.object(agent, "_call_llm", return_value=str(sample_plan).replace("'", '"')):
                    result = await agent.execute(state)

    assert result["plan"] is not None
    assert len(result["tasks"]) > 0
    assert result["plan"]["summary"] == "Implement feature X"


@pytest.mark.asyncio
async def test_coder_agent_creates_branch(sample_plan):
    """Test that coder agent creates a branch and PR."""
    state: OrchestrationState = {
        "repo": "test-owner/test-repo",
        "issue_number": None,
        "pr_number": None,
        "spec_content": None,
        "mode": "autonomous",
        "messages": [],
        "plan": sample_plan,
        "tasks": sample_plan["tasks"],
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
        "started_at": None,
        "completed_at": None,
        "error": None,
    }

    agent = CoderAgent()

    with patch("src.tools.github.create_branch", return_value=True):
        with patch("src.tools.github.get_file_contents", return_value=None):
            with patch("src.tools.github.create_or_update_file", return_value={}):
                with patch("src.tools.github.create_pull_request", return_value=456):
                    with patch.object(
                        agent,
                        "_call_llm",
                        return_value='{"files": [{"path": "test.py", "content": "# test", "action": "create", "message": "Add test"}]}',
                    ):
                        result = await agent.execute(state)

    assert len(result["files_changed"]) > 0
    assert len(result["prs_created"]) > 0
    assert result["prs_created"][0] == 456
