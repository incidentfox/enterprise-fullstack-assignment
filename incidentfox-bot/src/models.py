"""Database models for IncidentFox."""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class DeploymentStatus(str, Enum):
    """Deployment status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisStatus(str, Enum):
    """Analysis status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class FailureCategory(str, Enum):
    """Failure category classification."""
    ENV_VAR_MISSING = "env_var_missing"
    PORT_MISMATCH = "port_mismatch"
    DEPENDENCY_ERROR = "dependency_error"
    BUILD_FAILURE = "build_failure"
    RUNTIME_CRASH = "runtime_crash"
    HEALTHCHECK_FAILURE = "healthcheck_failure"
    DATABASE_CONNECTION = "database_connection"
    UNKNOWN = "unknown"


class ActionType(str, Enum):
    """Action type enumeration."""
    ANALYZE = "analyze"
    SHOW_LOGS = "show_logs"
    APPLY_FIX = "apply_fix"
    RERUN = "rerun"


class PullRequest(Base):
    """Track GitHub pull requests."""
    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True)
    repo_owner = Column(String(255), nullable=False, index=True)
    repo_name = Column(String(255), nullable=False, index=True)
    pr_number = Column(Integer, nullable=False, index=True)
    branch_name = Column(String(255), nullable=False)
    head_sha = Column(String(40), nullable=False, index=True)

    # GitHub metadata
    author = Column(String(255), nullable=False)
    title = Column(Text, nullable=False)
    pr_url = Column(String(512), nullable=False)

    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    deployments = relationship("Deployment", back_populates="pull_request", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<PullRequest {self.repo_owner}/{self.repo_name}#{self.pr_number}>"


class Deployment(Base):
    """Track Coolify deployments."""
    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=False, index=True)

    # Coolify metadata
    coolify_deployment_id = Column(String(255), unique=True, index=True)
    coolify_application_id = Column(String(255), index=True)
    commit_sha = Column(String(40), nullable=False, index=True)

    # Status
    status = Column(SQLEnum(DeploymentStatus), default=DeploymentStatus.PENDING, nullable=False, index=True)

    # Logs and metadata
    deployment_url = Column(String(512))
    logs_url = Column(String(512))
    error_message = Column(Text)
    full_logs = Column(Text)

    # Timing
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)

    # Relationships
    pull_request = relationship("PullRequest", back_populates="deployments")
    analyses = relationship("Analysis", back_populates="deployment", cascade="all, delete-orphan")
    actions = relationship("Action", back_populates="deployment", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Deployment {self.coolify_deployment_id} status={self.status.value}>"


class Analysis(Base):
    """Track failure analyses."""
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id"), nullable=False, index=True)

    # Analysis metadata
    status = Column(SQLEnum(AnalysisStatus), default=AnalysisStatus.PENDING, nullable=False, index=True)
    failure_category = Column(SQLEnum(FailureCategory), index=True)

    # Results
    summary = Column(Text)
    root_cause = Column(Text)
    evidence = Column(JSON)  # Store log excerpts, patterns matched, etc.
    recommendations = Column(JSON)  # List of recommended fixes
    confidence_score = Column(Integer)  # 0-100

    # LLM details
    llm_provider = Column(String(50))  # "openai" or "anthropic"
    llm_model = Column(String(100))
    llm_prompt_tokens = Column(Integer)
    llm_completion_tokens = Column(Integer)
    llm_raw_response = Column(Text)

    # Deterministic detection
    patterns_matched = Column(JSON)  # List of regex patterns that matched

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)

    # Relationships
    deployment = relationship("Deployment", back_populates="analyses")

    def __repr__(self) -> str:
        return f"<Analysis {self.id} category={self.failure_category}>"


class Action(Base):
    """Track user actions (commands in PR comments)."""
    __tablename__ = "actions"

    id = Column(Integer, primary_key=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id"), nullable=False, index=True)

    # Action metadata
    action_type = Column(SQLEnum(ActionType), nullable=False, index=True)
    requested_by = Column(String(255), nullable=False)

    # Command details
    command_text = Column(Text, nullable=False)
    comment_id = Column(String(255))  # GitHub comment ID

    # Execution
    executed = Column(Boolean, default=False, nullable=False)
    success = Column(Boolean)
    result_message = Column(Text)

    # Patch details (for APPLY_FIX actions)
    files_modified = Column(JSON)  # List of files changed
    patch_content = Column(Text)
    commit_sha = Column(String(40))

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    executed_at = Column(DateTime)

    # Relationships
    deployment = relationship("Deployment", back_populates="actions")

    def __repr__(self) -> str:
        return f"<Action {self.action_type.value} by {self.requested_by}>"


class PRComment(Base):
    """Track PR comments posted by the bot (for idempotency)."""
    __tablename__ = "pr_comments"

    id = Column(Integer, primary_key=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=False, index=True)

    # GitHub comment metadata
    comment_id = Column(String(255), unique=True, nullable=False, index=True)
    comment_type = Column(String(50), nullable=False)  # "failure_analysis", "action_result", etc.

    # Content tracking (for updates)
    content_hash = Column(String(64))  # SHA256 of content for change detection

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<PRComment {self.comment_id} type={self.comment_type}>"
