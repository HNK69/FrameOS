"""Isolated Security & Multi-Agency Test Suite for Client Portal.

Tests:
1. Unauthenticated access rejected (HTTP 401).
2. Agency Owner / Editor sessions strictly forbidden from client portal (HTTP 403).
3. Client user with multiple agencies accesses only their own projects across workspaces.
4. Cross-client project access is rejected (HTTP 404/403).
5. Guest passcode access is strictly scoped to that guest's client_id and workspace_id.
"""

import json
from datetime import UTC, datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import get_db
from app.main import app
from app.models import (
    AgencyProfile,
    Base,
    Client,
    ClientPortalAccess,
    Membership,
    Project,
    ProjectRequest,
    Proposal,
    User,
    Workspace,
)
from app.security import hash_password, issue_client_session_token, issue_token


@pytest.fixture
def isolated_env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(settings, "auth_secret", "test-secret-with-sufficient-entropy-1234567890")
    app.dependency_overrides[get_db] = override_get_db

    # Seed two agency workspaces and two clients
    db = TestingSession()

    # Agency 1 & Owner 1
    agency1_owner = User(email="owner1@agency1.com", password_hash=hash_password("Pass123!"), role="agency_owner", full_name="Agency One Owner")
    db.add(agency1_owner)
    db.flush()
    ws1 = Workspace(name="Agency One Creative")
    db.add(ws1)
    db.flush()
    db.add(Membership(workspace_id=ws1.id, user_id=agency1_owner.id, role="owner"))
    db.add(AgencyProfile(workspace_id=ws1.id, is_published=True, tagline="Agency 1", description="Agency 1 desc"))

    # Agency 2 & Owner 2
    agency2_owner = User(email="owner2@agency2.com", password_hash=hash_password("Pass123!"), role="agency_owner", full_name="Agency Two Owner")
    db.add(agency2_owner)
    db.flush()
    ws2 = Workspace(name="Agency Two Production")
    db.add(ws2)
    db.flush()
    db.add(Membership(workspace_id=ws2.id, user_id=agency2_owner.id, role="owner"))
    db.add(AgencyProfile(workspace_id=ws2.id, is_published=True, tagline="Agency 2", description="Agency 2 desc"))

    # Client User 1 (works with BOTH Agency 1 and Agency 2)
    client_user_1 = User(email="client1@corp.com", password_hash=hash_password("Pass123!"), role="client", full_name="Client One Exec")
    db.add(client_user_1)

    # Client User 2 (separate client)
    client_user_2 = User(email="client2@competitor.com", password_hash=hash_password("Pass123!"), role="client", full_name="Client Two Exec")
    db.add(client_user_2)
    db.commit()

    # Project 1: Client 1 with Agency 1
    c1_ws1 = Client(workspace_id=ws1.id, name=client_user_1.full_name, brand="Corp One", memory_bank_id="bank-c1-ws1")
    db.add(c1_ws1)
    db.flush()
    req_c1_ws1 = ProjectRequest(client_user_id=client_user_1.id, agency_workspace_id=ws1.id, title="Corp 1 Anthem", status="accepted")
    db.add(req_c1_ws1)
    db.flush()
    proj1 = Project(workspace_id=ws1.id, client_id=c1_ws1.id, name="Corp 1 Anthem Film", request_id=req_c1_ws1.id, status="active")
    db.add(proj1)

    # Project 2: Client 1 with Agency 2 (Multi-Agency Relationship)
    c1_ws2 = Client(workspace_id=ws2.id, name=client_user_1.full_name, brand="Corp One", memory_bank_id="bank-c1-ws2")
    db.add(c1_ws2)
    db.flush()
    req_c1_ws2 = ProjectRequest(client_user_id=client_user_1.id, agency_workspace_id=ws2.id, title="Corp 1 Social Cut", status="accepted")
    db.add(req_c1_ws2)
    db.flush()
    proj2 = Project(workspace_id=ws2.id, client_id=c1_ws2.id, name="Corp 1 Social Cut Edit", request_id=req_c1_ws2.id, status="active")
    db.add(proj2)

    # Project 3: Client 2 with Agency 1 (Target for cross-tenant testing)
    c2_ws1 = Client(workspace_id=ws1.id, name=client_user_2.full_name, brand="Competitor Inc", memory_bank_id="bank-c2-ws1")
    db.add(c2_ws1)
    db.flush()
    req_c2_ws1 = ProjectRequest(client_user_id=client_user_2.id, agency_workspace_id=ws1.id, title="Competitor Promo", status="accepted")
    db.add(req_c2_ws1)
    db.flush()
    proj3 = Project(workspace_id=ws1.id, client_id=c2_ws1.id, name="Competitor Promo Cut", request_id=req_c2_ws1.id, status="active")
    db.add(proj3)

    # Guest portal access for Client 1 on Workspace 1 only
    guest_access = ClientPortalAccess(
        workspace_id=ws1.id,
        client_id=c1_ws1.id,
        access_token="guest-token-c1-ws1",
        passcode="CORP-1111",
        client_email=client_user_1.email,
    )
    db.add(guest_access)
    db.commit()

    yield {
        "db": db,
        "ws1": ws1,
        "ws2": ws2,
        "owner1": agency1_owner,
        "client1": client_user_1,
        "client2": client_user_2,
        "proj1": proj1,
        "proj2": proj2,
        "proj3": proj3,
        "guest_token": "guest-token-c1-ws1",
    }

    db.close()
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_unauthenticated_portal_access_rejected(isolated_env):
    """Unauthenticated requests must be rejected with HTTP 401."""
    with TestClient(app) as client:
        r1 = client.get("/api/portal/auth/me")
        assert r1.status_code == 401

        r2 = client.get("/api/portal/projects")
        assert r2.status_code == 401

        r3 = client.get(f"/api/portal/projects/{isolated_env['proj1'].id}")
        assert r3.status_code == 401


