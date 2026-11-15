"""Security, Password Hashing, JWT Sessions & RBAC Guards for FRAMEOPS."""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Client, ClientPortalAccess, Membership, User, now_utc

password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash password using Argon2id via pwdlib."""
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against Argon2id hash."""
    return password_hash.verify(password, hashed)


def issue_token(user: User, membership: Membership) -> str:
    """Issue JWT session token for agency user with workspace membership."""
    if not settings.auth_secret:
        raise HTTPException(503, "Set AUTH_SECRET before enabling sign-in")
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "email": user.email,
            "workspace_id": membership.workspace_id,
            "role": membership.role,
            "user_role": user.role,
            "iat": now,
            "exp": now + timedelta(minutes=settings.auth_token_minutes),
        },
        settings.auth_secret,
        algorithm="HS256",
    )


def issue_client_session_token(user: User) -> str:
    """Issue JWT session token for client user."""
    if not settings.auth_secret:
        raise HTTPException(503, "Set AUTH_SECRET before enabling sign-in")
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "email": user.email,
            "role": "client",
            "workspace_id": None,
            "iat": now,
            "exp": now + timedelta(minutes=settings.auth_token_minutes),
        },
        settings.auth_secret,
        algorithm="HS256",
    )


def issue_user_token(user: User, workspace_id: int | None = None, role: str | None = None) -> str:
    """Issue JWT session token for either client or agency persona."""
    if not settings.auth_secret:
        raise HTTPException(503, "Set AUTH_SECRET before enabling sign-in")
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user.id),
        "user_id": user.id,
        "email": user.email,
        "role": role or user.role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.auth_token_minutes),
    }
    if workspace_id is not None:
        payload["workspace_id"] = workspace_id
    return jwt.encode(payload, settings.auth_secret, algorithm="HS256")


