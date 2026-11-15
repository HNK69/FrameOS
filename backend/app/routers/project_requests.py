"""Project Requests & Proposals Router — M4: Client Briefs, Agency Proposals, Acceptance Flow."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    AgencyProfile,
    Client,
    Membership,
    Project,
    ProjectMessage,
    ProjectRequest,
    Proposal,
    User,
    Workspace,
    now_utc,
)
from ..schemas import (
    ProjectMessageCreateInput,
    ProjectMessageResponse,
    ProjectRequestCreateInput,
    ProjectRequestResponse,
    ProjectRequestUpdateInput,
    ProposalActionResponse,
    ProposalCreateInput,
    ProposalResponse,
    ProposalUpdateInput,
)
from ..security import (
    get_current_user,
    require_agency_role,
    require_client_role,
)

router = APIRouter(tags=["project_requests"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _request_response(req: ProjectRequest, db: Session) -> ProjectRequestResponse:
    agency_ws = db.get(Workspace, req.agency_workspace_id)
    agency_name = agency_ws.name if agency_ws else ""
    client_user = db.get(User, req.client_user_id)
    client_name = client_user.full_name if client_user else ""
    proposals_count = db.query(Proposal).filter_by(request_id=req.id).count()
    project = db.scalar(select(Project).where(Project.request_id == req.id))
    return ProjectRequestResponse(
        id=req.id,
        client_user_id=req.client_user_id,
        agency_workspace_id=req.agency_workspace_id,
        agency_name=agency_name,
        client_name=client_name,
        title=req.title,
        description=req.description,
        video_type=req.video_type,
        target_platform=req.target_platform,
        target_duration=req.target_duration,
        aspect_ratio=req.aspect_ratio,
        editing_requirements=req.editing_requirements,
        creative_direction=req.creative_direction,
        reference_links=req.reference_links_list,
        deliverables_format=req.deliverables_format,
        budget=req.budget,
        deadline=req.deadline,
        status=req.status,
        project_id=project.id if project else None,
        proposals_count=proposals_count,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


def _proposal_response(p: Proposal) -> ProposalResponse:
    return ProposalResponse(
        id=p.id,
        request_id=p.request_id,
        agency_workspace_id=p.agency_workspace_id,
        scope_description=p.scope_description,
        estimated_days=p.estimated_days,
        estimated_delivery_date=p.estimated_delivery_date,
        deliverables_summary=p.deliverables_summary,
        status=p.status,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _message_response(m: ProjectMessage) -> ProjectMessageResponse:
    sender = m.sender
    sender_name = sender.full_name if sender else ""
    return ProjectMessageResponse(
        id=m.id,
        request_id=m.request_id,
        project_id=m.project_id,
        sender_id=m.sender_id,
        sender_name=sender_name,
        sender_role=m.sender_role,
        content=m.content,
        created_at=m.created_at,
    )


class MessageBodyInput(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


# ---------------------------------------------------------------------------
# CLIENT — Project Request Lifecycle
# ---------------------------------------------------------------------------

@router.post("/api/client/requests", status_code=201, response_model=ProjectRequestResponse)
def create_project_request(
    data: ProjectRequestCreateInput,
    current_user: User = Depends(require_client_role),
    db: Session = Depends(get_db),
) -> ProjectRequestResponse:
    """Client submits a project brief to a specific agency."""
    agency_ws = db.get(Workspace, data.agency_workspace_id)
    if not agency_ws:
        raise HTTPException(404, "Agency not found")

    agency_profile = db.scalar(
        select(AgencyProfile).where(AgencyProfile.workspace_id == data.agency_workspace_id)
    )
    if not agency_profile or not agency_profile.is_published:
        raise HTTPException(404, "Agency is not accepting project requests")

    req = ProjectRequest(
        client_user_id=current_user.id,
        agency_workspace_id=data.agency_workspace_id,
        title=data.title.strip(),
        description=data.description,
        video_type=data.video_type,
        target_platform=data.target_platform,
        target_duration=data.target_duration,
        aspect_ratio=data.aspect_ratio,
        editing_requirements=data.editing_requirements,
        creative_direction=data.creative_direction,
        reference_links=json.dumps(data.reference_links),
        deliverables_format=data.deliverables_format,
        budget=data.budget,
        deadline=data.deadline,
        status=data.status,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return _request_response(req, db)


@router.get("/api/client/requests", response_model=list[ProjectRequestResponse])
def list_client_requests(
    status: str | None = None,
    current_user: User = Depends(require_client_role),
    db: Session = Depends(get_db),
) -> list[ProjectRequestResponse]:
    """Client lists all their own project requests."""
    stmt = select(ProjectRequest).where(ProjectRequest.client_user_id == current_user.id)
    if status:
        stmt = stmt.where(ProjectRequest.status == status)
    stmt = stmt.order_by(ProjectRequest.created_at.desc())
    reqs = db.scalars(stmt).all()
    return [_request_response(r, db) for r in reqs]


@router.get("/api/client/requests/{request_id}", response_model=ProjectRequestResponse)
def get_client_request(
    request_id: int,
    current_user: User = Depends(require_client_role),
    db: Session = Depends(get_db),
) -> ProjectRequestResponse:
    """Client retrieves a specific project request with proposals."""
    req = db.scalar(
        select(ProjectRequest).where(
            ProjectRequest.id == request_id,
            ProjectRequest.client_user_id == current_user.id,
        )
    )
    if not req:
        raise HTTPException(404, "Project request not found")
    return _request_response(req, db)


@router.patch("/api/client/requests/{request_id}", response_model=ProjectRequestResponse)
def update_client_request(
    request_id: int,
    data: ProjectRequestUpdateInput,
    current_user: User = Depends(require_client_role),
    db: Session = Depends(get_db),
) -> ProjectRequestResponse:
    """Client updates a request."""
    req = db.scalar(
        select(ProjectRequest).where(
            ProjectRequest.id == request_id,
            ProjectRequest.client_user_id == current_user.id,
        )
    )
    if not req:
        raise HTTPException(404, "Project request not found")
    if req.status not in ("draft", "submitted"):
        raise HTTPException(400, f"Cannot edit a request with status '{req.status}'")

    update_dict = data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if field == "reference_links":
            setattr(req, field, json.dumps(value or []))
        else:
            setattr(req, field, value)
    req.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(req)
    return _request_response(req, db)


@router.get("/api/client/requests/{request_id}/proposals", response_model=list[ProposalResponse])
def list_request_proposals(
    request_id: int,
    current_user: User = Depends(require_client_role),
    db: Session = Depends(get_db),
) -> list[ProposalResponse]:
    """Client lists proposals received for one of their requests."""
    req = db.scalar(
        select(ProjectRequest).where(
            ProjectRequest.id == request_id,
            ProjectRequest.client_user_id == current_user.id,
        )
    )
    if not req:
        raise HTTPException(404, "Project request not found")
    proposals = db.scalars(
        select(Proposal).where(Proposal.request_id == request_id).order_by(Proposal.created_at)
    ).all()
    return [_proposal_response(p) for p in proposals]


@router.post("/api/client/requests/{request_id}/proposals/{proposal_id}/accept",
             response_model=ProposalActionResponse)
def accept_proposal(
    request_id: int,
    proposal_id: int,
    current_user: User = Depends(require_client_role),
    db: Session = Depends(get_db),
) -> ProposalActionResponse:
    """Client accepts a proposal — creates an active project and marks other proposals declined."""
    req = db.scalar(
        select(ProjectRequest).where(
            ProjectRequest.id == request_id,
            ProjectRequest.client_user_id == current_user.id,
        )
    )
    if not req:
        raise HTTPException(404, "Project request not found")

    proposal = db.scalar(
        select(Proposal).where(Proposal.id == proposal_id, Proposal.request_id == request_id)
    )
    if not proposal:
        raise HTTPException(404, "Proposal not found")

    if proposal.status != "pending":
        raise HTTPException(400, f"Proposal is already '{proposal.status}'")

    if req.status in ("accepted", "declined", "cancelled"):
        raise HTTPException(400, f"Request is already '{req.status}'")

    proposal.status = "accepted"
    proposal.updated_at = datetime.now(UTC)

    other_proposals = db.scalars(
        select(Proposal).where(Proposal.request_id == request_id, Proposal.id != proposal_id)
    ).all()
    for other in other_proposals:
        other.status = "declined"
        other.updated_at = datetime.now(UTC)

    req.status = "accepted"
    req.updated_at = datetime.now(UTC)

    agency_workspace_id = req.agency_workspace_id
    client = db.scalar(
        select(Client).where(
            Client.workspace_id == agency_workspace_id,
            Client.name == (current_user.full_name or current_user.email),
        )
    )
    if not client:
        from uuid import uuid4
        bank_id = f"frameops-w{agency_workspace_id}-u{current_user.id}-{uuid4().hex[:8]}"
        client = Client(
            workspace_id=agency_workspace_id,
            name=current_user.full_name or current_user.email,
            brand=current_user.client_profile.company_name if current_user.client_profile else "",
            industry=current_user.client_profile.industry if current_user.client_profile else "",
            description="",
            memory_bank_id=bank_id,
            memory_status="unavailable",
        )
        db.add(client)
        db.flush()

    project = Project(
        workspace_id=agency_workspace_id,
        client_id=client.id,
        name=req.title,
        description=req.description,
        status="active",
        due_date=req.deadline,
        request_id=req.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    return ProposalActionResponse(
        proposal_id=proposal.id,
        request_id=req.id,
        status="accepted",
        project_id=project.id,
    )


@router.post("/api/client/requests/{request_id}/proposals/{proposal_id}/decline",
             response_model=ProposalActionResponse)
def decline_proposal(
    request_id: int,
    proposal_id: int,
    current_user: User = Depends(require_client_role),
    db: Session = Depends(get_db),
) -> ProposalActionResponse:
    """Client declines a specific proposal."""
    req = db.scalar(
        select(ProjectRequest).where(
            ProjectRequest.id == request_id,
            ProjectRequest.client_user_id == current_user.id,
        )
    )
    if not req:
        raise HTTPException(404, "Project request not found")

    proposal = db.scalar(
        select(Proposal).where(Proposal.id == proposal_id, Proposal.request_id == request_id)
    )
    if not proposal:
        raise HTTPException(404, "Proposal not found")

    if proposal.status != "pending":
        raise HTTPException(400, f"Proposal is already '{proposal.status}'")

    proposal.status = "declined"
    proposal.updated_at = datetime.now(UTC)
    db.commit()

    return ProposalActionResponse(
        proposal_id=proposal.id,
        request_id=req.id,
        status="declined",
        project_id=None,
    )


# ---------------------------------------------------------------------------
# AGENCY — Incoming Requests & Proposal Management
# ---------------------------------------------------------------------------

@router.get("/api/agency/requests", response_model=list[ProjectRequestResponse])
def list_agency_requests(
    status: str | None = None,
    identity: tuple[User, int, str] = Depends(require_agency_role),
    db: Session = Depends(get_db),
) -> list[ProjectRequestResponse]:
    """Agency lists all incoming project requests for their workspace (omitting drafts)."""
    _, workspace_id, _ = identity
    stmt = select(ProjectRequest).where(
        ProjectRequest.agency_workspace_id == workspace_id,
        ProjectRequest.status != "draft",
    )
    if status and status != "all":
        stmt = stmt.where(ProjectRequest.status == status)
    stmt = stmt.order_by(ProjectRequest.created_at.desc())
    reqs = db.scalars(stmt).all()
    return [_request_response(r, db) for r in reqs]


@router.get("/api/agency/requests/{request_id}", response_model=ProjectRequestResponse)
def get_agency_request(
    request_id: int,
    identity: tuple[User, int, str] = Depends(require_agency_role),
    db: Session = Depends(get_db),
) -> ProjectRequestResponse:
    """Agency retrieves a specific incoming request."""
    _, workspace_id, _ = identity
    req = db.scalar(
        select(ProjectRequest).where(
            ProjectRequest.id == request_id,
            ProjectRequest.agency_workspace_id == workspace_id,
        )
    )
    if not req:
        raise HTTPException(404, "Project request not found")
    return _request_response(req, db)


@router.post("/api/agency/requests/{request_id}/proposals", status_code=201,
             response_model=ProposalResponse)
def create_proposal(
    request_id: int,
    data: ProposalCreateInput,
    identity: tuple[User, int, str] = Depends(require_agency_role),
    db: Session = Depends(get_db),
) -> ProposalResponse:
    """Agency submits a proposal for an incoming project request."""
    _, workspace_id, _ = identity
    req = db.scalar(
        select(ProjectRequest).where(
            ProjectRequest.id == request_id,
            ProjectRequest.agency_workspace_id == workspace_id,
        )
    )
    if not req:
        raise HTTPException(404, "Project request not found")
    if req.status == "draft":
        raise HTTPException(400, "Cannot propose on a draft request")
    if req.status == "cancelled":
        raise HTTPException(400, "Cannot propose on a cancelled request")

    existing = db.scalar(
        select(Proposal).where(
            Proposal.request_id == request_id,
            Proposal.agency_workspace_id == workspace_id,
        )
    )
    if existing:
        raise HTTPException(409, "A proposal already exists for this request. Use PATCH to update it.")

    proposal = Proposal(
        request_id=request_id,
        agency_workspace_id=workspace_id,
        scope_description=data.scope_description,
        estimated_days=data.estimated_days,
        estimated_delivery_date=data.estimated_delivery_date,
        deliverables_summary=data.deliverables_summary,
        status="pending",
    )
    db.add(proposal)

    # Transition request status to proposal_received
    req.status = "proposal_received"
    req.updated_at = datetime.now(UTC)

    db.commit()
    db.refresh(proposal)
    return _proposal_response(proposal)


@router.patch("/api/agency/requests/{request_id}/proposals/{proposal_id}",
              response_model=ProposalResponse)
def update_proposal(
    request_id: int,
    proposal_id: int,
    data: ProposalUpdateInput,
    identity: tuple[User, int, str] = Depends(require_agency_role),
    db: Session = Depends(get_db),
) -> ProposalResponse:
    """Agency updates a pending proposal."""
    _, workspace_id, _ = identity
    proposal = db.scalar(
        select(Proposal).where(
            Proposal.id == proposal_id,
            Proposal.request_id == request_id,
            Proposal.agency_workspace_id == workspace_id,
        )
    )
    if not proposal:
        raise HTTPException(404, "Proposal not found")
    if proposal.status != "pending":
        raise HTTPException(400, f"Cannot update a proposal with status '{proposal.status}'")

    update_dict = data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(proposal, field, value)
    proposal.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(proposal)
    return _proposal_response(proposal)


@router.get("/api/agency/requests/{request_id}/proposals", response_model=list[ProposalResponse])
def list_agency_request_proposals(
    request_id: int,
    identity: tuple[User, int, str] = Depends(require_agency_role),
    db: Session = Depends(get_db),
) -> list[ProposalResponse]:
    """Agency lists proposals for a request in their workspace."""
    _, workspace_id, _ = identity
    req = db.scalar(
        select(ProjectRequest).where(
            ProjectRequest.id == request_id,
            ProjectRequest.agency_workspace_id == workspace_id,
        )
    )
    if not req:
        raise HTTPException(404, "Project request not found")
    proposals = db.scalars(
        select(Proposal).where(
            Proposal.request_id == request_id,
            Proposal.agency_workspace_id == workspace_id,
        ).order_by(Proposal.created_at)
    ).all()
    return [_proposal_response(p) for p in proposals]


# ---------------------------------------------------------------------------
# CLIENT PROFILE — Self-management
# ---------------------------------------------------------------------------

@router.get("/api/client/profile")
def get_client_profile(
    current_user: User = Depends(require_client_role),
    db: Session = Depends(get_db),
) -> dict:
    """Client retrieves their own profile."""
    profile = current_user.client_profile
    if not profile:
        return {
            "id": None,
            "user_id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "company_name": "",
            "industry": "",
            "brand_guidelines": "",
            "website": "",
        }
    return {
        "id": profile.id,
        "user_id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "company_name": profile.company_name,
        "industry": profile.industry,
        "brand_guidelines": profile.brand_guidelines,
        "website": profile.website,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


@router.patch("/api/client/profile")
def update_client_profile(
    data: dict,
    current_user: User = Depends(require_client_role),
    db: Session = Depends(get_db),
) -> dict:
    """Client updates their profile fields."""
    profile = current_user.client_profile
    if not profile:
        raise HTTPException(404, "Client profile not found — please re-register")

    allowed_fields = {"company_name", "industry", "brand_guidelines", "website"}
    for field, value in data.items():
        if field in allowed_fields and isinstance(value, str):
            setattr(profile, field, value.strip())
    profile.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(profile)
    return {
        "id": profile.id,
        "user_id": current_user.id,
        "company_name": profile.company_name,
        "industry": profile.industry,
        "brand_guidelines": profile.brand_guidelines,
        "website": profile.website,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


# ---------------------------------------------------------------------------
# MESSAGING (Shared / Standard endpoint: /api/requests/{id}/messages)
# ---------------------------------------------------------------------------

@router.post("/api/requests/{request_id}/messages", status_code=201, response_model=ProjectMessageResponse)
def post_request_message(
    request_id: int,
    data: MessageBodyInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectMessageResponse:
    """Post clarification or status message on a project request."""
    req = db.get(ProjectRequest, request_id)
    if not req:
        raise HTTPException(404, "Project request not found")

    sender_role = ""
    if current_user.role == "client":
        if req.client_user_id != current_user.id:
            raise HTTPException(403, "Access forbidden: you do not own this request")
        sender_role = "client"
    else:
        member = db.query(Membership).filter_by(
            user_id=current_user.id, workspace_id=req.agency_workspace_id
        ).first()
        if not member:
            raise HTTPException(403, "Access forbidden: this request belongs to another agency")
        sender_role = "agency"

    msg = ProjectMessage(
        request_id=request_id,
        sender_id=current_user.id,
        sender_role=sender_role,
        content=data.content.strip(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _message_response(msg)


@router.get("/api/requests/{request_id}/messages", response_model=list[ProjectMessageResponse])
def get_request_messages(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectMessageResponse]:
    """Retrieve message thread for a request."""
    req = db.get(ProjectRequest, request_id)
    if not req:
        raise HTTPException(404, "Project request not found")

    if current_user.role == "client":
        if req.client_user_id != current_user.id:
            raise HTTPException(403, "Access forbidden: you do not own this request")
    else:
        member = db.query(Membership).filter_by(
            user_id=current_user.id, workspace_id=req.agency_workspace_id
        ).first()
        if not member:
            raise HTTPException(403, "Access forbidden: this request belongs to another agency")

    msgs = db.scalars(
        select(ProjectMessage).where(ProjectMessage.request_id == request_id)
        .order_by(ProjectMessage.created_at)
    ).all()
    return [_message_response(m) for m in msgs]


@router.post("/api/messages", status_code=201, response_model=ProjectMessageResponse)
def client_send_message_alias(
    data: ProjectMessageCreateInput,
    current_user: User = Depends(require_client_role),
    db: Session = Depends(get_db),
) -> ProjectMessageResponse:
    """Client sends a message on a project request thread (alias)."""
    if not data.request_id and not data.project_id:
        raise HTTPException(422, "Either request_id or project_id is required")

    if data.request_id:
        req = db.scalar(
            select(ProjectRequest).where(
                ProjectRequest.id == data.request_id,
                ProjectRequest.client_user_id == current_user.id,
            )
        )
        if not req:
            raise HTTPException(404, "Project request not found")

    msg = ProjectMessage(
        request_id=data.request_id,
        project_id=data.project_id,
        sender_id=current_user.id,
        sender_role="client",
        content=data.content.strip(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _message_response(msg)


@router.post("/api/agency/messages", status_code=201, response_model=ProjectMessageResponse)
def agency_send_message_alias(
    data: ProjectMessageCreateInput,
    identity: tuple[User, int, str] = Depends(require_agency_role),
    db: Session = Depends(get_db),
) -> ProjectMessageResponse:
    """Agency sends a message on a project request thread (alias)."""
    current_user, workspace_id, _ = identity
    if not data.request_id and not data.project_id:
        raise HTTPException(422, "Either request_id or project_id is required")

    if data.request_id:
        req = db.scalar(
            select(ProjectRequest).where(
                ProjectRequest.id == data.request_id,
                ProjectRequest.agency_workspace_id == workspace_id,
            )
        )
        if not req:
            raise HTTPException(404, "Project request not found or does not belong to your workspace")

    msg = ProjectMessage(
        request_id=data.request_id,
        project_id=data.project_id,
        sender_id=current_user.id,
        sender_role="agency",
        content=data.content.strip(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _message_response(msg)


@router.get("/api/agency/requests/{request_id}/messages", response_model=list[ProjectMessageResponse])
def get_agency_request_messages_alias(
    request_id: int,
    identity: tuple[User, int, str] = Depends(require_agency_role),
    db: Session = Depends(get_db),
) -> list[ProjectMessageResponse]:
    """Agency lists all messages for a request thread (alias)."""
    _, workspace_id, _ = identity
    req = db.scalar(
        select(ProjectRequest).where(
            ProjectRequest.id == request_id,
            ProjectRequest.agency_workspace_id == workspace_id,
        )
    )
    if not req:
        raise HTTPException(404, "Project request not found")
    msgs = db.scalars(
        select(ProjectMessage).where(ProjectMessage.request_id == request_id)
        .order_by(ProjectMessage.created_at)
    ).all()
    return [_message_response(m) for m in msgs]
