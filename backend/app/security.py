"""Security, Password Hashing, JWT Sessions & RBAC Guards for FRAMEOPS."""

import hashlib
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Client, ClientPortalAccess, Membership, Project, ProjectRequest, User, Workspace, now_utc

password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


def _extract_client_ip(request: Request) -> str:
    """Extract client IP, verifying X-Forwarded-For strictly if request originates from a trusted proxy."""
    peer_ip = request.client.host if request.client else "127.0.0.1"
    trusted_raw = getattr(settings, "trusted_proxies", "127.0.0.1,::1")
    trusted_proxies = [p.strip() for p in trusted_raw.split(",") if p.strip()]

    if peer_ip in trusted_proxies:
        forwarded = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return peer_ip


class InMemoryRateLimiter:
    """Thread-safe sliding window rate limiter keyed by client IP and action."""

    def __init__(self, requests_limit: int = 15, window_seconds: int = 60):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self._history: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check_with_ip(
        self,
        client_ip: str,
        endpoint_key: str = "auth",
        limit: int | None = None,
        window: int | None = None,
    ) -> None:
        key = f"{client_ip}:{endpoint_key}"
        now = time.time()
        max_reqs = limit if limit is not None else self.requests_limit
        win = window if window is not None else self.window_seconds

        with self._lock:
            # Retain only timestamps within the rolling window
            timestamps = [t for t in self._history[key] if now - t < win]
            if len(timestamps) >= max_reqs:
                retry_after = int(win - (now - timestamps[0])) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many authentication attempts. Please try again later.",
                    headers={"Retry-After": str(max(1, retry_after))},
                )
            timestamps.append(now)
            self._history[key] = timestamps

    def check(
        self,
        request: Request,
        endpoint_key: str = "auth",
        limit: int | None = None,
        window: int | None = None,
    ) -> None:
        client_ip = _extract_client_ip(request)
        self.check_with_ip(client_ip, endpoint_key, limit=limit, window=window)

    def reset(self) -> None:
        with self._lock:
            self._history.clear()


class DistributedRateLimiter:
    """Rate limiter supporting optional Redis cluster with in-memory fallback."""

    def __init__(self, requests_limit: int = 15, window_seconds: int = 60):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self._fallback = InMemoryRateLimiter(requests_limit=requests_limit, window_seconds=window_seconds)
        self._redis_client = None
        self._redis_tested = False

    def _get_redis(self):
        if not self._redis_tested:
            self._redis_tested = True
            redis_url = getattr(settings, "redis_url", "")
            if redis_url:
                try:
                    import redis
                    r = redis.from_url(redis_url, decode_responses=True)
                    r.ping()
                    self._redis_client = r
                except Exception:
                    self._redis_client = None
        return self._redis_client

    def check(
        self,
        request: Request,
        endpoint_key: str = "auth",
        limit: int | None = None,
        window: int | None = None,
    ) -> None:
        client_ip = _extract_client_ip(request)
        max_reqs = limit if limit is not None else self.requests_limit
        win = window if window is not None else self.window_seconds
        r = self._get_redis()

        if r is not None:
            try:
                key = f"rl:{client_ip}:{endpoint_key}"
                now = time.time()
                pipeline = r.pipeline()
                pipeline.zremrangebyscore(key, 0, now - win)
                pipeline.zcard(key)
                pipeline.zadd(key, {f"{now}:{uuid4().hex[:6]}": now})
                pipeline.expire(key, win + 1)
                res = pipeline.execute()
                current_count = res[1]
                if current_count >= max_reqs:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Too many authentication attempts. Please try again later.",
                        headers={"Retry-After": str(win)},
                    )
                return
            except HTTPException:
                raise
            except Exception:
                pass

        self._fallback.check_with_ip(client_ip, endpoint_key, limit=max_reqs, window=win)

    def reset(self) -> None:
        self._fallback.reset()
        r = self._get_redis()
        if r is not None:
            try:
                keys = r.keys("rl:*")
                if keys:
                    r.delete(*keys)
            except Exception:
                pass


