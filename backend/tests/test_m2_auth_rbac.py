"""Milestone 2 Specification Test Suite: Role-Aware Auth, RBAC & Tenant Isolation.

Implements the 50-test specification matrix:
- Group 1: Baseline Invariants & DB Safety (Tests 1–2)
- Group 2: Public Client Registration (Tests 3–9)
- Group 3: Public Agency Registration (Tests 10–16)
- Group 4: Role-Aware Login (Tests 17–22)
- Group 5: Logout & Cookie Invalidation (Tests 23–25)
- Group 6: Current User /api/me Identity (Tests 26–31)
- Group 7: RBAC Security Guards (Tests 32–40)
- Group 8: Cross-Tenant Isolation (Tests 41–45)
- Group 9: Backwards Compatibility (Tests 46–50)
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.db import get_db
from app.main import app
from app.models import (
    AgencyProfile,
    Client,
    ClientPortalAccess,
    ClientProfile,
    Membership,
    Project,
    User,
    Workspace,
    now_utc,
)
from app.security import (
    hash_password,
    issue_client_session_token,
    issue_token,
    require_agency_role,
    require_client_role,
    require_workspace_owner,
)

# Test-specific RBAC testing endpoints
rbac_test_router = APIRouter(prefix="/api/test-rbac", tags=["test-rbac"])


@rbac_test_router.get("/client-only")
def _test_client_only(user: User = Depends(require_client_role)) -> dict[str, Any]:
    return {"status": "ok", "user_id": user.id, "role": user.role}


@rbac_test_router.get("/agency-only")
def _test_agency_only(identity: tuple[User, int, str] = Depends(require_agency_role)) -> dict[str, Any]:
    return {"status": "ok", "user_id": identity[0].id, "workspace_id": identity[1], "role": identity[2]}


@rbac_test_router.get("/owner-only/{workspace_id}")
def _test_owner_only(workspace_id: int, identity: tuple[User, int, str] = Depends(require_workspace_owner)) -> dict[str, Any]:
    return {"status": "ok", "user_id": identity[0].id, "workspace_id": identity[1], "role": identity[2]}


# Mount RBAC test router idempotently
if not any(getattr(r, "prefix", None) == "/api/test-rbac" for r in app.routes):
    app.include_router(rbac_test_router)


# ==============================================================================
# Group 1: Baseline Invariants & DB Safety (Tests 1–2)
# ==============================================================================

def test_baseline_144_records_invariants():
    """Test 1: Verify exactly 144 operational records and PRAGMA integrity in active database."""
    if os.path.exists("frameops_rehearse.db"):
        prod_path = "frameops_rehearse.db"
    elif os.path.exists("backend/frameops_rehearse.db"):
        prod_path = "backend/frameops_rehearse.db"
    elif os.path.exists("backend/frameops.db"):
        prod_path = "backend/frameops.db"
    else:
        prod_path = "frameops.db"
    assert os.path.isfile(prod_path), f"Database not found at {prod_path}"

    con = sqlite3.connect(f"file:{prod_path}?mode=ro", uri=True)
    cur = con.cursor()

    integrity = cur.execute("PRAGMA integrity_check").fetchall()
    assert integrity == [("ok",)], f"Integrity check failed: {integrity}"

    fk_check = cur.execute("PRAGMA foreign_key_check").fetchall()
    assert fk_check == [], f"Foreign key check violations: {fk_check}"

    tables = [
        "users",
        "workspaces",
        "clients",
        "projects",
        "transcripts",
        "processing_runs",
        "extracted_items",
        "memory_operations",
        "memberships",
    ]
    counts = {t: cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    assert counts == {
        "users": 1,
        "workspaces": 1,
        "clients": 9,
        "projects": 13,
        "transcripts": 16,
        "processing_runs": 16,
        "extracted_items": 56,
        "memory_operations": 31,
        "memberships": 1,
    }
    assert sum(counts.values()) == 144, f"Expected 144 baseline records, found {sum(counts.values())}"

    user1 = cur.execute("SELECT id, email, role FROM users WHERE id = 1").fetchone()
    assert user1 is not None
    assert user1[1] == "hnkrupaal@gmail.com"
    assert user1[2] == "agency_owner"

    con.close()


def test_isolated_db_does_not_mutate_frameops_db(isolated_db):
    """Test 2: Operations in isolated_db never alter the active database SHA-256."""
    prod_path = "backend/frameops.db" if os.path.exists("backend/frameops.db") else "frameops.db"
    with open(prod_path, "rb") as f:
        initial_sha = hashlib.sha256(f.read()).hexdigest()

    with isolated_db() as db:
        user = User(
            email="isolated_test_user@example.com",
            password_hash=hash_password("Pass1234!"),
            role="client",
            full_name="Isolated User",
        )
        db.add(user)
        db.commit()

    with open(prod_path, "rb") as f:
        final_sha = hashlib.sha256(f.read()).hexdigest()

    assert initial_sha == final_sha, "Active database was modified during isolated test execution!"


# ==============================================================================
# Group 2: Public Client Registration (Tests 3–9)
# ==============================================================================

def test_client_register_happy_path(isolated_db):
    """Test 3: Public client registration creates User, ClientProfile, and returns 201."""
    payload = {
        "email": "client_reg_happy@example.com",
        "password": "Password123!",
        "full_name": "Happy Client",
        "company_name": "Happy Corp",
    }
    with TestClient(app) as client:
        resp = client.post("/api/auth/register/client", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] > 0
        assert data["email"] == "client_reg_happy@example.com"
        assert data["role"] == "client"
        assert data["full_name"] == "Happy Client"
        assert data["workspace_id"] is None
        assert "frameops_client_session" in resp.cookies

        with isolated_db() as db:
            u = db.scalar(select(User).where(User.email == "client_reg_happy@example.com"))
            assert u is not None
            assert u.role == "client"
            assert u.client_profile is not None
            assert u.client_profile.company_name == "Happy Corp"


def test_client_register_duplicate_client_email(isolated_db):
    """Test 4: Registering with an existing client email returns 409 Conflict."""
    with isolated_db() as db:
        u = User(
            email="existing_c@example.com",
            password_hash=hash_password("Password123!"),
            full_name="Existing Client",
            role="client",
        )
        db.add(u)
        db.commit()

    payload = {
        "email": "existing_c@example.com",
        "password": "NewPassword123!",
        "full_name": "Another Person",
        "company_name": "Another Corp",
    }
    with TestClient(app) as client:
        resp = client.post("/api/auth/register/client", json=payload)
        assert resp.status_code == 409
        assert "already registered" in resp.text.lower()


def test_client_register_duplicate_agency_email(isolated_db):
    """Test 5: Registering client with an existing agency email returns 409 Conflict."""
    with isolated_db() as db:
        u = User(
            email="agency_exists@example.com",
            password_hash=hash_password("Password123!"),
            full_name="Agency User",
            role="agency_owner",
        )
        db.add(u)
        db.commit()

    payload = {
        "email": "agency_exists@example.com",
        "password": "Password123!",
        "full_name": "Attempt Client",
        "company_name": "Attempt Corp",
    }
    with TestClient(app) as client:
        resp = client.post("/api/auth/register/client", json=payload)
        assert resp.status_code == 409


def test_client_register_short_password():
    """Test 6: Client password < 8 characters returns 422."""
    payload = {
        "email": "shortpw@example.com",
        "password": "short",
        "full_name": "Short Pw",
        "company_name": "Short Inc",
    }
    with TestClient(app) as client:
        resp = client.post("/api/auth/register/client", json=payload)
        assert resp.status_code == 422


def test_client_register_invalid_email_format():
    """Test 7: Client invalid email format returns 422."""
    payload = {
        "email": "not-an-email",
        "password": "Password123!",
        "full_name": "Invalid Email",
        "company_name": "Invalid Inc",
    }
    with TestClient(app) as client:
        resp = client.post("/api/auth/register/client", json=payload)
        assert resp.status_code == 422


def test_client_register_missing_fields():
    """Test 8: Client registration missing required full_name returns 422."""
    payload = {
        "email": "missing_fn@example.com",
        "password": "Password123!",
        "company_name": "No Name Inc",
    }
    with TestClient(app) as client:
        resp = client.post("/api/auth/register/client", json=payload)
        assert resp.status_code == 422


def test_client_register_empty_company_name_allowed(isolated_db):
    """Test 9: Client registration with empty company_name succeeds with 201."""
    payload = {
        "email": "nocompany@example.com",
        "password": "Password123!",
        "full_name": "Independent Creator",
        "company_name": "",
    }
    with TestClient(app) as client:
        resp = client.post("/api/auth/register/client", json=payload)
        assert resp.status_code == 201
        assert resp.json()["role"] == "client"


# ==============================================================================
# Group 3: Public Agency Registration (Tests 10–16)
# ==============================================================================

def test_agency_register_happy_path(isolated_db):
    """Test 10: Public agency registration creates User, Workspace, Membership, AgencyProfile."""
    payload = {
        "email": "apex@apexstudio.com",
        "password": "Password123!",
        "full_name": "Apex Owner",
        "agency_name": "Apex Creative Studio",
    }
    with TestClient(app) as client:
        resp = client.post("/api/auth/register/agency", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] > 0
        assert data["email"] == "apex@apexstudio.com"
        assert data["role"] == "agency_owner"
        assert data["workspace_id"] > 0
        assert "frameops_session" in resp.cookies

        with isolated_db() as db:
            u = db.scalar(select(User).where(User.email == "apex@apexstudio.com"))
            assert u is not None
            assert u.role == "agency_owner"
            ws = db.get(Workspace, data["workspace_id"])
            assert ws is not None
            assert ws.name == "Apex Creative Studio"
            mem = db.query(Membership).filter_by(user_id=u.id, workspace_id=ws.id).first()
            assert mem is not None
            assert mem.role == "owner"
            ap = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == ws.id))
            assert ap is not None
            assert ap.is_published is False


def test_agency_register_duplicate_agency_email(isolated_db):
    """Test 11: Registering agency with existing email returns 409 Conflict."""
    with isolated_db() as db:
        u = User(
            email="existing_agency@example.com",
            password_hash=hash_password("Password123!"),
            full_name="Existing Agency",
            role="agency_owner",
        )
        db.add(u)
        db.commit()

    payload = {
        "email": "existing_agency@example.com",
        "password": "Password123!",
        "full_name": "Duplicate Owner",
        "agency_name": "Duplicate Studio",
    }
    with TestClient(app) as client:
        resp = client.post("/api/auth/register/agency", json=payload)
        assert resp.status_code == 409


def test_agency_register_duplicate_client_email(isolated_db):
    """Test 12: Registering agency with existing client email returns 409 Conflict."""
    with isolated_db() as db:
        u = User(
            email="existing_client_for_agency@example.com",
            password_hash=hash_password("Password123!"),
            full_name="Client Person",
            role="client",
        )
        db.add(u)
        db.commit()

    payload = {
        "email": "existing_client_for_agency@example.com",
        "password": "Password123!",
        "full_name": "Attempt Owner",
        "agency_name": "Attempt Studio",
    }
    with TestClient(app) as client:
        resp = client.post("/api/auth/register/agency", json=payload)
        assert resp.status_code == 409


def test_agency_register_short_agency_name():
    """Test 13: Agency name < 2 characters returns 422."""
    payload = {
        "email": "short_agency_name@example.com",
        "password": "Password123!",
        "full_name": "Short Name",
        "agency_name": "A",
    }
    with TestClient(app) as client:
        resp = client.post("/api/auth/register/agency", json=payload)
        assert resp.status_code == 422


def test_agency_register_whitespace_trimming(isolated_db):
    """Test 14: Agency registration trims whitespace from workspace name."""
    payload = {
        "email": "trimmed_studio@example.com",
        "password": "Password123!",
        "full_name": "Trimmed Owner",
        "agency_name": "   Spaced Studio   ",
    }
    with TestClient(app) as client:
        resp = client.post("/api/auth/register/agency", json=payload)
        assert resp.status_code == 201
        ws_id = resp.json()["workspace_id"]
        with isolated_db() as db:
            ws = db.get(Workspace, ws_id)
            assert ws is not None
            assert ws.name == "Spaced Studio"


def test_agency_register_short_password():
    """Test 15: Agency password < 8 characters returns 422."""
    payload = {
        "email": "short_pw_agency@example.com",
        "password": "short",
        "full_name": "Short Pw",
        "agency_name": "Short Agency",
    }
    with TestClient(app) as client:
        resp = client.post("/api/auth/register/agency", json=payload)
        assert resp.status_code == 422


def test_agency_register_unpublished_profile_default(isolated_db):
    """Test 16: Newly registered agency profile has is_published=False and published_at=None."""
    payload = {
        "email": "unpub_profile@example.com",
        "password": "Password123!",
        "full_name": "Unpublished Owner",
        "agency_name": "Unpublished Studio",
    }
    with TestClient(app) as client:
        resp = client.post("/api/auth/register/agency", json=payload)
        assert resp.status_code == 201
        ws_id = resp.json()["workspace_id"]
        with isolated_db() as db:
            profile = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == ws_id))
            assert profile is not None
            assert profile.is_published is False
            assert profile.published_at is None


# ==============================================================================
# Group 4: Role-Aware Login (Tests 17–22)
# ==============================================================================

def test_login_agency_owner_success(isolated_db):
    """Test 17: Agency owner login succeeds and returns workspace context."""
    with isolated_db() as db:
        u = User(
            email="login_agency@example.com",
            password_hash=hash_password("AgencyPass123!"),
            full_name="Agency Login",
            role="agency_owner",
        )
        ws = Workspace(name="Login Studio")
        db.add_all([u, ws])
        db.flush()
        mem = Membership(user_id=u.id, workspace_id=ws.id, role="owner")
        db.add(mem)
        db.commit()

    with TestClient(app) as client:
        resp = client.post("/api/auth/login", json={"email": "login_agency@example.com", "password": "AgencyPass123!"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "agency_owner"
        assert data["workspace_id"] > 0
        assert "frameops_session" in resp.cookies


def test_login_client_success(isolated_db):
    """Test 18: Client login succeeds and sets frameops_client_session cookie."""
    with isolated_db() as db:
        u = User(
            email="login_client@example.com",
            password_hash=hash_password("ClientPass123!"),
            full_name="Client Login",
            role="client",
        )
        db.add(u)
        db.flush()
        cp = ClientProfile(user_id=u.id, company_name="Login Client Corp")
        db.add(cp)
        db.commit()

    with TestClient(app) as client:
        resp = client.post("/api/auth/login", json={"email": "login_client@example.com", "password": "ClientPass123!"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "client"
        assert data["workspace_id"] is None
        assert "frameops_client_session" in resp.cookies


def test_login_invalid_password(isolated_db):
    """Test 19: Login with wrong password returns 401 Unauthorized."""
    with isolated_db() as db:
        u = User(
            email="wrongpass@example.com",
            password_hash=hash_password("CorrectPass123!"),
            role="client",
        )
        db.add(u)
        db.commit()

    with TestClient(app) as client:
        resp = client.post("/api/auth/login", json={"email": "wrongpass@example.com", "password": "WrongPassword99!"})
        assert resp.status_code == 401
        assert "Invalid email or password" in resp.text


def test_login_nonexistent_email(isolated_db):
    """Test 20: Login with unregistered email returns identical 401 Unauthorized."""
    with TestClient(app) as client:
        resp = client.post("/api/auth/login", json={"email": "ghost_user@example.com", "password": "AnyPassword123!"})
        assert resp.status_code == 401
        assert "Invalid email or password" in resp.text


def test_login_case_insensitive_email(isolated_db):
    """Test 21: Login email lookup is case-insensitive."""
    with isolated_db() as db:
        u = User(
            email="case_test@example.com",
            password_hash=hash_password("Password123!"),
            role="client",
        )
        db.add(u)
        db.commit()

    with TestClient(app) as client:
        resp = client.post("/api/auth/login", json={"email": "CASE_TEST@EXAMPLE.COM", "password": "Password123!"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "client"


def test_login_missing_auth_secret_returns_503(isolated_db, monkeypatch):
    """Test 22: Login returns 503 if auth_secret is unconfigured."""
    monkeypatch.setattr(settings, "auth_secret", "")
    with isolated_db() as db:
        u = User(
            email="secret_test@example.com",
            password_hash=hash_password("Password123!"),
            role="client",
        )
        db.add(u)
        db.commit()

    with TestClient(app) as client:
        resp = client.post("/api/auth/login", json={"email": "secret_test@example.com", "password": "Password123!"})
        assert resp.status_code == 503


# ==============================================================================
# Group 5: Logout & Cookie Invalidation (Tests 23–25)
# ==============================================================================

def test_logout_agency_clears_cookie(isolated_db):
    """Test 23: Logout sets Set-Cookie with deletion attributes for frameops_session."""
    with isolated_db() as db:
        u = User(
            email="logout_agency@example.com",
            password_hash=hash_password("Pass123!"),
            role="agency_owner",
        )
        ws = Workspace(name="Logout WS")
        db.add_all([u, ws])
        db.flush()
        mem = Membership(user_id=u.id, workspace_id=ws.id, role="owner")
        db.add(mem)
        db.commit()
        token = issue_token(u, mem)

    with TestClient(app) as client:
        client.cookies.set("frameops_session", token)
        me_before = client.get("/api/me")
        assert me_before.status_code == 200

        logout_resp = client.post("/api/auth/logout")
        assert logout_resp.status_code == 200
        assert logout_resp.json()["logged_out"] is True
        set_cookies = logout_resp.headers.get_list("set-cookie")
        assert any("frameops_session" in h for h in set_cookies)


def test_logout_client_clears_cookie(isolated_db):
    """Test 24: Logout sets Set-Cookie with deletion attributes for frameops_client_session."""
    with isolated_db() as db:
        u = User(
            email="logout_client@example.com",
            password_hash=hash_password("Pass123!"),
            role="client",
        )
        db.add(u)
        db.commit()
        token = issue_client_session_token(u)

    with TestClient(app) as client:
        client.cookies.set("frameops_client_session", token)
        me_before = client.get("/api/me")
        assert me_before.status_code == 200

        logout_resp = client.post("/api/auth/logout")
        assert logout_resp.status_code == 200
        assert logout_resp.json()["logged_out"] is True
        set_cookies = logout_resp.headers.get_list("set-cookie")
        assert any("frameops_client_session" in h for h in set_cookies)


def test_logout_idempotent_unauthenticated():
    """Test 25: Unauthenticated logout call returns 200 OK safely."""
    with TestClient(app) as client:
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["logged_out"] is True


# ==============================================================================
# Group 6: Current User /api/me Identity (Tests 26–31)
# ==============================================================================

def test_me_agency_owner_cookie(isolated_db):
    """Test 26: GET /api/me with agency cookie returns workspace_id and role."""
    with isolated_db() as db:
        u = User(
            email="me_agency_c@example.com",
            password_hash=hash_password("Pass123!"),
            role="agency_owner",
        )
        ws = Workspace(name="Me Studio")
        db.add_all([u, ws])
        db.flush()
        mem = Membership(user_id=u.id, workspace_id=ws.id, role="owner")
        db.add(mem)
        db.commit()
        token = issue_token(u, mem)
        ws_id = ws.id

    with TestClient(app) as client:
        client.cookies.set("frameops_session", token)
        resp = client.get("/api/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me_agency_c@example.com"
        assert data["role"] in ("agency_owner", "owner")
        assert data["workspace_id"] == ws_id


def test_me_agency_owner_bearer(isolated_db):
    """Test 27: GET /api/me with Bearer token resolves agency owner identity."""
    with isolated_db() as db:
        u = User(
            email="me_agency_b@example.com",
            password_hash=hash_password("Pass123!"),
            role="agency_owner",
        )
        ws = Workspace(name="Bearer Studio")
        db.add_all([u, ws])
        db.flush()
        mem = Membership(user_id=u.id, workspace_id=ws.id, role="owner")
        db.add(mem)
        db.commit()
        token = issue_token(u, mem)

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.get("/api/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me_agency_b@example.com"
        assert data["role"] in ("agency_owner", "owner")


def test_me_client_cookie(isolated_db):
    """Test 28: GET /api/me with client session cookie resolves client identity."""
    with isolated_db() as db:
        u = User(
            email="me_client_c@example.com",
            password_hash=hash_password("Pass123!"),
            role="client",
        )
        db.add(u)
        db.flush()
        cp = ClientProfile(user_id=u.id, company_name="Me Client Corp")
        db.add(cp)
        db.commit()
        token = issue_client_session_token(u)

    with TestClient(app) as client:
        client.cookies.set("frameops_client_session", token)
        resp = client.get("/api/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me_client_c@example.com"
        assert data["role"] == "client"
        assert data["workspace_id"] is None
        assert data["company_name"] == "Me Client Corp"


def test_me_client_bearer(isolated_db):
    """Test 29: GET /api/me with client Bearer token resolves client identity."""
    with isolated_db() as db:
        u = User(
            email="me_client_b@example.com",
            password_hash=hash_password("Pass123!"),
            role="client",
        )
        db.add(u)
        db.commit()
        token = issue_client_session_token(u)

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.get("/api/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me_client_b@example.com"
        assert data["role"] == "client"


def test_me_unauthenticated_returns_401():
    """Test 30: GET /api/me without credentials returns 401 Unauthorized."""
    with TestClient(app) as client:
        resp = client.get("/api/me")
        assert resp.status_code == 401


def test_me_expired_token_returns_401(isolated_db):
    """Test 31: GET /api/me with expired token returns 401 Unauthorized."""
    past = datetime.now(UTC) - timedelta(hours=1)
    expired_token = jwt.encode(
        {"sub": "1", "user_id": 1, "role": "client", "exp": past},
        settings.auth_secret,
        algorithm="HS256",
    )
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {expired_token}"
        resp = client.get("/api/me")
        assert resp.status_code == 401
        assert "Session expired or invalid" in resp.text


# ==============================================================================
# Group 7: RBAC Security Guards (Tests 32–40)
# ==============================================================================

def test_require_client_role_accepts_client(isolated_db):
    """Test 32: Endpoint guarded by require_client_role allows client user."""
    with isolated_db() as db:
        u = User(email="guard_client@example.com", password_hash=hash_password("P!"), role="client")
        db.add(u)
        db.commit()
        token = issue_client_session_token(u)

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.get("/api/test-rbac/client-only")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


def test_require_client_role_rejects_agency_with_403(isolated_db):
    """Test 33: Endpoint guarded by require_client_role returns 403 for agency user."""
    with isolated_db() as db:
        u = User(email="guard_agency@example.com", password_hash=hash_password("P!"), role="agency_owner")
        ws = Workspace(name="Guard Studio")
        db.add_all([u, ws])
        db.flush()
        mem = Membership(user_id=u.id, workspace_id=ws.id, role="owner")
        db.add(mem)
        db.commit()
        token = issue_token(u, mem)

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.get("/api/test-rbac/client-only")
        assert resp.status_code == 403
        assert "Client role required" in resp.text


def test_require_client_role_rejects_unauth_with_401():
    """Test 34: Endpoint guarded by require_client_role returns 401 for unauthenticated user."""
    with TestClient(app) as client:
        resp = client.get("/api/test-rbac/client-only")
        assert resp.status_code == 401


def test_require_agency_role_accepts_agency_owner(isolated_db):
    """Test 35: require_agency_role allows agency_owner."""
    with isolated_db() as db:
        u = User(email="owner_rbac@example.com", password_hash=hash_password("P!"), role="agency_owner")
        ws = Workspace(name="Owner WS")
        db.add_all([u, ws])
        db.flush()
        mem = Membership(user_id=u.id, workspace_id=ws.id, role="owner")
        db.add(mem)
        db.commit()
        token = issue_token(u, mem)

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.get("/api/test-rbac/agency-only")
        assert resp.status_code == 200
        assert resp.json()["role"] == "owner"


def test_require_agency_role_accepts_agency_member(isolated_db):
    """Test 36: require_agency_role allows agency_member."""
    with isolated_db() as db:
        u = User(email="member_rbac@example.com", password_hash=hash_password("P!"), role="agency_member")
        ws = Workspace(name="Member WS")
        db.add_all([u, ws])
        db.flush()
        mem = Membership(user_id=u.id, workspace_id=ws.id, role="member")
        db.add(mem)
        db.commit()
        token = issue_token(u, mem)

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.get("/api/test-rbac/agency-only")
        assert resp.status_code == 200
        assert resp.json()["role"] == "member"


def test_require_agency_role_rejects_client_with_403(isolated_db):
    """Test 37: require_agency_role returns 403 Forbidden for client user."""
    with isolated_db() as db:
        u = User(email="client_blocked@example.com", password_hash=hash_password("P!"), role="client")
        db.add(u)
        db.commit()
        token = issue_client_session_token(u)

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.get("/api/test-rbac/agency-only")
        assert resp.status_code == 403
        assert "Agency role required" in resp.text


def test_require_agency_role_rejects_unauth_with_401():
    """Test 38: require_agency_role returns 401 for unauthenticated request."""
    with TestClient(app) as client:
        resp = client.get("/api/test-rbac/agency-only")
        assert resp.status_code == 401


def test_require_workspace_owner_accepts_owner(isolated_db):
    """Test 39: require_workspace_owner allows workspace owner."""
    with isolated_db() as db:
        u = User(email="true_owner@example.com", password_hash=hash_password("P!"), role="agency_owner")
        ws = Workspace(name="True WS")
        db.add_all([u, ws])
        db.flush()
        mem = Membership(user_id=u.id, workspace_id=ws.id, role="owner")
        db.add(mem)
        db.commit()
        token = issue_token(u, mem)
        ws_id = ws.id

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.get(f"/api/test-rbac/owner-only/{ws_id}")
        assert resp.status_code == 200
        assert resp.json()["role"] == "owner"


def test_require_workspace_owner_rejects_non_owner_member_with_403(isolated_db):
    """Test 40: require_workspace_owner returns 403 for member who is not owner."""
    with isolated_db() as db:
        u = User(email="editor_non_owner@example.com", password_hash=hash_password("P!"), role="agency_member")
        ws = Workspace(name="Shared WS")
        db.add_all([u, ws])
        db.flush()
        mem = Membership(user_id=u.id, workspace_id=ws.id, role="editor")
        db.add(mem)
        db.commit()
        token = issue_token(u, mem)
        ws_id = ws.id

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.get(f"/api/test-rbac/owner-only/{ws_id}")
        assert resp.status_code == 403


# ==============================================================================
# Group 8: Cross-Tenant Isolation (Tests 41–45)
# ==============================================================================

def test_client_cannot_access_agency_clients_list(isolated_db):
    """Test 41: Client user cannot access agency clients endpoint GET /api/clients (403 Forbidden)."""
    with isolated_db() as db:
        u = User(email="client_isolation1@example.com", password_hash=hash_password("P!"), role="client")
        db.add(u)
        db.commit()
        token = issue_client_session_token(u)

    with TestClient(app) as client:
        client.cookies.set("frameops_client_session", token)
        resp = client.get("/api/clients")
        assert resp.status_code == 403


def test_client_cannot_create_agency_client(isolated_db):
    """Test 42: Client user cannot POST /api/clients (403 Forbidden)."""
    with isolated_db() as db:
        u = User(email="client_isolation2@example.com", password_hash=hash_password("P!"), role="client")
        db.add(u)
        db.commit()
        token = issue_client_session_token(u)

    with TestClient(app) as client:
        client.cookies.set("frameops_client_session", token)
        resp = client.post("/api/clients", json={"name": "Intruder Corp", "brand": "Intruder"})
        assert resp.status_code == 403


def test_client_cannot_access_agency_projects_list(isolated_db):
    """Test 43: Client user cannot access agency projects endpoint GET /api/projects (403 Forbidden)."""
    with isolated_db() as db:
        u = User(email="client_isolation3@example.com", password_hash=hash_password("P!"), role="client")
        db.add(u)
        db.commit()
        token = issue_client_session_token(u)

    with TestClient(app) as client:
        client.cookies.set("frameops_client_session", token)
        resp = client.get("/api/projects")
        assert resp.status_code == 403


def test_agency_cannot_access_other_agency_client(isolated_db):
    """Test 44: Agency A cannot access Agency B's client record (404 Not Found)."""
    with isolated_db() as db:
        # Agency A
        user_a = User(email="agency_a@example.com", password_hash=hash_password("P!"), role="agency_owner")
        ws_a = Workspace(name="Workspace A")
        db.add_all([user_a, ws_a])
        db.flush()
        mem_a = Membership(user_id=user_a.id, workspace_id=ws_a.id, role="owner")
        db.add(mem_a)

        # Agency B
        user_b = User(email="agency_b@example.com", password_hash=hash_password("P!"), role="agency_owner")
        ws_b = Workspace(name="Workspace B")
        db.add_all([user_b, ws_b])
        db.flush()
        mem_b = Membership(user_id=user_b.id, workspace_id=ws_b.id, role="owner")
        db.add(mem_b)

        # Client belonging to Agency B
        client_b = Client(name="Client B", workspace_id=ws_b.id, memory_bank_id=f"bank-ws-{ws_b.id}")
        db.add(client_b)
        db.commit()

        token_a = issue_token(user_a, mem_a)
        client_b_id = client_b.id

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token_a}"
        resp = client.get(f"/api/clients/{client_b_id}")
        assert resp.status_code == 404


