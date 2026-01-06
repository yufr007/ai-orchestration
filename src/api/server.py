"""FastAPI server for orchestration platform."""

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


app = FastAPI(
    title="AI Orchestration Platform",
    description="Elite multi-agent orchestration for autonomous software development",
    version="0.1.0",
)


# In-memory job store (in production, use database)
jobs: dict[str, dict[str, Any]] = {}


class JobRequest(BaseModel):
    """Request to create an orchestration job."""

    repo: str = Field(..., description="Repository in format 'owner/repo'")
    issue_number: int | None = Field(None, description="GitHub issue number")
    pr_number: int | None = Field(None, description="GitHub PR number")
    spec_content: str | None = Field(None, description="Specification content")
    mode: str = Field(default="autonomous", description="Mode: autonomous, plan, or review")
    max_retries: int = Field(default=3, description="Maximum retry attempts")


class JobResponse(BaseModel):
    """Response for job operations."""

    job_id: str
    status: str
    repo: str
    mode: str
    created_at: datetime
    updated_at: datetime
    result: dict[str, Any] | None = None
    error: str | None = None


async def run_orchestration(job_id: str, initial_state: OrchestrationState) -> None:
    """Run orchestration workflow in background."""
    try:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["updated_at"] = datetime.now()

        # Create and run graph
        graph = create_orchestration_graph()
        config = {"configurable": {"thread_id": job_id}}

        # Stream execution
        async for event in graph.astream(initial_state, config):
            # Store latest state in job
            jobs[job_id]["state"] = event
            jobs[job_id]["updated_at"] = datetime.now()

        # Mark as completed
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = event
        jobs[job_id]["updated_at"] = datetime.now()

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["updated_at"] = datetime.now()


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": "AI Orchestration Platform",
        "version": "0.1.0",
        "status": "operational",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    settings = get_settings()
    return {
        "status": "healthy",
        "environment": settings.environment,
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/v1/jobs", response_model=JobResponse)
async def create_job(request: JobRequest, background_tasks: BackgroundTasks) -> JobResponse:
    """Create and start an orchestration job."""
    job_id = str(uuid.uuid4())

    # Create initial state
    initial_state: OrchestrationState = {
        "repo": request.repo,
        "issue_number": request.issue_number,
        "pr_number": request.pr_number,
        "spec_content": request.spec_content,
        "mode": request.mode,
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
        "max_retries": request.max_retries,
        "started_at": datetime.now(),
        "completed_at": None,
        "error": None,
    }

    # Store job
    jobs[job_id] = {
        "id": job_id,
        "status": "pending",
        "repo": request.repo,
        "mode": request.mode,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "state": initial_state,
        "result": None,
        "error": None,
    }

    # Start orchestration in background
    background_tasks.add_task(run_orchestration, job_id, initial_state)

    return JobResponse(
        job_id=job_id,
        status="pending",
        repo=request.repo,
        mode=request.mode,
        created_at=jobs[job_id]["created_at"],
        updated_at=jobs[job_id]["updated_at"],
    )


@app.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    """Get job status and results."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    return JobResponse(
        job_id=job["id"],
        status=job["status"],
        repo=job["repo"],
        mode=job["mode"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        result=job.get("result"),
        error=job.get("error"),
    )


@app.get("/api/v1/jobs")
async def list_jobs() -> list[JobResponse]:
    """List all jobs."""
    return [
        JobResponse(
            job_id=job["id"],
            status=job["status"],
            repo=job["repo"],
            mode=job["mode"],
            created_at=job["created_at"],
            updated_at=job["updated_at"],
            result=job.get("result"),
            error=job.get("error"),
        )
        for job in jobs.values()
    ]


@app.get("/api/v1/jobs/{job_id}/stream")
async def stream_job_logs(job_id: str) -> StreamingResponse:
    """Stream job execution logs in real-time."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator() -> Any:
        """Generate SSE events for job updates."""
        last_update = jobs[job_id]["updated_at"]

        while jobs[job_id]["status"] in ["pending", "running"]:
            current_update = jobs[job_id]["updated_at"]

            if current_update > last_update:
                state = jobs[job_id].get("state", {})
                current_agent = state.get("current_agent")

                yield f"data: {{\"agent\": \"{current_agent}\", \"status\": \"{jobs[job_id]['status']}\"}}\n\n"
                last_update = current_update

            await asyncio.sleep(1)

        # Send final status
        yield f"data: {{\"status\": \"{jobs[job_id]['status']}\", \"completed\": true}}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.delete("/api/v1/jobs/{job_id}")
async def delete_job(job_id: str) -> dict[str, str]:
    """Delete a job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    del jobs[job_id]
    return {"message": "Job deleted", "job_id": job_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
