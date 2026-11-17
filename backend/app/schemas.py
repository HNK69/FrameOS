from datetime import datetime
from typing import Any

import email_validator
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class InputModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class SetupInput(InputModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    workspace_name: str = Field(min_length=2, max_length=160)


class LoginInput(InputModel):
    email: EmailStr
    password: str


class ClientInput(InputModel):
    name: str = Field(min_length=1, max_length=160)
    brand: str = Field(default="", max_length=160)
    industry: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=5000)


class ProjectInput(InputModel):
    client_id: int
    name: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=5000)
    status: str = Field(default="active", pattern="^(active|in_review|completed|archived)$")
    due_date: datetime | None = None


class ProcessInput(InputModel):
    project_id: int
    transcript: str = Field(min_length=10, max_length=100_000)


class FeedbackInput(InputModel):
    action: str = Field(pattern="^(accept|correct|reject|in_progress|completed|blocked)$")
    correction: str = Field(default="", max_length=5000)
    client_confirmed: bool = False
    knowledge_type: str = Field(default="editor_correction", pattern="^(editor_correction|client_confirmed|reusable_client_knowledge|project_specific)$")
    priority: str | None = Field(default=None, pattern="^(low|medium|high|urgent)$")


class TaskUpdateInput(InputModel):
    status: str | None = Field(default=None, pattern="^(pending|in_progress|completed|blocked|accepted|rejected)$")
    priority: str | None = Field(default=None, pattern="^(low|medium|high|urgent)$")
    instruction: str | None = Field(default=None, max_length=5000)
    title: str | None = Field(default=None, max_length=200)
    resolve_workflow: str | None = Field(default=None, max_length=5000)
    correction_note: str | None = Field(default=None, max_length=5000)
    knowledge_type: str = Field(default="editor_correction", pattern="^(editor_correction|client_confirmed|reusable_client_knowledge|project_specific)$")
    client_confirmed: bool = False


class AdaptiveKnowledgeInput(InputModel):
    content: str = Field(min_length=5, max_length=12000)
    knowledge_type: str = Field(default="reusable_client_knowledge", pattern="^(reusable_client_knowledge|client_confirmed|project_specific|editor_correction)$")
    project_id: int | None = None
    category: str = Field(default="general", max_length=48)
    client_confirmed: bool = False


class RetainInput(InputModel):
    client_id: int
    content: str = Field(min_length=8, max_length=12_000)
    project_id: int | None = None
    provenance: str = Field(pattern="^(client_confirmed|editor_interpretation|ai_inference)$")
    client_confirmed: bool = False


