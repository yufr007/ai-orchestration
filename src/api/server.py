"""FastAPI application with REST endpoints."""

import asyncio
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import structlog

from src.api.models import JobCreate, JobResponse, JobStatus
from src.config import get_settings
from src.core.graph import create_orchestration_graph
from src.core.state import OrchestrationState

logger = structlog.get_logger()

app = FastAPI(
    title="AI Orchestration Platform",
    description="Elite multi-agent orchestration for autonomous software development",
    version="0.1.0",
)

# In-memory job storage (use database in production)
jobs: dict[str, dict[str, Any]] = {}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": "AI Orchestration Platform API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/api/v1/jobs", response_model=JobResponse)
async def create_job(
    job: JobCreate,
    background_tasks: BackgroundTasks,
) -> JobResponse:
    """Create and start a new orchestration job."""
    job_id = str(uuid4())

    # Initialize job state
    jobs[job_id] = {
        "id": job_id,
        "status": JobStatus.PENDING,
        "repo": job.repo,
        "issue_number": job.issue_number,
        "pr_number": job.pr_number,
        "spec_content": job.spec_content,
        "mode": job.mode,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "result": None,
        "error": None,
        "logs": [],
    }

    # Start job in background
    background_tasks.add_task(run_job, job_id, job)

    logger.info("Job created", job_id=job_id, repo=job.repo)

    return JobResponse(
        id=job_id,
        status=JobStatus.PENDING,
        repo=job.repo,
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
        id=job_id,
        status=job["status"],
        repo=job["repo"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        result=job.get("result"),
        error=job.get("error"),
    )


@app.get("/api/v1/jobs/{job_id}/stream")
async def stream_job_logs(job_id: str) -> StreamingResponse:
    """Stream job logs in real-time."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def generate_logs() -> Any:
        last_index = 0
        while True:
            job = jobs.get(job_id)
            if not job:
                break

            logs = job.get("logs", [])
            new_logs = logs[last_index:]

            for log in new_logs:
                yield f"data: {log}\n\n"

            last_index = len(logs)

            # Check if job is complete
            if job["status"] in [JobStatus.COMPLETED, JobStatus.FAILED]:
                break

            await asyncio.sleep(1)

    return StreamingResponse(generate_logs(), media_type="text/event-stream")


@app.get("/api/v1/jobs")
async def list_jobs(
    status: JobStatus | None = None,
    limit: int = 10,
) -> list[JobResponse]:
    """List all jobs with optional status filter."""
    filtered_jobs = jobs.values()

    if status:
        filtered_jobs = [j for j in filtered_jobs if j["status"] == status]

    # Sort by created_at descending
    sorted_jobs = sorted(filtered_jobs, key=lambda x: x["created_at"], reverse=True)

    return [
        JobResponse(
            id=job["id"],
            status=job["status"],
            repo=job["repo"],
            created_at=job["created_at"],
            updated_at=job["updated_at"],
            result=job.get("result"),
            error=job.get("error"),
        )
        for job in sorted_jobs[:limit]
    ]


async def run_job(job_id: str, job_input: JobCreate) -> None:
    """Execute orchestration workflow for a job."""
    try:
        jobs[job_id]["status"] = JobStatus.RUNNING
        jobs[job_id]["updated_at"] = datetime.now()
        jobs[job_id]["logs"].append(f"Starting job {job_id}")

        # Create initial state
        initial_state: OrchestrationState = {
            "repo": job_input.repo,
            "issue_number": job_input.issue_number,
            "pr_number": job_input.pr_number,
            "spec_content": job_input.spec_content,
            "mode": job_input.mode,
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

        # Execute workflow
        config = {"configurable": {"thread_id": job_id}}
        final_state = await graph.ainvoke(initial_state, config)

        # Update job with results
        jobs[job_id]["status"] = JobStatus.COMPLETED
        jobs[job_id]["result"] = {
            "plan": final_state.get("plan"),
            "files_changed": final_state.get("files_changed", []),
            "prs_created": final_state.get("prs_created", []),
            "test_results": final_state.get("test_results"),
            "approval_status": final_state.get("approval_status"),
            "agent_results": [
                {
                    "agent": r["agent"],
                    "status": r["status"],
                    "timestamp": r["timestamp"].isoformat(),
                }
                for r in final_state.get("agent_results", [])
            ],
        }
        jobs[job_id]["logs"].append(f"Job {job_id} completed successfully")

    except Exception as e:
        logger.error("Job failed", job_id=job_id, error=str(e))
        jobs[job_id]["status"] = JobStatus.FAILED
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["logs"].append(f"Job {job_id} failed: {str(e)}")

    finally:
        jobs[job_id]["updated_at"] = datetime.now()
