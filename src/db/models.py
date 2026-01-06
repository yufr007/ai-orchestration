"""SQLAlchemy database models."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Job(Base):
    """Orchestration job record."""

    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True)
    repo = Column(String(255), nullable=False, index=True)
    issue_number = Column(Integer, nullable=True)
    pr_number = Column(Integer, nullable=True)
    spec_content = Column(Text, nullable=True)
    mode = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    result = Column(JSON, nullable=True)

    # Relationships
    executions = relationship("AgentExecution", back_populates="job", cascade="all, delete-orphan")


class AgentExecution(Base):
    """Agent execution record."""

    __tablename__ = "agent_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=False, index=True)
    agent_role = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    output = Column(Text, nullable=True)
    artifacts = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)

    # Relationships
    job = relationship("Job", back_populates="executions")
