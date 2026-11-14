from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
    status: str = Field(default="active", pattern="^(active|completed|archived)$")
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


class ExtractionResult(BaseModel):
    requests: list[ExtractionItem] = []
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
