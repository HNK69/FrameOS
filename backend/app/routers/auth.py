"""Authentication Router: Client and Agency Registration, Login, Logout, Status, Setup, and Identity."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import AgencyProfile, ClientProfile, Membership, User, Workspace
from ..schemas import (
    AgencyRegisterInput,
    AuthResponse,
    ClientRegisterInput,
    LoginInput,
    SetupInput,
    UserResponse,
)
from ..security import (
    clear_auth_cookies,
    get_current_user,
    hash_password,
    issue_client_session_token,
    issue_token,
    set_auth_cookie,
    verify_password,
)

router = APIRouter(tags=["auth"])


@router.get("/api/auth/status")
def auth_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Workspace bootstrap and authentication readiness status."""
    return {
        "setup_required": db.query(User).count() == 0,
        "auth_ready": bool(settings.auth_secret),
    }


@router.post("/api/auth/setup")
def setup(data: SetupInput, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Initial workspace owner setup for bootstrap deployments."""
    if not settings.auth_secret:
        raise HTTPException(503, "Set AUTH_SECRET before creating the workspace owner")
    if db.query(User).count():
        raise HTTPException(409, "Initial owner is already configured")

    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        full_name="",
        role="agency_owner",
    )
    workspace = Workspace(name=data.workspace_name.strip())
    db.add_all([user, workspace])
    db.flush()

    member = Membership(workspace_id=workspace.id, user_id=user.id, role="owner")
    profile = AgencyProfile(
        workspace_id=workspace.id,
        tagline="",
        description="",
        specializations="[]",
        services="[]",
        portfolio="[]",
        contact_email=data.email.lower(),
        is_published=False,
    )
    db.add_all([member, profile])
    db.commit()
    db.refresh(user)
    db.refresh(workspace)

    token = issue_token(user, member)
    set_auth_cookie(response, token, "frameops_session")

    return {
        "workspace": {"id": workspace.id, "name": workspace.name},
        "workspace_id": workspace.id,
        "user_id": user.id,
        "id": user.id,
        "email": user.email,
        "role": "agency_owner",
    }


@router.post(
    "/api/auth/register/client",
    status_code=status.HTTP_201_CREATED,
    response_model=AuthResponse,
)
def register_client(
    data: ClientRegisterInput,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Public Client Registration: Creates User(role='client') and ClientProfile."""
    if not settings.auth_secret:
        raise HTTPException(503, "Set AUTH_SECRET before enabling sign-in")

    existing = db.scalar(select(User).where(User.email == data.email.lower()))
    if existing:
        raise HTTPException(409, "Email is already registered")

    full_name = data.full_name.strip()
    company_name = data.company_name.strip()

    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        full_name=full_name,
        role="client",
    )
    db.add(user)
    db.flush()

    profile = ClientProfile(
        user_id=user.id,
        company_name=company_name,
    )
    db.add(profile)
    db.commit()
    db.refresh(user)

    token = issue_client_session_token(user)
    set_auth_cookie(response, token, "frameops_client_session")
    response.delete_cookie("frameops_session", path="/", httponly=True, secure=settings.auth_cookie_secure, samesite="lax")

    return AuthResponse(
        user_id=user.id,
        id=user.id,
        email=user.email,
        role="client",
        full_name=user.full_name,
        company_name=company_name,
        workspace_id=None,
    )


