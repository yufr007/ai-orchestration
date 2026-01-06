-- PostgreSQL initialization script for AI Orchestration Platform

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Jobs table
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo VARCHAR(255) NOT NULL,
    issue_number INTEGER,
    pr_number INTEGER,
    spec_content TEXT,
    mode VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    result_json JSONB,
    error TEXT,
    created_by VARCHAR(255)
);

CREATE INDEX idx_jobs_repo ON jobs(repo);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);

-- Checkpoints table for LangGraph persistence
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id VARCHAR(255) NOT NULL,
    checkpoint_id VARCHAR(255) NOT NULL,
    parent_id VARCHAR(255),
    checkpoint BYTEA NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_id)
);

CREATE INDEX idx_checkpoints_thread ON checkpoints(thread_id);

-- Agent executions table
CREATE TABLE IF NOT EXISTS agent_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    agent_role VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    output TEXT,
    artifacts JSONB,
    metadata JSONB,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_seconds FLOAT
);

CREATE INDEX idx_agent_executions_job ON agent_executions(job_id);
CREATE INDEX idx_agent_executions_agent ON agent_executions(agent_role);

-- API usage tracking
CREATE TABLE IF NOT EXISTS api_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,  -- perplexity, anthropic, openai, github
    operation VARCHAR(100) NOT NULL,
    tokens_used INTEGER,
    cost_usd DECIMAL(10, 4),
    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_usage_job ON api_usage(job_id);
CREATE INDEX idx_api_usage_provider ON api_usage(provider);
CREATE INDEX idx_api_usage_timestamp ON api_usage(timestamp DESC);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    actor VARCHAR(255),
    details JSONB,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_log_action ON audit_log(action);

-- Functions
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER jobs_updated_at
BEFORE UPDATE ON jobs
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();

-- Views
CREATE OR REPLACE VIEW job_statistics AS
SELECT
    repo,
    mode,
    status,
    COUNT(*) as count,
    AVG(EXTRACT(EPOCH FROM (completed_at - created_at))) as avg_duration_seconds,
    MAX(created_at) as last_run
FROM jobs
GROUP BY repo, mode, status;

CREATE OR REPLACE VIEW api_cost_summary AS
SELECT
    DATE(timestamp) as date,
    provider,
    SUM(tokens_used) as total_tokens,
    SUM(cost_usd) as total_cost_usd
FROM api_usage
GROUP BY DATE(timestamp), provider
ORDER BY date DESC, provider;
