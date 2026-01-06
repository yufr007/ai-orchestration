-- PostgreSQL initialization script
-- This runs when the database container starts

-- Jobs table
CREATE TABLE IF NOT EXISTS jobs (
    id VARCHAR(36) PRIMARY KEY,
    repo VARCHAR(255) NOT NULL,
    issue_number INTEGER,
    pr_number INTEGER,
    mode VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error TEXT,
    INDEX idx_repo (repo),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
);

-- Agent results table
CREATE TABLE IF NOT EXISTS agent_results (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(36) NOT NULL,
    agent VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    output TEXT,
    artifacts JSONB,
    metadata JSONB,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    INDEX idx_job_id (job_id),
    INDEX idx_agent (agent),
    INDEX idx_timestamp (timestamp)
);

-- Checkpoints table (for LangGraph persistence)
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id VARCHAR(255) NOT NULL,
    checkpoint_id VARCHAR(255) NOT NULL,
    parent_id VARCHAR(255),
    checkpoint BYTEA NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (thread_id, checkpoint_id),
    INDEX idx_thread_id (thread_id),
    INDEX idx_parent_id (parent_id)
);

-- Metrics table (for observability)
CREATE TABLE IF NOT EXISTS metrics (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(36),
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC,
    labels JSONB,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_job_id (job_id),
    INDEX idx_metric_name (metric_name),
    INDEX idx_timestamp (timestamp)
);

-- Create views for analytics
CREATE OR REPLACE VIEW job_statistics AS
SELECT 
    status,
    COUNT(*) as count,
    AVG(EXTRACT(EPOCH FROM (completed_at - created_at))) as avg_duration_seconds
FROM jobs
WHERE completed_at IS NOT NULL
GROUP BY status;

CREATE OR REPLACE VIEW agent_performance AS
SELECT 
    agent,
    status,
    COUNT(*) as executions,
    AVG(LENGTH(output)) as avg_output_length
FROM agent_results
GROUP BY agent, status;