class AssetRequirement(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    category: str = Field(default="unknown", max_length=48)


class ExtractionItem(BaseModel):
    description: str
    category: str
    source_quote: str = ""
    classification: str = Field(pattern="^(explicit|inferred)$")
    confidence: float = Field(ge=0, le=1)
    requires_confirmation: bool
    kind: str = Field(
        default="request",
        pattern="^(request|revision|style_preference|constraint|duration|clarification)$",
    )
    memory_class: str = Field(
        default="project_specific",
        pattern="^(project_specific|temporary_revision|reusable_preference|confirmed_preference|editor_correction)$",
    )


class ExtractionResult(BaseModel):
    requests: list[ExtractionItem] = []
    summary: str = Field(default="", max_length=4000)
    questions: list[str] = []
    ambiguities: list[str] = []
    missing_information: list[str] = []
    production_risks: list[str] = []
    required_assets: list[AssetRequirement] = []


class TaskDraft(BaseModel):
    title: str
    category: str
    instruction: str
    resolve_workflow: str
    priority: str = Field(pattern="^(low|medium|high|urgent)$")
    source: str
    evidence: str = ""
    confidence: float = Field(ge=0, le=1)
    requires_confirmation: bool


class SynthesisResult(BaseModel):
    tasks: list[TaskDraft]


class PortalLoginInput(InputModel):
    token: str | None = None
    code: str | None = None
    email: EmailStr | None = None


class PortalDraftInput(InputModel):
    feedback_type: str = Field(default="text", pattern="^(brief|text|voice|review_notes)$")
    content: str = Field(min_length=3, max_length=100_000)


class PortalFeedbackItem(BaseModel):
    id: str | None = None
    description: str = Field(min_length=1, max_length=2000)
    category: str = Field(default="General", max_length=64)
    classification: str = Field(default="explicit", pattern="^(explicit|inferred)$")
    confidence: float = Field(default=1.0, ge=0, le=1)
    requires_confirmation: bool = False
    client_confirmed: bool = False
    actionable_cut_note: str = ""


class PortalFeedbackDraftResult(BaseModel):
    summary: str = ""
    requests: list[PortalFeedbackItem] = []
    ambiguities: list[str] = []
    missing_information: list[str] = []
    production_risks: list[str] = []


class PortalFeedbackSubmitInput(InputModel):
    feedback_type: str = Field(pattern="^(brief|text|voice|review_decision)$")
    content: str = Field(default="", max_length=100_000)
    version_id: int | None = None
    items: list[PortalFeedbackItem] = []
    audio_asset_id: int | None = None
    author_name: str = Field(default="Client", max_length=160)


class PortalDecisionInput(InputModel):
    decision: str = Field(pattern="^(approve|changes_requested|reject)$")
    version_id: int | None = None
    notes: str = Field(default="", max_length=10_000)
    author_name: str = Field(default="Client", max_length=160)


class PortalCommentInput(InputModel):
    timestamp_seconds: float = Field(ge=0)
    timecode: str = Field(min_length=1, max_length=16)
    content: str = Field(min_length=1, max_length=5000)
    version_id: int | None = None
    author_name: str = Field(default="Client", max_length=120)


# =============================================================================
# Two-Sided Platform Schemas (Auth, Profiles, Requests, Proposals, Messages)
# =============================================================================

class ClientRegisterInput(InputModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=160)
    company_name: str = Field(default="", max_length=160)


class AgencyRegisterInput(InputModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=160)
    agency_name: str = Field(min_length=2, max_length=160)


class AuthResponse(BaseModel):
    user_id: int
    id: int | None = None
    email: str
    role: str
    full_name: str = ""
    company_name: str | None = None
    workspace_id: int | None = None
    workspace: dict | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            self.id = self.user_id


class UserResponse(BaseModel):
    id: int
    user_id: int | None = None
    email: str
    full_name: str = ""
    role: str
    company_name: str | None = None
    workspace_id: int | None = None
    workspace_name: str | None = None
    workspace: dict | None = None
    client_profile: Any = None
    agency_profile: Any = None
    created_at: datetime | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.user_id is None:
            self.user_id = self.id


class PortfolioItem(BaseModel):
    title: str = Field(default="", max_length=200)
    video_url: str = Field(default="", max_length=500)
    thumbnail_url: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=2000)


class AgencyProfileUpdateInput(InputModel):
    tagline: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    specializations: list[str] | None = None
    services: list[str] | None = None
    portfolio: list[PortfolioItem] | None = None
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=64)
    website: str | None = Field(default=None, max_length=255)

    @field_validator("contact_email", mode="before")
    @classmethod
    def validate_contact_email(cls, v: Any) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return ""
            try:
                email_validator.validate_email(s, check_deliverability=False, test_environment=True)
            except Exception as e:
                raise ValueError(f"Invalid email format: {e}") from e
            return s
        raise ValueError("Invalid email format")


AgencyProfileUpdate = AgencyProfileUpdateInput


class AgencyProfileResponse(BaseModel):
    id: int
    workspace_id: int
    workspace_name: str = ""
    tagline: str = ""
    description: str = ""
    specializations: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    portfolio: list[PortfolioItem] = Field(default_factory=list)
    contact_email: str = ""
    contact_phone: str = ""
    website: str = ""
    is_published: bool = False
    published_at: datetime | None = None
    can_publish: bool = False
    is_ready_to_publish: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    missing_publish_fields: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PublishStatusResponse(BaseModel):
    workspace_id: int
    is_published: bool
    published_at: datetime | None = None
    can_publish: bool = True
    is_ready_to_publish: bool = True
    missing_fields: list[str] = Field(default_factory=list)
    missing_publish_fields: list[str] = Field(default_factory=list)
    message: str = ""


