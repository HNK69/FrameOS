from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Cookie, Depends, Header, HTTPException
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
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def issue_token(user: User, membership: Membership) -> str:
    if not settings.auth_secret:
        raise HTTPException(503, "Set AUTH_SECRET before enabling sign-in")
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(user.id), "workspace_id": membership.workspace_id,
         "role": membership.role, "iat": now, "exp": now + timedelta(minutes=settings.auth_token_minutes)},
        settings.auth_secret,
        algorithm="HS256",
    )


def current_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    frameops_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> tuple[User, int, str]:
    token = credentials.credentials if credentials else frameops_session
    if not token or not settings.auth_secret:
        raise HTTPException(401, "Sign in required")
    try:
        payload = jwt.decode(token, settings.auth_secret, algorithms=["HS256"])
        user_id, workspace_id = int(payload["sub"]), int(payload["workspace_id"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Session expired or invalid") from None
    user = db.get(User, user_id)
    member = db.query(Membership).filter_by(user_id=user_id, workspace_id=workspace_id).first()
    if not user or not member:
        raise HTTPException(401, "Workspace membership is no longer active")
    return user, workspace_id, member.role


def issue_client_token(client: Client) -> str:
    if not settings.auth_secret:
        raise HTTPException(503, "Set AUTH_SECRET before enabling sign-in")
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": f"client:{client.id}", "client_id": client.id, "workspace_id": client.workspace_id,
         "role": "client", "iat": now, "exp": now + timedelta(days=30)},
        settings.auth_secret,
        algorithm="HS256",
    )


def current_client_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    frameops_portal_session: str | None = Cookie(default=None),
    x_portal_token: str | None = Header(default=None, alias="X-Portal-Token"),
    db: Session = Depends(get_db),
) -> tuple[Client, int]:
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
