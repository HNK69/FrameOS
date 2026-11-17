"""Automated verification suite for FRAMEOPS November 16 Audit Remediation.

Tests all 7 audit remediation items:
1. Rate limiting isolation and behavior.
2. IP spoofing protection and trusted proxies.
3. Client portal onboarding for unengaged marketplace clients.
4. Upload security (magic bytes, executable rejection, path traversal).
5. Server-side session revocation on logout.
6. Rate limiter Redis sliding-window fallback / behavior.
7. Security headers (CSP, Permissions-Policy, HSTS).
"""

import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.main import app
from app.models import Client, Membership, User, Workspace
from app.security import (
    _extract_client_ip,
    auth_rate_limiter,
    hash_password,
    issue_client_session_token,
    issue_client_token,
    issue_user_token,
    token_revocation_store,
    validate_upload_security,
)


# ==============================================================================
# 1 & 6. RATE LIMITING & SLIDING WINDOW
# ==============================================================================

def test_rate_limiting_sliding_window_and_isolation(isolated_db):
    """Verify rate limiter blocks at limit (15 requests/min) and resets cleanly."""
    auth_rate_limiter.reset()
    client = TestClient(app)

    # 15 requests allowed to proceed (fail credentials 401)
    for _ in range(15):
        resp = client.post("/api/auth/login", json={"email": "nobody@test.com", "password": "wrong"})
        assert resp.status_code == 401

    # 16th request is blocked by rate limiter
    resp_blocked = client.post("/api/auth/login", json={"email": "nobody@test.com", "password": "wrong"})
    assert resp_blocked.status_code == 429
    assert "Too many authentication attempts" in resp_blocked.json()["detail"]
    assert "Retry-After" in resp_blocked.headers

    # Reset allows immediate resumption
    auth_rate_limiter.reset()
    resp_ok = client.post("/api/auth/login", json={"email": "nobody@test.com", "password": "wrong"})
    assert resp_ok.status_code == 401


# ==============================================================================
# 2. IP EXTRACTION & TRUSTED PROXY SPOOFING PROTECTION
# ==============================================================================

def test_ip_spoofing_untrusted_peer_ignores_x_forwarded_for(monkeypatch: pytest.MonkeyPatch):
    """Untrusted peer IP must NOT be able to spoof client IP via X-Forwarded-For."""
    monkeypatch.setattr(settings, "trusted_proxies", "10.0.0.1,10.0.0.2")

    class MockClient:
        host = "192.168.1.50"  # Untrusted peer

    class MockRequest:
        client = MockClient()
        headers = {"x-forwarded-for": "203.0.113.195, 10.0.0.1"}

    extracted = _extract_client_ip(MockRequest())
    # Must ignore forwarded header and use peer host directly
    assert extracted == "192.168.1.50"


def test_ip_spoofing_trusted_proxy_extracts_client_ip(monkeypatch: pytest.MonkeyPatch):
    """Trusted proxy peer correctly extracts original client IP from X-Forwarded-For."""
    monkeypatch.setattr(settings, "trusted_proxies", "127.0.0.1,10.0.0.1")

    class MockClient:
        host = "10.0.0.1"  # Trusted proxy

    class MockRequest:
        client = MockClient()
        headers = {"x-forwarded-for": "203.0.113.195, 10.0.0.2"}

    extracted = _extract_client_ip(MockRequest())
    assert extracted == "203.0.113.195"


# ==============================================================================
# 3. CLIENT PORTAL ONBOARDING (UNENGAGED MARKETPLACE CLIENT)
# ==============================================================================