def test_agency_owner_forbidden_from_client_portal(isolated_env):
    """Agency owners must NOT be able to access client portal endpoints (HTTP 403)."""
    owner = isolated_env["owner1"]
    membership = isolated_env["db"].scalar(select(Membership).where(Membership.user_id == owner.id))
    owner_token = issue_token(owner, membership)

    with TestClient(app) as client:
        # 1. Agency owner passes token via Bearer
        r1 = client.get("/api/portal/auth/me", headers={"Authorization": f"Bearer {owner_token}"})
        assert r1.status_code == 403
        assert "restricted to client accounts" in r1.json()["detail"]

        r2 = client.get("/api/portal/projects", headers={"Authorization": f"Bearer {owner_token}"})
        assert r2.status_code == 403

        r3 = client.get(f"/api/portal/projects/{isolated_env['proj1'].id}", headers={"Authorization": f"Bearer {owner_token}"})
        assert r3.status_code == 403

        # 2. Agency owner with frameops_session cookie only (not frameops_client_session)
        client.cookies.set("frameops_session", owner_token)
        r4 = client.get("/api/portal/auth/me")
        assert r4.status_code == 401  # frameops_session is completely ignored by client portal


def test_multi_agency_client_sees_projects_across_agencies(isolated_env):
    """Client 1 working with Agency 1 and Agency 2 sees both projects in portal."""
    c1 = isolated_env["client1"]
    c1_token = issue_client_session_token(c1)

    with TestClient(app) as client:
        client.cookies.set("frameops_client_session", c1_token)

        # 1. /api/portal/auth/me returns client identity and count across all agencies
        r_me = client.get("/api/portal/auth/me")
        assert r_me.status_code == 200
        data_me = r_me.json()
        assert data_me["client"]["name"] == c1.full_name
        assert data_me["projects_count"] == 2

        # 2. /api/portal/projects returns BOTH Agency 1 and Agency 2 projects
        r_projs = client.get("/api/portal/projects")
        assert r_projs.status_code == 200
        projs = r_projs.json()
        assert len(projs) == 2
        proj_ids = {p["id"] for p in projs}
        assert proj_ids == {isolated_env["proj1"].id, isolated_env["proj2"].id}

        # 3. Can access both project details
        r_p1 = client.get(f"/api/portal/projects/{isolated_env['proj1'].id}")
        assert r_p1.status_code == 200
        assert r_p1.json()["id"] == isolated_env["proj1"].id

        r_p2 = client.get(f"/api/portal/projects/{isolated_env['proj2'].id}")
        assert r_p2.status_code == 200
        assert r_p2.json()["id"] == isolated_env["proj2"].id


def test_cross_tenant_isolation_between_clients(isolated_env):
    """Client 1 cannot access Client 2's project, comments, or submissions."""
    c1 = isolated_env["client1"]
    c1_token = issue_client_session_token(c1)
    proj3_id = isolated_env["proj3"].id  # Belongs to Client 2

    with TestClient(app) as client:
        client.cookies.set("frameops_client_session", c1_token)

        # Attempt to access Client 2's project
        r = client.get(f"/api/portal/projects/{proj3_id}")
        assert r.status_code == 404

        # Attempt to post comment on Client 2's project
        r_comment = client.post(
            f"/api/portal/projects/{proj3_id}/comments",
            json={"review_version_id": 1, "timestamp_seconds": 10.0, "timecode": "00:00:10:00", "content": "Spying on competitor"},
        )
        assert r_comment.status_code == 404


def test_guest_passcode_strictly_scoped(isolated_env):
    """Guest passcode issued for Client 1 on Workspace 1 only grants access to that specific project."""
    guest_token = isolated_env["guest_token"]

    with TestClient(app) as client:
        client.cookies.set("frameops_portal_session", guest_token)

        # 1. Sees only Project 1 (Workspace 1)
        r = client.get("/api/portal/projects")
        assert r.status_code == 200
        projs = r.json()
        assert len(projs) == 1
        assert projs[0]["id"] == isolated_env["proj1"].id

        # 2. Cannot see Client 1's project on Workspace 2 (proj2) via this guest token
        r_p2 = client.get(f"/api/portal/projects/{isolated_env['proj2'].id}")
        assert r_p2.status_code == 404

        # 3. Cannot see Client 2's project on Workspace 1 (proj3)
        r_p3 = client.get(f"/api/portal/projects/{isolated_env['proj3'].id}")
        assert r_p3.status_code == 404
