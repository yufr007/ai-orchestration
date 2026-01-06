-- PostgreSQL initialization script
-- Used by docker-compose for initial database setup

-- Orchestration jobs table
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    repo TEXT NOT NULL,
    issue_number INTEGER,
    pr_number INTEGER,
    spec_content TEXT,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    error TEXT,
    result JSONB
);

-- Agent execution results
CREATE TABLE IF NOT EXISTS agent_results (
    id SERIAL PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    agent TEXT NOT NULL,
    status TEXT NOT NULL,
    output TEXT,
    artifacts JSONB,
    metadata JSONB,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Workflow checkpoints (used by LangGraph)
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    checkpoint BYTEA NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_jobs_repo ON jobs(repo);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_results_job ON agent_results(job_id);
CREATE INDEX IF NOT EXISTS idx_agent_results_agent ON agent_results(agent);
CREATE INDEX IF NOT EXISTS idx_checkpoints_thread ON checkpoints(thread_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_created ON checkpoints(created_at DESC);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO orchestration;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO orchestration;
