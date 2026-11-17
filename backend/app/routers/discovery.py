"""Agency Discovery Catalog Router.

Provides public endpoints for browsing, searching, and viewing published agency profiles.
Enforces the invariant that only published profiles are visible to the public.
Allows workspace owners/members to preview their unpublished profiles.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AgencyProfile, Membership, User, Workspace
from ..schemas import AgencyDiscoveryDetail, AgencyDiscoveryItem
from ..security import get_optional_current_user

router = APIRouter(prefix="/api/discovery", tags=["discovery"])


@router.get("/agencies", response_model=list[AgencyDiscoveryItem])
def list_agencies(
    query: str | None = Query(default=None, description="Search term matching agency name, tagline, or description"),
    specialization: str | None = Query(default=None, description="Filter by specialization"),
    service: str | None = Query(default=None, description="Filter by service"),
    category: str | None = Query(default=None, description="Filter by category (matches specialization or service)"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[AgencyDiscoveryItem]:
    """List published agencies in the discovery catalog with search and filtering.
    
    INVARIANT: Only agencies with is_published == True are returned.
    """
    stmt = (
        select(AgencyProfile, Workspace)
        .join(Workspace, AgencyProfile.workspace_id == Workspace.id)
        .where(AgencyProfile.is_published.is_(True))
    )

    if query and query.strip():
        q = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                Workspace.name.ilike(q),
                AgencyProfile.tagline.ilike(q),
                AgencyProfile.description.ilike(q),
            )
        )

    if specialization and specialization.strip():
        spec = f"%{specialization.strip()}%"
        stmt = stmt.where(AgencyProfile.specializations.ilike(spec))

    if service and service.strip():
        srv = f"%{service.strip()}%"
        stmt = stmt.where(AgencyProfile.services.ilike(srv))

    if category and category.strip():
        cat = f"%{category.strip()}%"
        stmt = stmt.where(
            or_(
                AgencyProfile.specializations.ilike(cat),
                AgencyProfile.services.ilike(cat),
            )
        )

    stmt = stmt.order_by(AgencyProfile.published_at.desc(), AgencyProfile.id.desc())
    stmt = stmt.offset(offset).limit(limit)

    rows = db.execute(stmt).all()

    items: list[AgencyDiscoveryItem] = []
    for profile, ws in rows:
        # Refine in-memory matching on parsed lists for exact case-insensitive matches
        if specialization and specialization.strip():
            spec_lower = specialization.strip().lower()
            if not any(spec_lower in s.lower() for s in profile.specializations_list):
                continue

        if service and service.strip():
            srv_lower = service.strip().lower()
            if not any(srv_lower in s.lower() for s in profile.services_list):
                continue

        if category and category.strip():
            cat_lower = category.strip().lower()
            match_spec = any(cat_lower in s.lower() for s in profile.specializations_list)
            match_srv = any(cat_lower in s.lower() for s in profile.services_list)
            if not (match_spec or match_srv):
                continue

        items.append(
            AgencyDiscoveryItem(
                workspace_id=profile.workspace_id,
                name=ws.name,
                tagline=profile.tagline or "",
                description=profile.description or "",
                specializations=profile.specializations_list,
                services=profile.services_list,
                portfolio=profile.portfolio_list,
                contact_email=profile.contact_email or "",
                website=profile.website or "",
                is_published=True,
                published_at=profile.published_at,
            )
        )

    return items


@router.get("/agencies/{workspace_id}", response_model=AgencyDiscoveryDetail)
def get_agency_detail(
    workspace_id: int,
    optional_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> AgencyDiscoveryDetail:
    """Retrieve detailed public profile for a single agency.
    
    Unpublished agencies return 404 unless previewed by an authenticated member/owner of the workspace.
    """
    row = db.execute(
        select(AgencyProfile, Workspace)
        .join(Workspace, AgencyProfile.workspace_id == Workspace.id)
        .where(AgencyProfile.workspace_id == workspace_id)
    ).first()

    if not row:
        raise HTTPException(status_code=404, detail="Agency not found")

    profile, ws = row

    if not profile.is_published:
        # Owner / member preview check
        is_member = False
        if optional_user:
            mem = db.scalar(
                select(Membership).where(
                    Membership.workspace_id == workspace_id,
                    Membership.user_id == optional_user.id,
                )
            )
            if mem:
                is_member = True

        if not is_member:
            raise HTTPException(status_code=404, detail="Agency not found or not published")

    return AgencyDiscoveryDetail(
        workspace_id=profile.workspace_id,
        name=ws.name,
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
        created_at=profile.created_at,
    )