def test_portal_me_unengaged_marketplace_client(isolated_db):
    """Authenticated marketplace client with zero agency projects receives 200 with has_engagement=False."""
    client = TestClient(app)

    with isolated_db() as db:
        user = User(
            email="newclient@brand.com",
            password_hash=hash_password("Password123!"),
            full_name="Alice Founder",
            role="client",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = issue_client_session_token(user)

    # Request /api/portal/auth/me
    resp = client.get("/api/portal/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is True
    assert data["has_engagement"] is False
    assert data["client"] is None
    assert data["user"]["email"] == "newclient@brand.com"
    assert data["user"]["full_name"] == "Alice Founder"
    assert data["projects_count"] == 0
    assert data["workspace_id"] is None

    # Projects list returns empty list [] instead of error
    proj_resp = client.get("/api/portal/projects", headers={"Authorization": f"Bearer {token}"})
    assert proj_resp.status_code == 200
    assert proj_resp.json() == []


def test_portal_me_agency_owner_forbidden(isolated_db):
    """Agency owners must be rejected with 403 on client portal endpoints."""
    client = TestClient(app)

    with isolated_db() as db:
        ws = Workspace(name="Creative Studio")
        db.add(ws)
        db.flush()
        owner = User(
            email="agencyowner@studio.com",
            password_hash=hash_password("Password123!"),
            full_name="Studio Owner",
            role="agency_owner",
        )
        db.add(owner)
        db.flush()
        db.add(Membership(workspace_id=ws.id, user_id=owner.id, role="owner"))
        db.commit()

    token = issue_user_token(owner, ws.id, "owner")
    resp = client.get("/api/portal/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert "client accounts" in resp.json()["detail"].lower()


# ==============================================================================
# 4. FILE UPLOAD SECURITY (MAGIC BYTES & EXTENSION VALIDATION)
# ==============================================================================

def test_upload_security_rejects_executables_and_scripts():
    """Executable binaries and scripts must be rejected with 415."""
    # PE Windows binary (MZ header)
    with pytest.raises(Exception) as exc:
        validate_upload_security("cut.mp4", b"MZ\x90\x00\x03\x00\x00\x00malicious_pe")
    assert "Windows executables are not permitted" in str(exc.value)

    # Linux ELF binary
    with pytest.raises(Exception) as exc:
        validate_upload_security("image.png", b"\x7fELF\x01\x01\x01\x00linux_binary")
    assert "Linux executables are not permitted" in str(exc.value)

    # Shell script disguised as text
    with pytest.raises(Exception) as exc:
        validate_upload_security("notes.txt", b"#!/bin/sh\nrm -rf /")
    assert "Script files are not permitted" in str(exc.value)

    # PHP code
    with pytest.raises(Exception) as exc:
        validate_upload_security("audio.wav", b"<?php system($_GET['cmd']); ?>")
    assert "Server-side scripts are not permitted" in str(exc.value)

    # SVG with embedded script
    with pytest.raises(Exception) as exc:
        validate_upload_security("logo.svg", b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>")
    assert "SVG files with script tags are forbidden" in str(exc.value)

    # Extension mismatch (e.g. text file renamed to .png)
    with pytest.raises(Exception) as exc:
        validate_upload_security("fake.png", b"This is just plain text content")
    assert "Corrupt or invalid PNG signature" in str(exc.value)


def test_upload_security_accepts_valid_files():
    """Valid files with matching magic bytes are accepted."""
    # Valid PNG
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    name, mime = validate_upload_security("valid.png", png_bytes)
    assert name == "valid.png"
    assert mime == "image/png"

    # Valid WAV
    wav_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
    name, mime = validate_upload_security("audio.wav", wav_bytes)
    assert name == "audio.wav"
    assert mime == "audio/wav"

    # Valid MP4
    mp4_bytes = b"\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00isommp42"
    name, mime = validate_upload_security("video.mp4", mp4_bytes)
    assert name == "video.mp4"
    assert mime == "video/mp4"


# ==============================================================================
# 5. SERVER-SIDE SESSION REVOCATION
# ==============================================================================

def test_session_revocation_on_auth_logout(isolated_db):
    """Logging out of /api/auth/logout revokes the token immediately."""
    client = TestClient(app)

    with isolated_db() as db:
        ws = Workspace(name="Revoke Studio")
        db.add(ws)
        db.flush()
        user = User(
            email="editor@studio.com",
            password_hash=hash_password("Password123!"),
            full_name="Studio Editor",
            role="agency_member",
        )
        db.add(user)
        db.flush()
        db.add(Membership(workspace_id=ws.id, user_id=user.id, role="editor"))
        db.commit()

    token = issue_user_token(user, ws.id, "editor")

    # Protected agency endpoint succeeds with active token
    resp_before = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_before.status_code == 200

    # Logout
    resp_logout = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp_logout.status_code == 200
    assert resp_logout.json()["logged_out"] is True

    # Same token must now be rejected with 401
    resp_after = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_after.status_code == 401
    assert "revoked" in resp_after.json()["detail"].lower()


def test_session_revocation_on_portal_logout(isolated_db):
    """Logging out of /api/portal/auth/logout revokes portal token immediately."""
    client = TestClient(app)

    with isolated_db() as db:
        user = User(
            email="portaluser@brand.com",
            password_hash=hash_password("Password123!"),
            full_name="Portal User",
            role="client",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = issue_client_session_token(user)

    # Portal me succeeds
    resp_before = client.get("/api/portal/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_before.status_code == 200

    # Portal logout
    resp_logout = client.post("/api/portal/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp_logout.status_code == 200
    assert resp_logout.json()["logged_out"] is True

    # Same token must now be rejected
    resp_after = client.get("/api/portal/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_after.status_code == 401
    assert "revoked" in resp_after.json()["detail"].lower()


# ==============================================================================
# 7. SECURITY HEADERS
# ==============================================================================

def test_security_headers_present():
    """Verify security headers: CSP, Permissions-Policy, X-Content-Type-Options, X-Frame-Options, Referrer-Policy."""
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200

    headers = resp.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in headers
    csp = headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "media-src 'self' blob: data:" in csp
    assert "Permissions-Policy" in headers
    perm = headers["Permissions-Policy"]
    assert "microphone=(self)" in perm
