"""Agency Profile Management Router.

Enforces RBAC via `require_agency_role` and provides endpoints for retrieving,
updating, publishing, and unpublishing agency profiles.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AgencyProfile, User, Workspace
from ..schemas import (
    AgencyProfileResponse,
    AgencyProfileUpdateInput,
    PublishStatusResponse,
)
from ..security import require_agency_role

router = APIRouter(prefix="/api/agency", tags=["agency_profile"])


def evaluate_publishing_readiness(profile: AgencyProfile) -> tuple[bool, list[str]]:
    """Evaluates readiness of an agency profile for public discovery.
    
    Minimum requirements:
    1. description (non-empty, non-whitespace)
    2. contact_email (non-empty, non-whitespace, contains '@')
    3. specializations (at least one non-empty entry)
    4. services (at least one non-empty entry)
    """
    missing: list[str] = []

    if not (profile.description and profile.description.strip()):
        missing.append("description")

    if not (profile.contact_email and profile.contact_email.strip() and "@" in profile.contact_email):
        missing.append("contact_email")

    specs = [s.strip() for s in profile.specializations_list if s and s.strip()]
    if len(specs) == 0:
        missing.append("specializations")

    srvs = [s.strip() for s in profile.services_list if s and s.strip()]
    if len(srvs) == 0:
        missing.append("services")

    return len(missing) == 0, missing


def _build_profile_response(profile: AgencyProfile, workspace_name: str) -> AgencyProfileResponse:
    is_ready, missing = evaluate_publishing_readiness(profile)
    return AgencyProfileResponse(
        id=profile.id,
        workspace_id=profile.workspace_id,
        workspace_name=workspace_name,
        tagline=profile.tagline or "",
        description=profile.description or "",
        specializations=profile.specializations_list,
        services=profile.services_list,
        portfolio=profile.portfolio_list,
        contact_email=profile.contact_email or "",
        contact_phone=profile.contact_phone or "",
        website=profile.website or "",
        is_published=profile.is_published,
        published_at=profile.published_at,
        can_publish=is_ready,
        is_ready_to_publish=is_ready,
        missing_fields=missing,
        missing_publish_fields=missing,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get("/profile", response_model=AgencyProfileResponse)
def get_agency_profile(
    identity: tuple[User, int, str] = Depends(require_agency_role),
    db: Session = Depends(get_db),
) -> AgencyProfileResponse:
    """Retrieve the current agency workspace profile and publication readiness."""
    current_user, workspace_id, role = identity
    profile = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == workspace_id))
    if not profile:
        profile = AgencyProfile(
            workspace_id=workspace_id,
            contact_email=current_user.email,
            is_published=False,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

    ws = db.get(Workspace, workspace_id)
    ws_name = ws.name if ws else ""
    return _build_profile_response(profile, ws_name)


@router.put("/profile", response_model=AgencyProfileResponse)
def update_agency_profile(
    data: AgencyProfileUpdateInput,
    identity: tuple[User, int, str] = Depends(require_agency_role),
    db: Session = Depends(get_db),
) -> AgencyProfileResponse:
    """Partially update agency profile fields and serialize list fields to JSON."""
    current_user, workspace_id, role = identity
    profile = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == workspace_id))
    if not profile:
        profile = AgencyProfile(
            workspace_id=workspace_id,
            contact_email=current_user.email,
            is_published=False,
        )
        db.add(profile)
        db.flush()

    update_dict = data.model_dump(exclude_unset=True)

    if "tagline" in update_dict:
        profile.tagline = (update_dict["tagline"] or "").strip()
    if "description" in update_dict:
        profile.description = (update_dict["description"] or "").strip()
    if "contact_email" in update_dict:
        profile.contact_email = (update_dict["contact_email"] or "").strip()
    if "contact_phone" in update_dict:
        profile.contact_phone = (update_dict["contact_phone"] or "").strip()
    if "website" in update_dict:
        profile.website = (update_dict["website"] or "").strip()

    if "specializations" in update_dict:
        specs = update_dict["specializations"]
        if specs is None:
            specs = []
        profile.specializations = json.dumps(specs, ensure_ascii=False)

    if "services" in update_dict:
        srvs = update_dict["services"]
        if srvs is None:
            srvs = []
        profile.services = json.dumps(srvs, ensure_ascii=False)

    if "portfolio" in update_dict:
        port = update_dict["portfolio"]
        if port is None:
            port = []
        profile.portfolio = json.dumps(port, ensure_ascii=False)

    profile.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(profile)

    ws = db.get(Workspace, workspace_id)
    ws_name = ws.name if ws else ""
    return _build_profile_response(profile, ws_name)


@router.post("/profile/publish", response_model=PublishStatusResponse)
def publish_agency_profile(
    identity: tuple[User, int, str] = Depends(require_agency_role),
    db: Session = Depends(get_db),
) -> PublishStatusResponse:
    """Validate publishing readiness and publish profile for public discovery."""
    current_user, workspace_id, role = identity
    profile = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == workspace_id))
    if not profile:
        profile = AgencyProfile(
            workspace_id=workspace_id,
            contact_email=current_user.email,
            is_published=False,
        )
        db.add(profile)
        db.flush()

    is_ready, missing = evaluate_publishing_readiness(profile)
    if not is_ready:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Cannot publish incomplete profile. Please provide all required fields.",
                "missing_fields": missing,
            },
        )

    profile.is_published = True
    profile.published_at = datetime.now(UTC)
    profile.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(profile)

    return PublishStatusResponse(
        workspace_id=profile.workspace_id,
        is_published=True,
        published_at=profile.published_at,
        can_publish=True,
        is_ready_to_publish=True,
        missing_fields=[],
        missing_publish_fields=[],
        message="Agency profile published successfully",
    )


@router.post("/profile/unpublish", response_model=PublishStatusResponse)
def unpublish_agency_profile(
    identity: tuple[User, int, str] = Depends(require_agency_role),
    db: Session = Depends(get_db),
) -> PublishStatusResponse:
    """Explicitly unpublish profile, hiding it immediately from public discovery."""
    current_user, workspace_id, role = identity
    profile = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == workspace_id))
    if not profile:
        profile = AgencyProfile(
            workspace_id=workspace_id,
            contact_email=current_user.email,
            is_published=False,
        )
        db.add(profile)
        db.flush()

    profile.is_published = False
    profile.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(profile)

    is_ready, missing = evaluate_publishing_readiness(profile)
    return PublishStatusResponse(
        workspace_id=profile.workspace_id,
        is_published=False,
        published_at=profile.published_at,
        can_publish=is_ready,
        is_ready_to_publish=is_ready,
        missing_fields=missing,
        missing_publish_fields=missing,
        message="Agency profile unpublished successfully",
    )