auth_rate_limiter = DistributedRateLimiter(requests_limit=15, window_seconds=60)


def rate_limit_auth(request: Request) -> None:
    """Dependency that applies sliding-window IP rate limiting to auth endpoints."""
    auth_rate_limiter.check(request, endpoint_key="auth")


class TokenRevocationStore:
    """Thread-safe store for revoked JWT IDs and token signatures."""

    def __init__(self):
        self._revoked: dict[str, float] = {}  # token_ident -> exp
        self._lock = Lock()

    def revoke(self, token: str) -> None:
        if not token:
            return
        now = time.time()
        exp = now + 86400 * 30
        ident = hashlib.sha256(token.encode("utf-8")).hexdigest()
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            if "exp" in payload:
                exp = float(payload["exp"])
            if "jti" in payload:
                ident = str(payload["jti"])
        except Exception:
            pass

        with self._lock:
            self._revoked = {k: v for k, v in self._revoked.items() if v > now}
            self._revoked[ident] = exp

    def is_revoked(self, token: str, payload: dict[str, Any] | None = None) -> bool:
        if not token:
            return False
        now = time.time()
        ident = hashlib.sha256(token.encode("utf-8")).hexdigest()
        jti = payload.get("jti") if payload else None

        with self._lock:
            if jti and jti in self._revoked:
                if self._revoked[jti] > now:
                    return True
            if ident in self._revoked:
                if self._revoked[ident] > now:
                    return True
        return False

    def reset(self) -> None:
        with self._lock:
            self._revoked.clear()


