"""FastAPI server for orchestration jobs."""

import asyncio
import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.config import get_settings
from src.core import create_orchestration_graph, OrchestrationState
from src.core.state import AgentRole

settings = get_settings()

# Initialize FastAPI
app = FastAPI(
    title="AI Orchestration Platform",
    description="Elite multi-agent orchestration for autonomous software development",
    version="0.1.0",
)

# In-memory job storage (use database in production)
jobs: dict[str, dict[str, Any]] = {}


class JobRequest(BaseModel):
    """Job creation request."""

    repo: str = Field(..., description="Repository name (owner/repo)")
    issue_number: int | None = Field(None, description="Issue number to implement")
    pr_number: int | None = Field(None, description="PR number to review")
    spec_content: str | None = Field(None, description="Specification content")
    mode: str = Field(default="autonomous", description="Execution mode: autonomous, plan, review")


class JobResponse(BaseModel):
    """Job status response."""

    job_id: str
    status: str
    repo: str
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    result: dict[str, Any] | None = None


async def run_orchestration_job(job_id: str, request: JobRequest) -> None:
    """Execute orchestration workflow in background."""
    try:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["logs"].append(f"[{datetime.now()}] Starting orchestration...")

        # Create workflow graph
        graph = create_orchestration_graph()

        # Prepare initial state
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
            "max_retries": 3,
            "started_at": datetime.now(),
            "completed_at": None,
            "error": None,
        }

        # Execute workflow
        jobs[job_id]["logs"].append(f"[{datetime.now()}] Executing workflow...")
        result = await graph.ainvoke(initial_state, {"configurable": {"thread_id": job_id}})

        # Store results
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["result"] = result
        jobs[job_id]["completed_at"] = datetime.now()
        jobs[job_id]["logs"].append(f"[{datetime.now()}] Workflow completed successfully")

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["completed_at"] = datetime.now()
        jobs[job_id]["logs"].append(f"[{datetime.now()}] ERROR: {e}")


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
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/api/v1/jobs", response_model=JobResponse)
async def create_job(request: JobRequest, background_tasks: BackgroundTasks) -> JobResponse:
    """Create and start a new orchestration job."""
    job_id = str(uuid.uuid4())

    # Initialize job
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "repo": request.repo,
        "created_at": datetime.now(),
        "completed_at": None,
        "error": None,
        "result": None,
        "logs": [],
    }

    # Start background task
    background_tasks.add_task(run_orchestration_job, job_id, request)

    return JobResponse(
        job_id=job_id,
        status="pending",
        repo=request.repo,
        created_at=jobs[job_id]["created_at"],
    )


@app.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    """Get job status and results."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    return JobResponse(
        job_id=job_id,
        status=job["status"],
        repo=job["repo"],
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
        error=job.get("error"),
        result=job.get("result"),
    )


@app.get("/api/v1/jobs")
async def list_jobs() -> dict[str, Any]:
    """List all jobs."""
    return {
        "total": len(jobs),
        "jobs": [
            {
                "job_id": job_id,
                "status": job["status"],
                "repo": job["repo"],
                "created_at": job["created_at"].isoformat(),
            }
            for job_id, job in jobs.items()
        ],
    }


@app.get("/api/v1/jobs/{job_id}/logs")
async def get_job_logs(job_id: str) -> dict[str, Any]:
    """Get job logs."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    return {"job_id": job_id, "logs": jobs[job_id]["logs"]}


@app.get("/api/v1/jobs/{job_id}/stream")
async def stream_job_logs(job_id: str) -> StreamingResponse:
    """Stream job logs in real-time."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def log_generator() -> Any:
        """Generate log stream."""
        last_index = 0
        while jobs[job_id]["status"] in ["pending", "running"]:
            current_logs = jobs[job_id]["logs"]
            if len(current_logs) > last_index:
                for log in current_logs[last_index:]:
                    yield f"data: {log}\n\n"
                last_index = len(current_logs)
            await asyncio.sleep(0.5)

        # Send final logs
        current_logs = jobs[job_id]["logs"]
        for log in current_logs[last_index:]:
            yield f"data: {log}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(log_generator(), media_type="text/event-stream")


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
