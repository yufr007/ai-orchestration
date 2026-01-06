"""Pydantic models for API requests and responses."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobMode(str, Enum):
    """Job execution mode."""

    AUTONOMOUS = "autonomous"
    PLAN = "plan"
    REVIEW = "review"


class JobStatus(str, Enum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobCreate(BaseModel):
    """Request model for creating a new job."""

    repo: str = Field(..., description="Repository in format owner/name")
    issue_number: int | None = Field(None, description="GitHub issue number to implement")
    pr_number: int | None = Field(None, description="GitHub PR number to review")
    spec_content: str | None = Field(None, description="Inline specification content")
    mode: JobMode = Field(default=JobMode.AUTONOMOUS, description="Execution mode")

    class Config:
        json_schema_extra = {
            "example": {
                "repo": "yufr007/vitaflow",
                "issue_number": 123,
                "mode": "autonomous",
            }
        }


class JobResponse(BaseModel):
    """Response model for job status."""

    id: str
    status: JobStatus
    repo: str
    created_at: datetime
    updated_at: datetime
    result: dict[str, Any] | None = None
    error: str | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "repo": "yufr007/vitaflow",
                "created_at": "2026-01-07T00:00:00Z",
                "updated_at": "2026-01-07T00:05:00Z",
                "result": {
                    "files_changed": ["src/feature.py"],
                    "prs_created": [456],
                    "approval_status": "APPROVE",
                },
            }
        }