def set_auth_cookie(response: Response, token: str, cookie_name: str = "frameops_session") -> None:
    """Set secure HTTP-only session cookie."""
    response.set_cookie(
        cookie_name,
        token,
        max_age=settings.auth_token_minutes * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear all session cookies across both client and agency personas."""
    for cookie_name in ("frameops_session", "frameops_client_session", "frameops_portal_session"):
        response.delete_cookie(
            cookie_name,
            path="/",
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite="lax",
        )


def decode_jwt_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT token signature and expiration."""
    if not settings.auth_secret:
        raise HTTPException(503, "Set AUTH_SECRET before enabling sign-in")
    try:
        return jwt.decode(token, settings.auth_secret, algorithms=["HS256"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Session expired or invalid") from None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    frameops_client_session: str | None = Cookie(default=None),
    frameops_session: str | None = Cookie(default=None),
    frameops_portal_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Resolve authenticated User from Bearer token or session cookies."""
    token = (
        credentials.credentials
        if credentials
        else (frameops_client_session or frameops_session or frameops_portal_session)
    )
    if not token:
        raise HTTPException(401, "Sign in required")

    payload = decode_jwt_token(token)
    user_id = payload.get("user_id")
    sub = payload.get("sub")
    if user_id is None and sub is not None:
        if isinstance(sub, int):
            user_id = sub
        elif isinstance(sub, str) and not sub.startswith("client:") and sub.isdigit():
            user_id = int(sub)

    if user_id is None:
        raise HTTPException(401, "Session expired or invalid")

    user = db.get(User, int(user_id))
    if not user:
        raise HTTPException(401, "User not found or account inactive")
    return user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    frameops_client_session: str | None = Cookie(default=None),
    frameops_session: str | None = Cookie(default=None),
    frameops_portal_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    """Resolve optional User from Bearer token or session cookies without raising 401."""
    token = (
        credentials.credentials
        if credentials
        else (frameops_client_session or frameops_session or frameops_portal_session)
    )
    if not token:
        return None
    try:
        payload = decode_jwt_token(token)
        user_id = payload.get("user_id")
        sub = payload.get("sub")
        if user_id is None and sub is not None:
            if isinstance(sub, int):
                user_id = sub
            elif isinstance(sub, str) and not sub.startswith("client:") and sub.isdigit():
                user_id = int(sub)
        if user_id is None:
            return None
        return db.get(User, int(user_id))
    except Exception:
        return None


def current_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    frameops_session: str | None = Cookie(default=None),
    frameops_client_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> tuple[User, int, str]:
    """Agency identity dependency. Preserves (User, workspace_id, role) tuple signature."""
    token = credentials.credentials if credentials else (frameops_session or frameops_client_session)
    if not token:
        raise HTTPException(401, "Sign in required")

    payload = decode_jwt_token(token)
    role = payload.get("role")
    workspace_id = payload.get("workspace_id")

    if role == "client" and workspace_id is None:
        raise HTTPException(403, "Access restricted to agency workspace members")

    sub = payload.get("sub", "")
    user_id = payload.get("user_id") or (int(sub) if isinstance(sub, str) and sub.isdigit() else None)
    if not user_id:
        raise HTTPException(401, "Session expired or invalid")

    user = db.get(User, int(user_id))
    if not user:
        raise HTTPException(401, "User not found")

    if user.role == "client" and workspace_id is None:
        raise HTTPException(403, "Access restricted to agency workspace members")

    if workspace_id is None:
        raise HTTPException(401, "Workspace membership is no longer active")

    member = db.query(Membership).filter_by(user_id=int(user_id), workspace_id=int(workspace_id)).first()
    if not member:
        if user.role == "client":
            raise HTTPException(403, "Access restricted to agency workspace members")
        raise HTTPException(401, "Workspace membership is no longer active")

    return user, int(workspace_id), member.role


def require_client_role(current_user: User = Depends(get_current_user)) -> User:
    """RBAC Guard: Restricts endpoint access strictly to client users."""
    if current_user.role != "client":
        raise HTTPException(403, "Client role required")
    return current_user


def require_agency_role(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> tuple[User, int, str]:
    """RBAC Guard: Restricts endpoint access to agency owners and members."""
    if current_user.role not in ("agency_owner", "agency_member"):
        raise HTTPException(403, "Agency role required")
    member = db.query(Membership).filter_by(user_id=current_user.id).order_by(Membership.id).first()
    if not member:
        raise HTTPException(403, "No active workspace membership found")
    return current_user, member.workspace_id, member.role


def require_workspace_owner(
    workspace_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> tuple[User, int, str]:
    """RBAC Guard: Restricts endpoint access to workspace owners."""
    if current_user.role not in ("agency_owner", "agency_member"):
        raise HTTPException(403, "Agency role required")
    if workspace_id is not None:
        member = db.query(Membership).filter_by(user_id=current_user.id, workspace_id=workspace_id).first()
    else:
        member = db.query(Membership).filter_by(user_id=current_user.id).order_by(Membership.id).first()
    if not member or member.role != "owner":
        raise HTTPException(403, "Workspace owner role required")
    return current_user, member.workspace_id, member.role


def issue_client_token(client: Client) -> str:
    """Issue legacy client portal JWT token (backward compatibility)."""
    if not settings.auth_secret:
        raise HTTPException(503, "Set AUTH_SECRET before enabling sign-in")
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": f"client:{client.id}",
            "client_id": client.id,
            "workspace_id": client.workspace_id,
            "role": "client",
            "iat": now,
            "exp": now + timedelta(days=30),
        },
        settings.auth_secret,
        algorithm="HS256",
    )


def current_client_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    frameops_portal_session: str | None = Cookie(default=None),
    x_portal_token: str | None = Header(default=None, alias="X-Portal-Token"),
    db: Session = Depends(get_db),
) -> tuple[Client, int]:
    """Client portal authentication dependency for video review endpoints (preserved)."""
    token = credentials.credentials if credentials else (frameops_portal_session or x_portal_token)
    if not token:
        raise HTTPException(401, "Client portal authentication required")

    portal_access = db.scalar(
        select(ClientPortalAccess).where(
            ClientPortalAccess.access_token == token
        )
    )
    if portal_access:
        if not getattr(portal_access, "is_active", True):
            raise HTTPException(401, "Client portal access has been deactivated")
        expires_at = getattr(portal_access, "expires_at", None)
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at < now_utc():
                raise HTTPException(401, "Client portal access has expired")
        client = db.get(Client, portal_access.client_id)
        if client:
            portal_access.last_accessed_at = now_utc()
            db.commit()
            return client, client.workspace_id
        raise HTTPException(401, "Client account not found")

    if not settings.auth_secret:
        raise HTTPException(503, "Authentication service is not configured")
    try:
        payload = jwt.decode(token, settings.auth_secret, algorithms=["HS256"])
        client_id = int(payload["client_id"])
        workspace_id = int(payload["workspace_id"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Session expired or invalid portal token") from None

    client = db.scalar(select(Client).where(Client.id == client_id, Client.workspace_id == workspace_id))
    if not client:
        raise HTTPException(401, "Client account not found or access revoked")
    return client, workspace_id
