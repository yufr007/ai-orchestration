"""FastAPI application for orchestration service."""

import asyncio
import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.config import get_settings
from src.core.graph import create_orchestration_graph
from src.core.state import OrchestrationState


# Request/Response Models
class JobRequest(BaseModel):
    """Request to create a new orchestration job."""

    repo: str = Field(..., description="Repository in format 'owner/repo'")
    issue_number: int | None = Field(None, description="Issue number to implement")
    pr_number: int | None = Field(None, description="PR number to review")
    spec_content: str | None = Field(None, description="Specification content")
    mode: str = Field("autonomous", description="Mode: autonomous, plan, review")


class JobStatus(BaseModel):
    """Job status response."""

    job_id: str
    status: str
    repo: str
    mode: str
    created_at: datetime
    updated_at: datetime
    progress: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    timestamp: datetime


# Initialize FastAPI
app = FastAPI(
    title="AI Orchestration Platform",
    description="Multi-agent orchestration for autonomous software development",
    version="0.1.0",
)

settings = get_settings()

# In-memory job store (use database in production)
jobs: dict[str, dict[str, Any]] = {}


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        timestamp=datetime.now(),
    )


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": "AI Orchestration Platform",
        "version": "0.1.0",
        "docs": "/docs",
    }


async def run_orchestration(job_id: str, job_request: JobRequest) -> None:
    """Background task to run orchestration."""
    try:
        # Update job status
        jobs[job_id]["status"] = "running"
        jobs[job_id]["updated_at"] = datetime.now()

        # Create initial state
        initial_state: OrchestrationState = {
            "repo": job_request.repo,
            "issue_number": job_request.issue_number,
            "pr_number": job_request.pr_number,
            "spec_content": job_request.spec_content,
            "mode": job_request.mode,
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
        config = {"configurable": {"thread_id": job_id}}

        result = await graph.ainvoke(initial_state, config=config)

        # Update job with results
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = result
        jobs[job_id]["updated_at"] = datetime.now()

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["updated_at"] = datetime.now()


@app.post("/api/v1/jobs", response_model=JobStatus)
async def create_job(
    job_request: JobRequest,
    background_tasks: BackgroundTasks,
) -> JobStatus:
    """Create and start a new orchestration job."""
    job_id = str(uuid.uuid4())

    # Create job record
    now = datetime.now()
    job_data = {
        "job_id": job_id,
        "status": "pending",
        "repo": job_request.repo,
        "mode": job_request.mode,
        "created_at": now,
        "updated_at": now,
        "progress": {},
        "result": None,
        "error": None,
    }
    jobs[job_id] = job_data

    # Start background task
    background_tasks.add_task(run_orchestration, job_id, job_request)

    return JobStatus(**job_data)


@app.get("/api/v1/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str) -> JobStatus:
    """Get status of a specific job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatus(**jobs[job_id])


@app.get("/api/v1/jobs")
async def list_jobs(
    limit: int = 10,
    status: str | None = None,
) -> list[JobStatus]:
    """List all jobs with optional filtering."""
    job_list = list(jobs.values())

    if status:
        job_list = [j for j in job_list if j["status"] == status]

    # Sort by created_at descending
    job_list.sort(key=lambda x: x["created_at"], reverse=True)

    return [JobStatus(**j) for j in job_list[:limit]]


@app.delete("/api/v1/jobs/{job_id}")
async def cancel_job(job_id: str) -> dict[str, str]:
    """Cancel a running job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job["status"] in ["completed", "failed"]:
        raise HTTPException(status_code=400, detail="Job already finished")

    jobs[job_id]["status"] = "cancelled"
    jobs[job_id]["updated_at"] = datetime.now()

    return {"message": "Job cancelled", "job_id": job_id}


@app.get("/api/v1/jobs/{job_id}/stream")
async def stream_job_logs(job_id: str) -> StreamingResponse:
    """Stream job logs in real-time."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        """Generate SSE events for job updates."""
        while True:
            job = jobs.get(job_id)
            if not job:
                break

            # Send status update
            yield f"data: {job['status']}\n\n"

            # Check if job is finished
            if job["status"] in ["completed", "failed", "cancelled"]:
                break

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
