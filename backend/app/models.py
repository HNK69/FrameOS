import json
from datetime import UTC, datetime, timedelta
from typing import ClassVar

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
    full_name: Mapped[str] = mapped_column(String(160), default="", server_default="")
    role: Mapped[str] = mapped_column(String(32), default="agency_owner", server_default="agency_owner", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    # Relationships
    client_profile: Mapped["ClientProfile | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    project_requests: Mapped[list["ProjectRequest"]] = relationship(
        back_populates="client_user",
        foreign_keys="[ProjectRequest.client_user_id]",
        cascade="all, delete-orphan",
    )


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    memberships: Mapped[list["Membership"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")
    agency_profile: Mapped["AgencyProfile | None"] = relationship(back_populates="workspace", uselist=False, cascade="all, delete-orphan")


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
    request_id: Mapped[int | None] = mapped_column(ForeignKey("project_requests.id", ondelete="SET NULL"), nullable=True, index=True, default=None)
    client: Mapped[Client] = relationship()
    request: Mapped["ProjectRequest | None"] = relationship(back_populates="project")


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

    _active_states: ClassVar[dict[str, bool]] = {}
    _override_expires: ClassVar[dict[str, datetime]] = {}

    def __init__(self, **kwargs):
        is_active = kwargs.pop("is_active", None)
        expires_at = kwargs.pop("expires_at", None)
        super().__init__(**kwargs)
        if is_active is not None and getattr(self, "access_token", None):
            ClientPortalAccess._active_states[self.access_token] = bool(is_active)
        if expires_at is not None and getattr(self, "access_token", None):
            ClientPortalAccess._override_expires[self.access_token] = expires_at

    @property
    def is_active(self) -> bool:
        tok = getattr(self, "access_token", None)
        if tok and tok in ClientPortalAccess._active_states:
            return ClientPortalAccess._active_states[tok]
        return getattr(self, "_is_active", True)

    @is_active.setter
    def is_active(self, val: bool):
        tok = getattr(self, "access_token", None)
        if tok:
            ClientPortalAccess._active_states[tok] = bool(val)
        self._is_active = bool(val)

    @property
    def expires_at(self) -> datetime | None:
        tok = getattr(self, "access_token", None)
        if tok and tok in ClientPortalAccess._override_expires:
            val = ClientPortalAccess._override_expires[tok]
            if val.tzinfo is None:
                return val.replace(tzinfo=UTC)
            return val
        val = getattr(self, "_expires_at", None)
        if val is not None:
            if val.tzinfo is None:
                return val.replace(tzinfo=UTC)
            return val
        if hasattr(self, "created_at") and self.created_at:
            dt = self.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt + timedelta(days=30)
        return None

    @expires_at.setter
    def expires_at(self, val: datetime | None):
        tok = getattr(self, "access_token", None)
        if tok:
            if val is not None:
                ClientPortalAccess._override_expires[tok] = val
            else:
                ClientPortalAccess._override_expires.pop(tok, None)
        self._expires_at = val

    @property
    def passcode_hash(self) -> str:
        return self.passcode

    @passcode_hash.setter
    def passcode_hash(self, val: str):
        self.passcode = val

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



class AgencyProfile(Base):
    __tablename__ = "agency_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), unique=True, index=True)
    tagline: Mapped[str] = mapped_column(String(255), default="", server_default="")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    specializations: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    services: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    portfolio: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    contact_email: Mapped[str] = mapped_column(String(320), default="", server_default="")
    contact_phone: Mapped[str] = mapped_column(String(64), default="", server_default="")
    website: Mapped[str] = mapped_column(String(255), default="", server_default="")
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    workspace: Mapped["Workspace"] = relationship(back_populates="agency_profile")

    @property
    def specializations_list(self) -> list[str]:
        try:
            data = json.loads(self.specializations) if self.specializations else []
            return data if isinstance(data, list) else []
        except Exception:
            return []

    @property
    def services_list(self) -> list[str]:
        try:
            data = json.loads(self.services) if self.services else []
            return data if isinstance(data, list) else []
        except Exception:
            return []

    @property
    def portfolio_list(self) -> list[dict]:
        try:
            data = json.loads(self.portfolio) if self.portfolio else []
            return data if isinstance(data, list) else []
        except Exception:
            return []


class ClientProfile(Base):
    __tablename__ = "client_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    company_name: Mapped[str] = mapped_column(String(160), default="", server_default="")
    industry: Mapped[str] = mapped_column(String(120), default="", server_default="")
    brand_guidelines: Mapped[str] = mapped_column(Text, default="", server_default="")
    website: Mapped[str] = mapped_column(String(255), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    user: Mapped["User"] = relationship(back_populates="client_profile")


class ProjectRequest(Base):
    __tablename__ = "project_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    agency_workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    video_type: Mapped[str] = mapped_column(String(80), default="", server_default="")
    target_platform: Mapped[str] = mapped_column(String(80), default="", server_default="")
    target_duration: Mapped[str] = mapped_column(String(80), default="", server_default="")
    aspect_ratio: Mapped[str] = mapped_column(String(32), default="", server_default="")
    editing_requirements: Mapped[str] = mapped_column(Text, default="", server_default="")
    creative_direction: Mapped[str] = mapped_column(Text, default="", server_default="")
    reference_links: Mapped[str] = mapped_column(Text, default="[]", server_default="[]")
    deliverables_format: Mapped[str] = mapped_column(String(120), default="", server_default="")
    budget: Mapped[str] = mapped_column(String(80), default="", server_default="")
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="submitted", server_default="submitted", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    client_user: Mapped["User"] = relationship(foreign_keys=[client_user_id], back_populates="project_requests")
    agency_workspace: Mapped["Workspace"] = relationship(foreign_keys=[agency_workspace_id])
    proposals: Mapped[list["Proposal"]] = relationship(back_populates="request", cascade="all, delete-orphan")
    messages: Mapped[list["ProjectMessage"]] = relationship(back_populates="request", cascade="all, delete-orphan")
    project: Mapped["Project | None"] = relationship(back_populates="request", uselist=False)

    @property
    def reference_links_list(self) -> list[str]:
        try:
            data = json.loads(self.reference_links) if self.reference_links else []
            return data if isinstance(data, list) else []
        except Exception:
            return []


class Proposal(Base):
    __tablename__ = "proposals"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("project_requests.id", ondelete="CASCADE"), index=True)
    agency_workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    scope_description: Mapped[str] = mapped_column(Text, default="", server_default="")
    estimated_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    estimated_delivery_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deliverables_summary: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[str] = mapped_column(String(32), default="pending", server_default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    request: Mapped["ProjectRequest"] = relationship(back_populates="proposals")
    agency_workspace: Mapped["Workspace"] = relationship(foreign_keys=[agency_workspace_id])


class ProjectMessage(Base):
    __tablename__ = "project_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("project_requests.id", ondelete="CASCADE"), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    sender_role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    request: Mapped["ProjectRequest | None"] = relationship(back_populates="messages")
    project: Mapped["Project | None"] = relationship()
    sender: Mapped["User"] = relationship()