def test_agency_cannot_delete_other_agency_project(isolated_db):
    """Test 45: Agency A cannot delete Agency B's project (404 Not Found, project remains)."""
    with isolated_db() as db:
        # Agency A
        user_a = User(email="owner_a_del@example.com", password_hash=hash_password("P!"), role="agency_owner")
        ws_a = Workspace(name="Workspace A Del")
        db.add_all([user_a, ws_a])
        db.flush()
        mem_a = Membership(user_id=user_a.id, workspace_id=ws_a.id, role="owner")
        db.add(mem_a)

        # Agency B
        user_b = User(email="owner_b_del@example.com", password_hash=hash_password("P!"), role="agency_owner")
        ws_b = Workspace(name="Workspace B Del")
        db.add_all([user_b, ws_b])
        db.flush()
        mem_b = Membership(user_id=user_b.id, workspace_id=ws_b.id, role="owner")
        db.add(mem_b)

        client_b = Client(name="Client B Target", workspace_id=ws_b.id, memory_bank_id=f"bank-del-{ws_b.id}")
        db.add(client_b)
        db.flush()

        proj_b = Project(name="Project B Secret", client_id=client_b.id, workspace_id=ws_b.id)
        db.add(proj_b)
        db.commit()

        token_a = issue_token(user_a, mem_a)
        proj_b_id = proj_b.id

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token_a}"
        resp = client.delete(f"/api/projects/{proj_b_id}")
        assert resp.status_code == 404

        with isolated_db() as db:
            persisted = db.get(Project, proj_b_id)
            assert persisted is not None
            assert persisted.name == "Project B Secret"


