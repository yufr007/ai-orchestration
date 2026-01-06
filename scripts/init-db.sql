-- Initialize database schema for PostgreSQL

CREATE TABLE IF NOT EXISTS jobs (
    id VARCHAR(36) PRIMARY KEY,
    repo VARCHAR(255) NOT NULL,
    issue_number INTEGER,
    pr_number INTEGER,
    spec_content TEXT,
    mode VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error TEXT,
    result JSONB
);

CREATE INDEX IF NOT EXISTS idx_jobs_repo ON jobs(repo);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC);

CREATE TABLE IF NOT EXISTS agent_executions (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(36) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    agent_role VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    output TEXT,
    artifacts JSONB,
    metadata JSONB,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_executions_job_id ON agent_executions(job_id);
CREATE INDEX IF NOT EXISTS idx_agent_executions_agent_role ON agent_executions(agent_role);
