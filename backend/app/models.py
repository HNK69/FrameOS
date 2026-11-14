from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now_utc() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    memberships: Mapped[list["Membership"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="owner")
    workspace: Mapped[Workspace] = relationship(back_populates="memberships")


class Client(Base):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    brand: Mapped[str] = mapped_column(String(160), default="")
    industry: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    memory_bank_id: Mapped[str] = mapped_column(String(120), unique=True)
    memory_status: Mapped[str] = mapped_column(String(24), default="unavailable")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="active")
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    client: Mapped[Client] = relationship()


class Transcript(Base):
    __tablename__ = "transcripts"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ProcessingRun(Base):
    __tablename__ = "processing_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    transcript_id: Mapped[int] = mapped_column(ForeignKey("transcripts.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(24), default="queued")
    stage: Mapped[str] = mapped_column(String(40), default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    error: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExtractedItem(Base):
    __tablename__ = "extracted_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("processing_runs.id", ondelete="CASCADE"), index=True)
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(48))
    source_quote: Mapped[str] = mapped_column(Text, default="")
    classification: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(48), default="unknown")
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ProductionTask(Base):
    __tablename__ = "production_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("processing_runs.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(48))
    instruction: Mapped[str] = mapped_column(Text)
    resolve_workflow: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    source: Mapped[str] = mapped_column(String(40))
    evidence: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("production_tasks.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(24))
    original_recommendation: Mapped[str] = mapped_column(Text)
    correction: Mapped[str] = mapped_column(Text, default="")
    client_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_status: Mapped[str] = mapped_column(String(24), default="not_requested")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ClientFeedback(Base):
    """Portal submission and its review/processing provenance; separate from task feedback."""
    __tablename__ = "client_feedback"
    __table_args__ = (UniqueConstraint("workspace_id", "idempotency_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    source_type: Mapped[str] = mapped_column(String(16))
    original_text: Mapped[str] = mapped_column(Text, default="")
    audio_path: Mapped[str] = mapped_column(String(600), default="")
    audio_filename: Mapped[str] = mapped_column(String(255), default="")
    audio_content_type: Mapped[str] = mapped_column(String(120), default="")
    transcript: Mapped[str] = mapped_column(Text, default="")
    transcript_provider: Mapped[str] = mapped_column(String(80), default="")
    transcript_model: Mapped[str] = mapped_column(String(120), default="")
    transcript_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extracted_json: Mapped[str] = mapped_column(Text, default="{}")
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(40), default="queued")
    error: Mapped[str] = mapped_column(Text, default="")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    client_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class MemoryOperation(Base):
    __tablename__ = "memory_operations"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("processing_runs.id", ondelete="CASCADE"), nullable=True)
    operation: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24))
    idempotency_key: Mapped[str] = mapped_column(String(120), index=True)
    provenance: Mapped[str] = mapped_column(String(32), default="")
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ClientPortalAccess(Base):
    __tablename__ = "client_portal_access"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True, unique=True)
    access_token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    passcode: Mapped[str] = mapped_column(String(64), index=True)
    client_email: Mapped[str] = mapped_column(String(320), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    client: Mapped[Client] = relationship()


class ReviewVersion(Base):
    __tablename__ = "review_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    version_label: Mapped[str] = mapped_column(String(32), default="v1")
    video_asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    video_url: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(32), default="in_review")
    change_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class VideoComment(Base):
    __tablename__ = "video_comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    review_version_id: Mapped[int | None] = mapped_column(ForeignKey("review_versions.id", ondelete="SET NULL"), nullable=True)
    timestamp_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    timecode: Mapped[str] = mapped_column(String(16), default="00:00")
    author_name: Mapped[str] = mapped_column(String(120), default="Client")
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="submitted")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ClientFeedbackSubmission(Base):
    __tablename__ = "client_feedback_submissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    review_version_id: Mapped[int | None] = mapped_column(ForeignKey("review_versions.id", ondelete="SET NULL"), nullable=True)
    feedback_type: Mapped[str] = mapped_column(String(32))
    author_name: Mapped[str] = mapped_column(String(160), default="Client")
    content: Mapped[str] = mapped_column(Text)
    structured_data: Mapped[str] = mapped_column(Text, default="{}")
    audio_asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="submitted")
    review_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
