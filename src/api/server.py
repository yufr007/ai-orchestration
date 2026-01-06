"""FastAPI server for orchestration jobs."""

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
    description="Elite multi-agent development team orchestration",
    version="0.1.0",
)


# In-memory job store (use database in production)
jobs: dict[str, dict[str, Any]] = {}


class JobRequest(BaseModel):
    """Request to create a new orchestration job."""
    
    repo: str = Field(..., description="Repository in format 'owner/name'")
    issue_number: int | None = Field(None, description="GitHub issue number")
    pr_number: int | None = Field(None, description="GitHub PR number")
    spec_content: str | None = Field(None, description="Specification content")
    mode: str = Field("autonomous", description="Execution mode: autonomous, plan, review")
    max_retries: int = Field(3, ge=0, le=10, description="Maximum retry attempts")


class JobResponse(BaseModel):
    """Response with job details."""
    
    job_id: str
    status: str
    repo: str
    mode: str
    created_at: datetime
    completed_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


async def run_orchestration(job_id: str, initial_state: OrchestrationState) -> None:
    """Run orchestration graph for a job."""
    try:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["started_at"] = datetime.now()
        
        # Create and run graph
        graph = create_orchestration_graph()
        
        config = {"configurable": {"thread_id": job_id}}
        
        final_state = None
        async for state in graph.astream(initial_state, config):
            # Update job with latest state
            jobs[job_id]["latest_state"] = state
            final_state = state
        
        # Job completed
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["completed_at"] = datetime.now()
        jobs[job_id]["result"] = final_state
    
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["completed_at"] = datetime.now()


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "name": "AI Orchestration Platform",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/api/v1/jobs", response_model=JobResponse)
async def create_job(
    request: JobRequest,
    background_tasks: BackgroundTasks,
) -> JobResponse:
    """Create a new orchestration job."""
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
        "initial_state": initial_state,
    }
    
    # Start orchestration in background
    background_tasks.add_task(run_orchestration, job_id, initial_state)
    
    return JobResponse(
        job_id=job_id,
        status="pending",
        repo=request.repo,
        mode=request.mode,
        created_at=jobs[job_id]["created_at"],
    )


@app.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    """Get job status and details."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    return JobResponse(
        job_id=job_id,
        status=job["status"],
        repo=job["repo"],
        mode=job["mode"],
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
        result=job.get("result"),
        error=job.get("error"),
    )


@app.get("/api/v1/jobs")
async def list_jobs() -> list[JobResponse]:
    """List all jobs."""
    return [
        JobResponse(
            job_id=job_id,
            status=job["status"],
            repo=job["repo"],
            mode=job["mode"],
            created_at=job["created_at"],
            completed_at=job.get("completed_at"),
            error=job.get("error"),
        )
        for job_id, job in jobs.items()
    ]


@app.get("/api/v1/jobs/{job_id}/stream")
async def stream_job_logs(job_id: str) -> StreamingResponse:
    """Stream job execution logs."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    async def generate_logs() -> Any:
        """Generate log stream."""
        while True:
            job = jobs[job_id]
            
            # Send status update
            yield f"data: {{\"status\": \"{job['status']}\", \"timestamp\": \"{datetime.now().isoformat()}\"}}}\n\n"
            
            # If job completed, send final state and close
            if job["status"] in ["completed", "failed"]:
                if job.get("result"):
                    import json
                    result_json = json.dumps(job["result"], default=str)
                    yield f"data: {{\"result\": {result_json}}}\n\n"
                break
            
            await asyncio.sleep(2)
    
    return StreamingResponse(generate_logs(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "src.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
    )
