"""FastAPI server for AI orchestration API."""

import asyncio
import uuid
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import structlog

from src.config import get_settings
from src.core.graph import create_orchestration_graph
from src.core.state import OrchestrationState

logger = structlog.get_logger()

app = FastAPI(
    title="AI Orchestration Platform",
    description="Elite multi-agent orchestration for autonomous software development",
    version="0.1.0",
)

# In-memory job storage (replace with database in production)
jobs: dict[str, dict[str, Any]] = {}


class JobRequest(BaseModel):
    """Request to create a new orchestration job."""

    repo: str = Field(..., description="GitHub repository (owner/repo)")
    issue_number: int | None = Field(None, description="Issue number to implement")
    pr_number: int | None = Field(None, description="PR number to review")
    spec_content: str | None = Field(None, description="Specification content")
    mode: str = Field("autonomous", description="Execution mode (autonomous|plan|review)")


class JobResponse(BaseModel):
    """Response with job details."""

    job_id: str
    status: str
    created_at: str
    repo: str
    mode: str


class JobStatus(BaseModel):
    """Detailed job status."""

    job_id: str
    status: str
    created_at: str
    started_at: str | None
    completed_at: str | None
    repo: str
    mode: str
    current_agent: str | None
    progress: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "AI Orchestration Platform",
        "version": "0.1.0",
        "status": "operational",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    settings = get_settings()
    return {
        "status": "healthy",
        "environment": settings.environment,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/v1/jobs", response_model=JobResponse)
async def create_job(request: JobRequest, background_tasks: BackgroundTasks):
    """Create a new orchestration job."""
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "started_at": None,
        "completed_at": None,
        "repo": request.repo,
        "issue_number": request.issue_number,
        "pr_number": request.pr_number,
        "spec_content": request.spec_content,
        "mode": request.mode,
        "current_agent": None,
        "progress": {},
        "result": None,
        "error": None,
    }

    jobs[job_id] = job
    logger.info("Job created", job_id=job_id, repo=request.repo)

    # Start job in background
    background_tasks.add_task(execute_job, job_id)

    return JobResponse(
        job_id=job_id,
        status=job["status"],
        created_at=job["created_at"],
        repo=job["repo"],
        mode=job["mode"],
    )


@app.get("/api/v1/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get job status."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    return JobStatus(**job)


@app.get("/api/v1/jobs")
async def list_jobs():
    """List all jobs."""
    return {"jobs": list(jobs.values())}


@app.get("/api/v1/jobs/{job_id}/stream")
async def stream_job_logs(job_id: str):
    """Stream job logs (SSE)."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        """Generate SSE events for job progress."""
        last_status = None
        while True:
            job = jobs.get(job_id)
            if not job:
                break

            current_status = job["status"]
            if current_status != last_status:
                yield f"data: {{'status': '{current_status}', 'agent': '{job.get('current_agent', 'none')}'}}\n\n"
                last_status = current_status

            if current_status in ["completed", "failed"]:
                break

            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def execute_job(job_id: str):
    """Execute orchestration job."""
    job = jobs[job_id]
    job["status"] = "running"
    job["started_at"] = datetime.utcnow().isoformat()

    logger.info("Job started", job_id=job_id)

    try:
        # Create orchestration graph
        graph = create_orchestration_graph()

        # Prepare initial state
        initial_state: OrchestrationState = {
            "repo": job["repo"],
            "issue_number": job["issue_number"],
            "pr_number": job["pr_number"],
            "spec_content": job["spec_content"],
            "mode": job["mode"],
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
            "started_at": datetime.utcnow(),
            "completed_at": None,
            "error": None,
        }

        # Execute graph with checkpointing
        config = {"configurable": {"thread_id": job_id}}
        final_state = None

        async for state in graph.astream(initial_state, config):
            # Update job progress
            if state:
                current_node = list(state.keys())[0] if state else None
                node_state = state.get(current_node, {})
                job["current_agent"] = node_state.get("current_agent")
                job["progress"] = {
                    "current_node": current_node,
                    "agent_results_count": len(node_state.get("agent_results", [])),
                }
                final_state = node_state

        # Job completed
        job["status"] = "completed"
        job["completed_at"] = datetime.utcnow().isoformat()
        job["result"] = {
            "plan": final_state.get("plan") if final_state else None,
            "prs_created": final_state.get("prs_created", []) if final_state else [],
            "test_results": final_state.get("test_results") if final_state else None,
            "approval_status": final_state.get("approval_status") if final_state else None,
        }

        logger.info("Job completed", job_id=job_id)

    except Exception as e:
        logger.error("Job failed", job_id=job_id, error=str(e))
        job["status"] = "failed"
        job["completed_at"] = datetime.utcnow().isoformat()
        job["error"] = str(e)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