class AgencyDiscoveryItem(BaseModel):
    workspace_id: int
    name: str
    tagline: str = ""
    description: str = ""
    specializations: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    portfolio: list[PortfolioItem] = Field(default_factory=list)
    contact_email: str = ""
    website: str = ""
    is_published: bool = True
    published_at: datetime | None = None


class AgencyDiscoveryDetail(BaseModel):
    workspace_id: int
    name: str
    tagline: str = ""
    description: str = ""
    specializations: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    portfolio: list[PortfolioItem] = Field(default_factory=list)
    contact_email: str = ""
    contact_phone: str = ""
    website: str = ""
    is_published: bool = True
    published_at: datetime | None = None
    created_at: datetime | None = None


class ClientProfileUpdateInput(InputModel):
    company_name: str = Field(default="", max_length=160)
    industry: str = Field(default="", max_length=120)
    brand_guidelines: str = Field(default="", max_length=10000)
    website: str = Field(default="", max_length=255)


class ClientProfileResponse(BaseModel):
    id: int
    user_id: int
    company_name: str = ""
    industry: str = ""
    brand_guidelines: str = ""
    website: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectRequestCreateInput(InputModel):
    agency_workspace_id: int
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    video_type: str = Field(default="", max_length=80)
    target_platform: str = Field(default="", max_length=80)
    target_duration: str = Field(default="", max_length=80)
    aspect_ratio: str = Field(default="", max_length=32)
    editing_requirements: str = Field(default="", max_length=10000)
    creative_direction: str = Field(default="", max_length=10000)
    reference_links: list[str] = Field(default_factory=list)
    deliverables_format: str = Field(default="", max_length=120)
    budget: str = Field(default="", max_length=80)
    deadline: datetime | None = None
    status: str = Field(default="submitted", pattern="^(draft|submitted)$")


class ProjectRequestUpdateInput(InputModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    video_type: str | None = None
    target_platform: str | None = None
    target_duration: str | None = None
    aspect_ratio: str | None = None
    editing_requirements: str | None = None
    creative_direction: str | None = None
    reference_links: list[str] | None = None
    deliverables_format: str | None = None
    budget: str | None = None
    deadline: datetime | None = None
    status: str | None = Field(default=None, pattern="^(draft|submitted|under_review|proposal_received|accepted|declined|cancelled)$")


class ProjectRequestResponse(BaseModel):
    id: int
    client_user_id: int
    agency_workspace_id: int
    agency_name: str = ""
    client_name: str = ""
    title: str
    description: str = ""
    video_type: str = ""
    target_platform: str = ""
    target_duration: str = ""
    aspect_ratio: str = ""
    editing_requirements: str = ""
    creative_direction: str = ""
    reference_links: list[str] = Field(default_factory=list)
    deliverables_format: str = ""
    budget: str = ""
    deadline: datetime | None = None
    status: str
    project_id: int | None = None
    proposals_count: int = 0
    created_at: datetime
    updated_at: datetime


class ProposalCreateInput(InputModel):
    scope_description: str = Field(min_length=1, max_length=10000)
    estimated_days: int = Field(ge=1, le=365)
    estimated_delivery_date: datetime | None = None
    deliverables_summary: str = Field(default="", max_length=5000)


class ProposalUpdateInput(InputModel):
    scope_description: str | None = None
    estimated_days: int | None = Field(default=None, ge=1, le=365)
    estimated_delivery_date: datetime | None = None
    deliverables_summary: str | None = None
    status: str | None = Field(default=None, pattern="^(pending|accepted|declined)$")


class ProposalResponse(BaseModel):
    id: int
    request_id: int
    agency_workspace_id: int
    scope_description: str
    estimated_days: int
    estimated_delivery_date: datetime | None = None
    deliverables_summary: str = ""
    status: str
    created_at: datetime
    updated_at: datetime


class ProposalActionResponse(BaseModel):
    proposal_id: int
    request_id: int
    status: str
    project_id: int | None = None


class ProjectMessageCreateInput(InputModel):
    request_id: int | None = None
    project_id: int | None = None
    content: str = Field(min_length=1, max_length=10000)


class ProjectMessageResponse(BaseModel):
    id: int
    request_id: int | None = None
    project_id: int | None = None
    sender_id: int
    sender_name: str = ""
    sender_role: str
    content: str
    created_at: datetime
