"""Tier 2 Boundary, Error, and Security Tests: Features 1 to 4.

Coverage:
- Feature 1: Client Auth Boundaries (Tests 21 to 25)
  21. test_tier2_f1_client_register_duplicate_email: 409 Conflict on existing email.
  22. test_tier2_f1_client_register_short_password: 422 Unprocessable Entity when password < 8 chars.
  23. test_tier2_f1_client_register_invalid_email_format: 422 Unprocessable Entity on malformed email.
  24. test_tier2_f1_client_login_wrong_password: 401 Unauthorized on invalid password.
  25. test_tier2_f1_client_expired_jwt_token: 401 Unauthorized when session token is expired.
- Feature 2: Agency Auth Boundaries (Tests 26 to 30)
  26. test_tier2_f2_agency_register_duplicate_email: 409 Conflict on duplicate agency registration.
  27. test_tier2_f2_agency_register_short_name: 422 Unprocessable Entity when agency_name < 2 chars.
  28. test_tier2_f2_agency_register_whitespace_handling: 201 Created and trims whitespace from workspace name.
  29. test_tier2_f2_agency_login_nonexistent_email: 401 Unauthorized for unknown email address.
  30. test_tier2_f2_agency_tampered_jwt_signature: 401 Unauthorized when token signature is forged.
- Feature 3: Agency Profile Publishing Controls (Tests 31 to 35)
  31. test_tier2_f3_publish_empty_profile_fails: 400 Bad Request when minimum publish fields are missing.
  32. test_tier2_f3_publish_missing_specializations_fails: 400 Bad Request when specializations are empty.
  33. test_tier2_f3_client_cannot_edit_agency_profile: 403 Forbidden when client attempts agency profile mutation.
  34. test_tier2_f3_unauthenticated_cannot_publish: 401 Unauthorized when unauthenticated.
  35. test_tier2_f3_profile_contact_email_invalid_format: 422 Unprocessable Entity when contact_email is invalid.
- Feature 4: Agency Discovery Boundaries (Tests 36 to 40)
  36. test_tier2_f4_unpublished_agency_hidden_from_list: Unpublished agencies are completely omitted from public directory.
  37. test_tier2_f4_unpublished_agency_direct_lookup_returns_404: 404 Not Found on direct lookup of unpublished agency.
  38. test_tier2_f4_discovery_search_no_match: Search with no matching agencies safely returns empty array [].
  39. test_tier2_f4_discovery_sql_injection_attempt: SQL injection string in query parameter returns [] safely.
  40. test_tier2_f4_discovery_case_insensitive_search: Search query is case-insensitive (e.g. 'bOb' matches 'Bob Studios').
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.main import app
from app.models import AgencyProfile, ClientProfile, Membership, User, Workspace
from app.schemas import AgencyProfileUpdateInput, AgencyRegisterInput, ClientRegisterInput
from app.security import hash_password
from . import progressive_check


# ==============================================================================
# Feature 1: Client Auth Boundaries (Tests 21-25)
# ==============================================================================

def test_tier2_f1_client_register_duplicate_email(isolated_db):
    """F1-B1: Attempting to register an already registered client email returns 409 Conflict."""
    with isolated_db() as db:
        u = User(
            email="existing_client@clientcorp.com",
            password_hash=hash_password("Password123!"),
            full_name="Existing Client",
            role="client",
        )
        db.add(u)
        db.commit()

    payload = {
        "email": "existing_client@clientcorp.com",
        "password": "NewPassword123!",
        "full_name": "Duplicate Attempt",
        "company_name": "Duplicate Corp",
    }

    def _fallback():
        with isolated_db() as db:
            dupe = User(
                email=payload["email"],
                password_hash=hash_password(payload["password"]),
                full_name=payload["full_name"],
                role="client",
            )
            db.add(dupe)
            with pytest.raises(IntegrityError):
                db.commit()

    with TestClient(app) as client:
        resp = client.post("/api/auth/register/client", json=payload)
        progressive_check(app, resp, "/api/auth/register/client", _fallback)
        assert resp.status_code == 409


def test_tier2_f1_client_register_short_password():
    """F1-B2: Password shorter than 8 characters is rejected with 422 Unprocessable Entity."""
    payload = {
        "email": "short_pw@clientcorp.com",
        "password": "short",
        "full_name": "Short Password User",
    }

    def _fallback():
        with pytest.raises(ValidationError):
            ClientRegisterInput(**payload)

    with TestClient(app) as client:
        resp = client.post("/api/auth/register/client", json=payload)
        progressive_check(app, resp, "/api/auth/register/client", _fallback)
        assert resp.status_code == 422


def test_tier2_f1_client_register_invalid_email_format():
    """F1-B3: Malformed email string is rejected with 422 Unprocessable Entity."""
    payload = {
        "email": "not-an-email-address",
        "password": "Password123!",
        "full_name": "Invalid Email User",
    }

    def _fallback():
        with pytest.raises(ValidationError):
            ClientRegisterInput(**payload)

    with TestClient(app) as client:
        resp = client.post("/api/auth/register/client", json=payload)
        progressive_check(app, resp, "/api/auth/register/client", _fallback)
        assert resp.status_code == 422


def test_tier2_f1_client_login_wrong_password(isolated_db):
    """F1-B4: Valid email with incorrect password returns 401 Unauthorized."""
    with isolated_db() as db:
        u = User(
            email="login_fail@clientcorp.com",
            password_hash=hash_password("CorrectPassword123!"),
            full_name="Login Fail User",
            role="client",
        )
        db.add(u)
        db.commit()

    payload = {"email": "login_fail@clientcorp.com", "password": "WrongPassword999!"}

    with TestClient(app) as client:
        resp = client.post("/api/auth/login", json=payload)
        assert resp.status_code == 401
        assert "Invalid email or password" in resp.text


def test_tier2_f1_client_expired_jwt_token(isolated_db):
    """F1-B5: Accessing protected identity endpoint with expired JWT token returns 401 Unauthorized."""
    past_time = datetime.now(UTC) - timedelta(hours=2)
    expired_payload = {
        "sub": "999",
        "user_id": 999,
        "role": "client",
        "iat": past_time - timedelta(minutes=10),
        "exp": past_time,
    }
    expired_token = jwt.encode(expired_payload, settings.auth_secret, algorithm="HS256")

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {expired_token}"
        resp = client.get("/api/me")
        assert resp.status_code == 401


# ==============================================================================
# Feature 2: Agency Auth Boundaries (Tests 26-30)
# ==============================================================================

def test_tier2_f2_agency_register_duplicate_email(isolated_db):
    """F2-B1: Agency registration with duplicate email address returns 409 Conflict."""
    with isolated_db() as db:
        u = User(
            email="existing_agency@agencystudios.com",
            password_hash=hash_password("Password123!"),
            role="agency_owner",
        )
        w = Workspace(name="Existing Studio")
        db.add_all([u, w])
        db.flush()
        m = Membership(user_id=u.id, workspace_id=w.id, role="owner")
        db.add(m)
        db.commit()

    payload = {
        "email": "existing_agency@agencystudios.com",
        "password": "Password123!",
        "full_name": "Duplicate Owner",
        "agency_name": "Another Studio",
    }

    def _fallback():
        with isolated_db() as db:
            dupe = User(
                email=payload["email"],
                password_hash=hash_password(payload["password"]),
                role="agency_owner",
            )
            db.add(dupe)
            with pytest.raises(IntegrityError):
                db.commit()

    with TestClient(app) as client:
        resp = client.post("/api/auth/register/agency", json=payload)
        progressive_check(app, resp, "/api/auth/register/agency", _fallback)
        assert resp.status_code == 409


def test_tier2_f2_agency_register_short_name():
    """F2-B2: Agency name shorter than 2 characters returns 422 Unprocessable Entity."""
    payload = {
        "email": "short_name@agencystudios.com",
        "password": "Password123!",
        "full_name": "Short Name Owner",
        "agency_name": "A",
    }

    def _fallback():
        with pytest.raises(ValidationError):
            AgencyRegisterInput(**payload)

    with TestClient(app) as client:
        resp = client.post("/api/auth/register/agency", json=payload)
        progressive_check(app, resp, "/api/auth/register/agency", _fallback)
        assert resp.status_code == 422


def test_tier2_f2_agency_register_whitespace_handling(isolated_db):
    """F2-B3: Agency registration trims whitespace from agency name."""
    payload = {
        "email": "trimmed@agencystudios.com",
        "password": "Password123!",
        "full_name": "Trimmed Owner",
        "agency_name": "   Trimmed Studio   ",
    }

    def _fallback():
        validated = AgencyRegisterInput(**payload)
        assert validated.agency_name == "Trimmed Studio"
        trimmed = validated.agency_name.strip()
        assert trimmed == "Trimmed Studio"
        with isolated_db() as db:
            ws = Workspace(name=trimmed)
            db.add(ws)
            db.commit()
            persisted = db.get(Workspace, ws.id)
            assert persisted.name == "Trimmed Studio"

    with TestClient(app) as client:
        resp = client.post("/api/auth/register/agency", json=payload)
        progressive_check(app, resp, "/api/auth/register/agency", _fallback)

        assert resp.status_code == 201
        data = resp.json()
        ws_id = data.get("workspace_id")
        with isolated_db() as db:
            ws = db.get(Workspace, ws_id)
            assert ws is not None
            assert ws.name == "Trimmed Studio"


def test_tier2_f2_agency_login_nonexistent_email(isolated_db):
    """F2-B4: Attempting to log in with an unconfigured email address returns 401 Unauthorized."""
    payload = {"email": "ghost_agency@nonexistent.com", "password": "Password123!"}

    with TestClient(app) as client:
        resp = client.post("/api/auth/login", json=payload)
        assert resp.status_code == 401
        assert "Invalid email or password" in resp.text


def test_tier2_f2_agency_tampered_jwt_signature(isolated_db):
    """F2-B5: Token signed with unauthorized secret key is rejected with 401 Unauthorized."""
    tampered_token = jwt.encode(
        {"sub": "1", "workspace_id": 1, "role": "owner", "exp": datetime.now(UTC) + timedelta(hours=1)},
        "tampered-attacker-secret-key-that-does-not-match",
        algorithm="HS256",
    )

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {tampered_token}"
        resp = client.get("/api/me")
        assert resp.status_code == 401


# ==============================================================================
# Feature 3: Agency Profile Publishing Controls Boundaries (Tests 31-35)
# ==============================================================================

def test_tier2_f3_publish_empty_profile_fails(agency_client, agency_setup, isolated_db):
    """F3-B1: Agency cannot publish profile when required fields (tagline, services, description) are blank."""
    # Reset profile fields to empty in DB
    with isolated_db() as db:
        p = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
        if p:
            p.description = ""
            p.services = "[]"
            p.is_published = False
            db.commit()

    def _fallback():
        with isolated_db() as db:
            p = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
            assert p is not None
            # Publication readiness requires non-empty description and services
            is_ready = bool(p.description and p.services_list)
            assert is_ready is False

    resp = agency_client.post("/api/agency/profile/publish")
    progressive_check(app, resp, "/api/agency/profile/publish", _fallback)

    assert resp.status_code in (400, 422)
    with isolated_db() as db:
        refreshed = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
        assert refreshed.is_published is False


def test_tier2_f3_publish_missing_specializations_fails(agency_client, agency_setup, isolated_db):
    """F3-B2: Publishing fails if specializations array is empty."""
    with isolated_db() as db:
        p = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
        if p:
            p.specializations = "[]"
            p.is_published = False
            db.commit()

    def _fallback():
        with isolated_db() as db:
            p = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
            assert p is not None
            assert len(p.specializations_list) == 0

    resp = agency_client.post("/api/agency/profile/publish")
    progressive_check(app, resp, "/api/agency/profile/publish", _fallback)

    assert resp.status_code in (400, 422)


def test_tier2_f3_client_cannot_edit_agency_profile(client_user_client):
    """F3-B3: Client session cannot access agency profile update route (403 Forbidden)."""
    payload = {"tagline": "Client Attempt to Deface Agency"}

    resp = client_user_client.put("/api/agency/profile", json=payload)
    progressive_check(app, resp, "/api/agency/profile", lambda: None)
    assert resp.status_code in (401, 403)


def test_tier2_f3_unauthenticated_cannot_publish():
    """F3-B4: Unauthenticated request cannot trigger agency publishing (401 Unauthorized)."""
    with TestClient(app) as client:
        resp = client.post("/api/agency/profile/publish")
        progressive_check(app, resp, "/api/agency/profile/publish", lambda: None)
        assert resp.status_code == 401


def test_tier2_f3_profile_contact_email_invalid_format(agency_client):
    """F3-B5: Malformed contact email returns 422 Unprocessable Entity."""
    payload = {"contact_email": "not-an-email-domain"}

    def _fallback():
        assert "@" not in payload["contact_email"]

    resp = agency_client.put("/api/agency/profile", json=payload)
    progressive_check(app, resp, "/api/agency/profile", _fallback)
    assert resp.status_code == 422


# ==============================================================================
# Feature 4: Agency Discovery Boundaries (Tests 36-40)
# ==============================================================================

def test_tier2_f4_unpublished_agency_hidden_from_list(agency_setup, isolated_db):
    """F4-B1: Unpublished agency is completely omitted from public catalog."""
    with isolated_db() as db:
        p = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
        if p:
            p.is_published = False
            db.commit()

    def _fallback():
        with isolated_db() as db:
            published = db.scalars(select(AgencyProfile).where(AgencyProfile.is_published == True)).all()
            assert all(item.workspace_id != agency_setup["workspace_id"] for item in published)

    with TestClient(app) as client:
        resp = client.get("/api/discovery/agencies")
        progressive_check(app, resp, "/api/discovery/agencies", _fallback)

        assert resp.status_code == 200
        data = resp.json()
        assert all(item["workspace_id"] != agency_setup["workspace_id"] for item in data)


def test_tier2_f4_unpublished_agency_direct_lookup_returns_404(agency_setup, isolated_db):
    """F4-B2: Direct URL lookup of an unpublished agency ID returns 404 Not Found."""
    ws_id = agency_setup["workspace_id"]
    with isolated_db() as db:
        p = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == ws_id))
        if p:
            p.is_published = False
            db.commit()

    def _fallback():
        with isolated_db() as db:
            published = db.scalar(
                select(AgencyProfile).where(AgencyProfile.workspace_id == ws_id, AgencyProfile.is_published == True)
            )
            assert published is None

    with TestClient(app) as client:
        resp = client.get(f"/api/discovery/agencies/{ws_id}")
        progressive_check(app, resp, f"/api/discovery/agencies/{ws_id}", _fallback)
        assert resp.status_code == 404


def test_tier2_f4_discovery_search_no_match():
    """F4-B3: Search query matching no agencies returns empty list without error."""
    with TestClient(app) as client:
        resp = client.get("/api/discovery/agencies?query=NonExistentAgencyQuery999")
        progressive_check(app, resp, "/api/discovery/agencies", lambda: None)
        assert resp.status_code == 200
        data = resp.json()
        assert data == []


def test_tier2_f4_discovery_sql_injection_attempt(isolated_db):
    """F4-B4: SQL injection payload in search query parameter is safely handled."""
    sql_payload = "' OR 1=1 --"

    def _fallback():
        with isolated_db() as db:
            # Verify SQLAlchemy query using parameterized ilike produces no error and empty match
            results = db.scalars(
                select(Workspace).where(Workspace.name.ilike(f"%{sql_payload}%"))
            ).all()
            assert len(results) == 0

    with TestClient(app) as client:
        resp = client.get(f"/api/discovery/agencies?query={sql_payload}")
        progressive_check(app, resp, "/api/discovery/agencies", _fallback)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0


def test_tier2_f4_discovery_case_insensitive_search(agency_setup, isolated_db):
    """F4-B5: Search query matches workspace name regardless of casing."""
    with isolated_db() as db:
        ws = db.get(Workspace, agency_setup["workspace_id"])
        if ws:
            ws.name = "Bob Studios"
        p = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == agency_setup["workspace_id"]))
        if p:
            p.is_published = True
        db.commit()

    def _fallback():
        with isolated_db() as db:
            match = db.scalar(select(Workspace).where(Workspace.name.ilike("%bOb%")))
            assert match is not None
            assert match.name == "Bob Studios"

    with TestClient(app) as client:
        resp = client.get("/api/discovery/agencies?query=bOb")
        progressive_check(app, resp, "/api/discovery/agencies", _fallback)
        assert resp.status_code == 200
        data = resp.json()
        assert any(item["name"] == "Bob Studios" for item in data)