token_revocation_store = TokenRevocationStore()


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
            "jti": uuid4().hex,
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
            "jti": uuid4().hex,
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
        "jti": uuid4().hex,
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
    """Decode and validate JWT token signature and expiration, checking revocation."""
    if not settings.auth_secret:
        raise HTTPException(503, "Set AUTH_SECRET before enabling sign-in")
    try:
        payload = jwt.decode(token, settings.auth_secret, algorithms=["HS256"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Session expired or invalid") from None

    if token_revocation_store.is_revoked(token, payload):
        raise HTTPException(401, "Session has been revoked. Please sign in again.")
    return payload


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
            "jti": uuid4().hex,
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


def resolve_portal_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    frameops_portal_session: str | None = Cookie(default=None),
    frameops_client_session: str | None = Cookie(default=None),
    x_portal_token: str | None = Header(default=None, alias="X-Portal-Token"),
    db: Session = Depends(get_db),
) -> tuple[Client | None, int | None, User | None]:
    """Client portal authentication and identity resolution dependency.
    Enforces that:
    1. Only guest portal tokens/passcodes OR client users (role == 'client') can authenticate.
    2. Agency owners / editors (role != 'client') are strictly forbidden (HTTP 403).
    3. Unauthenticated requests are rejected (HTTP 401).
    4. Authenticated marketplace clients without an active agency project return (None, None, user).
    """
    token = credentials.credentials if credentials else (
        frameops_portal_session or x_portal_token or frameops_client_session
    )
    if not token:
        raise HTTPException(401, "Client portal authentication required")

    # 1. Direct match on ClientPortalAccess token (passcode login / guest link)
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
            client._auth_user = None
            return client, client.workspace_id, None
        raise HTTPException(401, "Client account not found")

    # 2. Decode JWT and check revocation
    if not settings.auth_secret:
        raise HTTPException(503, "Authentication service is not configured")
    try:
        payload = decode_jwt_token(token)
    except HTTPException:
        raise
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Session expired or invalid portal token") from None

    # Case A: Legacy portal token with client_id and workspace_id
    if "client_id" in payload and "workspace_id" in payload and payload.get("role") == "client":
        client_id = int(payload["client_id"])
        workspace_id = int(payload["workspace_id"])
        client = db.scalar(select(Client).where(Client.id == client_id, Client.workspace_id == workspace_id))
        if not client:
            raise HTTPException(401, "Client account not found or access revoked")
        client._auth_user = None
        return client, workspace_id, None

    # Case B: Platform user session
    user_id_raw = payload.get("user_id") or payload.get("sub")
    if user_id_raw:
        try:
            user_id = int(user_id_raw)
        except ValueError:
            user_id = None
        if user_id:
            user = db.get(User, user_id)
            if user:
                # STRICT SECURITY CHECK: Only client role is authorized for client portal
                if user.role != "client":
                    raise HTTPException(403, "Access forbidden: Client portal is restricted to client accounts")

                # 1. Look for an active Project linked to any of this client user's requests
                stmt = (
                    select(Project)
                    .join(ProjectRequest, Project.request_id == ProjectRequest.id)
                    .where(ProjectRequest.client_user_id == user.id)
                    .order_by(Project.created_at.desc())
                )
                project = db.scalars(stmt).first()
                if project and project.client:
                    client = project.client
                    client._auth_user = user
                    return client, project.workspace_id, user

                # 2. Look for an existing Client record explicitly linked to this user via memory_bank_id
                client = db.scalar(
                    select(Client).where(
                        or_(
                            Client.memory_bank_id.like(f"bank-client-{user.id}-%"),
                            Client.memory_bank_id.like(f"%u{user.id}-%"),
                        )
                    ).order_by(Client.id.desc())
                )
                if client:
                    client._auth_user = user
                    return client, client.workspace_id, user

                # Authenticated marketplace client with no agency engagement yet
                return None, None, user

    raise HTTPException(401, "Session expired or invalid portal token")


def current_client_identity(
    identity: tuple[Client | None, int | None, User | None] = Depends(resolve_portal_identity),
) -> tuple[Client, int]:
    """Client portal authentication dependency requiring active project/client relationship."""
    client, wid, user = identity
    if not client or wid is None:
        raise HTTPException(
            401,
            "No active agency engagement found for client. Please accept an agency proposal or enter a valid access passcode.",
        )
    return client, wid


def validate_upload_security(
    filename: str,
    content: bytes,
    allowed_categories: list[str] | None = None,
) -> tuple[str, str]:
    """Validate uploaded file against size, path traversal, malicious executable signatures,
    and magic bytes matching the file extension.
    Returns (safe_filename, validated_content_type).
    """
    if not content or len(content) == 0:
        raise HTTPException(413, "Uploaded file is empty")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, "File exceeds maximum upload size limit")

    raw_name = Path(filename or "file.bin").name
    if "\x00" in raw_name:
        raise HTTPException(400, "Invalid characters in filename")
    safe_name = raw_name[:255]

    # Immediate rejection of dangerous executable / script signatures
    if content.startswith(b"MZ"):
        raise HTTPException(415, "Security validation failed: Windows executables are not permitted")
    if content.startswith(b"\x7fELF"):
        raise HTTPException(415, "Security validation failed: Linux executables are not permitted")
    if content[:4] in (b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe"):
        raise HTTPException(415, "Security validation failed: Mach-O binaries are not permitted")
    if content.startswith(b"\xca\xfe\xba\xbe"):
        raise HTTPException(415, "Security validation failed: Java class files are not permitted")
    if content.startswith(b"#!"):
        raise HTTPException(415, "Security validation failed: Script files are not permitted")

    first_512 = content[:512].lower()
    if b"<?php" in first_512 or b"<%" in first_512:
        raise HTTPException(415, "Security validation failed: Server-side scripts are not permitted")

    ext = Path(safe_name).suffix.lower()

    # Disallowed dangerous extensions
    disallowed_extensions = {
        ".exe", ".bat", ".cmd", ".sh", ".bash", ".zsh", ".php", ".phtml",
        ".py", ".pyw", ".pl", ".cgi", ".js", ".mjs", ".vbs", ".msi", ".com",
        ".scr", ".jar", ".war", ".dll", ".so", ".dylib"
    }
    if ext in disallowed_extensions:
        raise HTTPException(415, f"Security validation failed: File extension '{ext}' is forbidden")

    if not ext:
        if b"\x00" in content[:1024]:
            raise HTTPException(415, "Binary files without an extension are not permitted")
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(415, "Non-text files without an extension are not permitted")
        return safe_name, "text/plain"

    # Image formats
    if ext == ".png":
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise HTTPException(415, "File format validation failed: Corrupt or invalid PNG signature")
        return safe_name, "image/png"
    if ext in (".jpg", ".jpeg"):
        if not content.startswith(b"\xff\xd8\xff"):
            raise HTTPException(415, "File format validation failed: Corrupt or invalid JPEG signature")
        return safe_name, "image/jpeg"
    if ext == ".webp":
        if not (content[:4] == b"RIFF" and b"WEBP" in content[:64]):
            raise HTTPException(415, "File format validation failed: Corrupt or invalid WEBP signature")
        return safe_name, "image/webp"
    if ext == ".svg":
        if b"<svg" not in first_512 and b"<?xml" not in first_512:
            raise HTTPException(415, "File format validation failed: Corrupt or invalid SVG format")
        if b"<script" in content.lower():
            raise HTTPException(415, "Security validation failed: SVG files with script tags are forbidden")
        return safe_name, "image/svg+xml"

    # Audio formats
    if ext == ".wav":
        if content.startswith(b"\x89PNG") or content.startswith(b"%PDF") or content.startswith(b"\xff\xd8"):
            raise HTTPException(415, "File format validation failed: Mismatched image/PDF signature for WAV file")
        return safe_name, "audio/wav"
    if ext == ".mp3":
        if content.startswith(b"\x89PNG") or content.startswith(b"%PDF"):
            raise HTTPException(415, "File format validation failed: Mismatched signature for MP3 file")
        return safe_name, "audio/mpeg"
    if ext == ".ogg":
        if content.startswith(b"\x89PNG") or content.startswith(b"%PDF"):
            raise HTTPException(415, "File format validation failed: Mismatched signature for OGG file")
        return safe_name, "audio/ogg"
    if ext == ".flac":
        if not content.startswith(b"fLaC"):
            raise HTTPException(415, "File format validation failed: Corrupt or invalid FLAC signature")
        return safe_name, "audio/flac"

    # Video & Video/Audio containers
    if ext in (".mp4", ".mov", ".m4a"):
        if content.startswith(b"\x89PNG") or content.startswith(b"%PDF") or content.startswith(b"\xff\xd8"):
            raise HTTPException(415, "File format validation failed: Mismatched signature for MP4/MOV container")
        mime = "audio/mp4" if ext == ".m4a" else ("video/quicktime" if ext == ".mov" else "video/mp4")
        return safe_name, mime
    if ext in (".webm", ".mkv"):
        if content.startswith(b"\x89PNG") or content.startswith(b"%PDF"):
            raise HTTPException(415, "File format validation failed: Mismatched signature for WebM/MKV")
        return safe_name, "video/webm"

    # Document formats
    if ext == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(415, "File format validation failed: Corrupt or invalid PDF signature")
        return safe_name, "application/pdf"
    if ext in (".txt", ".md", ".json"):
        if b"\x00" in content[:1024]:
            raise HTTPException(415, "File format validation failed: Binary content in text document")
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(415, "File format validation failed: Document is not valid UTF-8 text")
        mime = "application/json" if ext == ".json" else ("text/markdown" if ext == ".md" else "text/plain")
        return safe_name, mime

    # Fonts
    if ext in (".woff", ".woff2"):
        if ext == ".woff" and not content.startswith(b"wOFF"):
            raise HTTPException(415, "File format validation failed: Invalid WOFF font signature")
        if ext == ".woff2" and not content.startswith(b"wOF2"):
            raise HTTPException(415, "File format validation failed: Invalid WOFF2 font signature")
        return safe_name, f"font/{ext[1:]}"

    raise HTTPException(415, f"Unsupported file type '{ext}'")
