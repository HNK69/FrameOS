from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Cookie, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Membership, User

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