@router.post(
    "/api/auth/register/agency",
    status_code=status.HTTP_201_CREATED,
    response_model=AuthResponse,
)
def register_agency(
    data: AgencyRegisterInput,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Public Agency Registration: Creates User(role='agency_owner'), Workspace, Membership & AgencyProfile."""
    if not settings.auth_secret:
        raise HTTPException(503, "Set AUTH_SECRET before enabling sign-in")

    existing = db.scalar(select(User).where(User.email == data.email.lower()))
    if existing:
        raise HTTPException(409, "Email is already registered")

    agency_name = data.agency_name.strip()
    if len(agency_name) < 2:
        raise HTTPException(422, "Agency name must be at least 2 characters")

    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        full_name=data.full_name.strip(),
        role="agency_owner",
    )
    workspace = Workspace(name=agency_name)
    db.add_all([user, workspace])
    db.flush()

    membership = Membership(
        user_id=user.id,
        workspace_id=workspace.id,
        role="owner",
    )
    profile = AgencyProfile(
        workspace_id=workspace.id,
        tagline="",
        description="",
        specializations="[]",
        services="[]",
        portfolio="[]",
        contact_email=data.email.lower(),
        is_published=False,
    )
    db.add_all([membership, profile])
    db.commit()
    db.refresh(user)
    db.refresh(workspace)

    token = issue_token(user, membership)
    set_auth_cookie(response, token, "frameops_session")
    response.delete_cookie("frameops_client_session", path="/", httponly=True, secure=settings.auth_cookie_secure, samesite="lax")

    return AuthResponse(
        user_id=user.id,
        id=user.id,
        email=user.email,
        role="agency_owner",
        full_name=user.full_name,
        workspace_id=workspace.id,
        workspace={"id": workspace.id, "name": workspace.name},
    )


@router.post("/api/auth/login", response_model=AuthResponse)
def login(
    data: LoginInput,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Role-aware user authentication: Validates credentials and sets persona session cookie."""
    if not settings.auth_secret:
        raise HTTPException(503, "Set AUTH_SECRET before enabling sign-in")

    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")

    if user.role == "client":
        token = issue_client_session_token(user)
        set_auth_cookie(response, token, "frameops_client_session")
        response.delete_cookie("frameops_session", path="/", httponly=True, secure=settings.auth_cookie_secure, samesite="lax")
        company_name = user.client_profile.company_name if user.client_profile else None
        return AuthResponse(
            user_id=user.id,
            id=user.id,
            email=user.email,
            role="client",
            full_name=user.full_name,
            company_name=company_name,
            workspace_id=None,
        )

    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id).order_by(Membership.id)
    )
    if not membership:
        raise HTTPException(403, "No workspace membership")

    token = issue_token(user, membership)
    set_auth_cookie(response, token, "frameops_session")
    response.delete_cookie("frameops_client_session", path="/", httponly=True, secure=settings.auth_cookie_secure, samesite="lax")

    return AuthResponse(
        user_id=user.id,
        id=user.id,
        email=user.email,
        role=user.role,
        full_name=user.full_name,
        workspace_id=membership.workspace_id,
        workspace={
            "id": membership.workspace_id,
            "name": membership.workspace.name if membership.workspace else "",
        },
    )


@router.post("/api/auth/logout")
def logout(response: Response) -> dict[str, Any]:
    """Logs out current user and clears all persona session cookies."""
    clear_auth_cookies(response)
    return {"logged_out": True, "message": "Logged out successfully"}


@router.get("/api/me", response_model=UserResponse)
def me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Returns currently authenticated identity, role, and workspace or profile context."""
    if user.role == "client":
        client_profile_data = None
        company_name = None
        if user.client_profile:
            company_name = user.client_profile.company_name
            client_profile_data = {
                "id": user.client_profile.id,
                "user_id": user.client_profile.user_id,
                "company_name": user.client_profile.company_name,
                "industry": user.client_profile.industry,
                "brand_guidelines": user.client_profile.brand_guidelines,
                "website": user.client_profile.website,
                "created_at": user.client_profile.created_at,
                "updated_at": user.client_profile.updated_at,
            }
        return UserResponse(
            id=user.id,
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role="client",
            company_name=company_name,
            workspace_id=None,
            workspace_name=None,
            client_profile=client_profile_data,
            created_at=user.created_at,
        )

    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id).order_by(Membership.id)
    )
    workspace_id = membership.workspace_id if membership else None
    workspace_name = (
        membership.workspace.name if (membership and membership.workspace) else None
    )

    agency_profile_data = None
    if workspace_id:
        ap = db.scalar(
            select(AgencyProfile).where(AgencyProfile.workspace_id == workspace_id)
        )
        if ap:
            agency_profile_data = {
                "id": ap.id,
                "workspace_id": ap.workspace_id,
                "workspace_name": workspace_name or "",
                "tagline": ap.tagline,
                "description": ap.description,
                "specializations": ap.specializations_list,
                "services": ap.services_list,
                "portfolio": ap.portfolio_list,
                "contact_email": ap.contact_email,
                "contact_phone": ap.contact_phone,
                "website": ap.website,
                "is_published": ap.is_published,
                "published_at": ap.published_at,
                "created_at": ap.created_at,
                "updated_at": ap.updated_at,
            }

    return UserResponse(
        id=user.id,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        workspace_id=workspace_id,
        workspace_name=workspace_name,
        workspace={"id": workspace_id, "name": workspace_name} if workspace_id else None,
        agency_profile=agency_profile_data,
        created_at=user.created_at,
    )