# ==============================================================================
# Group 9: Backwards Compatibility (Tests 46–50)
# ==============================================================================

def test_baseline_agency_owner_session_compat(isolated_db):
    """Test 46: Baseline user (hnkrupaal@gmail.com, workspace 1) logs in and me returns identity."""
    with isolated_db() as db:
        u = User(
            id=1,
            email="hnkrupaal@gmail.com",
            password_hash=hash_password("BaselinePass123!"),
            role="agency_owner",
            full_name="Krupaal",
        )
        ws = Workspace(id=1, name="FRAMEOPS Studio")
        db.add_all([u, ws])
        db.flush()
        mem = Membership(id=1, user_id=1, workspace_id=1, role="owner")
        db.add(mem)
        db.commit()

        token = issue_token(u, mem)

    with TestClient(app) as client:
        client.cookies.set("frameops_session", token)
        resp = client.get("/api/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "hnkrupaal@gmail.com"
        assert data["role"] in ("agency_owner", "owner")
        assert data["workspace_id"] == 1


def test_portal_token_header_auth(isolated_db):
    """Test 47: Preserves legacy portal token auth via X-Portal-Token header."""
    with isolated_db() as db:
        ws = Workspace(name="Portal Test WS")
        db.add(ws)
        db.flush()

        c = Client(name="Portal Client", workspace_id=ws.id, memory_bank_id=f"bank-portal-{ws.id}")
        db.add(c)
        db.flush()

        access = ClientPortalAccess(
            workspace_id=ws.id,
            client_id=c.id,
            access_token="test-portal-token-legacy-xyz",
            passcode="123456",
            is_active=True,
        )
        db.add(access)
        db.commit()

    with TestClient(app) as client:
        client.headers["X-Portal-Token"] = "test-portal-token-legacy-xyz"
        resp = client.get("/api/portal/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["client"]["id"] == c.id


def test_portal_token_expired_returns_401(isolated_db):
    """Test 48: Expired portal token returns 401 Unauthorized."""
    with isolated_db() as db:
        ws = Workspace(name="Expired Portal WS")
        db.add(ws)
        db.flush()

        c = Client(name="Expired Client", workspace_id=ws.id, memory_bank_id=f"bank-exp-{ws.id}")
        db.add(c)
        db.flush()

        past = now_utc() - timedelta(days=2)
        access = ClientPortalAccess(
            workspace_id=ws.id,
            client_id=c.id,
            access_token="expired-token-xyz",
            passcode="123456",
            is_active=True,
            expires_at=past,
        )
        db.add(access)
        db.commit()

    with TestClient(app) as client:
        client.headers["X-Portal-Token"] = "expired-token-xyz"
        resp = client.get("/api/portal/auth/me")
        assert resp.status_code == 401
        assert "expired" in resp.text.lower()


def test_portal_token_deactivated_returns_401(isolated_db):
    """Test 49: Deactivated portal token returns 401 Unauthorized."""
    with isolated_db() as db:
        ws = Workspace(name="Deactivated Portal WS")
        db.add(ws)
        db.flush()

        c = Client(name="Deactivated Client", workspace_id=ws.id, memory_bank_id=f"bank-deact-{ws.id}")
        db.add(c)
        db.flush()

        access = ClientPortalAccess(
            workspace_id=ws.id,
            client_id=c.id,
            access_token="deactivated-token-xyz",
            passcode="123456",
            is_active=False,
        )
        db.add(access)
        db.commit()

    with TestClient(app) as client:
        client.headers["X-Portal-Token"] = "deactivated-token-xyz"
        resp = client.get("/api/portal/auth/me")
        assert resp.status_code == 401
        assert "deactivated" in resp.text.lower()


def test_legacy_setup_endpoint_rejected_when_user_exists(isolated_db):
    """Test 50: POST /api/auth/setup returns 409 Conflict when users already exist."""
    with isolated_db() as db:
        u = User(email="setup_existing@example.com", password_hash=hash_password("Pass123!"), role="agency_owner")
        db.add(u)
        db.commit()

    payload = {
        "email": "another_owner@example.com",
        "password": "Password123456!",
        "workspace_name": "Second Studio",
    }
    with TestClient(app) as client:
        resp = client.post("/api/auth/setup", json=payload)
        assert resp.status_code == 409
        assert "Initial owner is already configured" in resp.text
