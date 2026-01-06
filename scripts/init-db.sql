-- PostgreSQL initialization script for AI Orchestration Platform
-- This runs automatically in Docker Compose

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- Orchestration runs table
CREATE TABLE IF NOT EXISTS orchestration_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo VARCHAR(255) NOT NULL,
    issue_number INTEGER,
    pr_number INTEGER,
    mode VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent executions table
CREATE TABLE IF NOT EXISTS agent_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL,
    agent_role VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    output TEXT,
    artifacts JSONB,
    metadata JSONB,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES orchestration_runs(id) ON DELETE CASCADE
);

-- Tasks table (decomposed from plans)
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL,
    task_number INTEGER NOT NULL,
    description TEXT NOT NULL,
    owner VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    dependencies INTEGER[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES orchestration_runs(id) ON DELETE CASCADE
);

-- Files changed tracking
CREATE TABLE IF NOT EXISTS file_changes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    change_type VARCHAR(20) NOT NULL,  -- created, updated, deleted
    branch VARCHAR(255),
    commit_sha VARCHAR(40),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES orchestration_runs(id) ON DELETE CASCADE
);

-- Test results tracking
CREATE TABLE IF NOT EXISTS test_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL,
    test_file VARCHAR(500) NOT NULL,
    test_name VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- passed, failed, skipped
    error TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES orchestration_runs(id) ON DELETE CASCADE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_runs_repo ON orchestration_runs(repo);
CREATE INDEX IF NOT EXISTS idx_runs_status ON orchestration_runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_created ON orchestration_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_executions_run ON agent_executions(run_id);
CREATE INDEX IF NOT EXISTS idx_executions_agent ON agent_executions(agent_role);
CREATE INDEX IF NOT EXISTS idx_tasks_run ON tasks(run_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_files_run ON file_changes(run_id);
CREATE INDEX IF NOT EXISTS idx_tests_run ON test_results(run_id);
CREATE INDEX IF NOT EXISTS idx_tests_status ON test_results(status);

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_orchestration_runs_updated_at
    BEFORE UPDATE ON orchestration_runs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert sample data (for testing)
INSERT INTO orchestration_runs (repo, mode, status, started_at) VALUES
    ('yufr007/vitaflow', 'autonomous', 'completed', NOW() - INTERVAL '1 day'),
    ('yufr007/autom8', 'plan', 'completed', NOW() - INTERVAL '2 hours')
ON CONFLICT DO NOTHING;
