import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import Client, Membership, Project, User, Workspace
from app.security import hash_password, issue_token


@pytest.fixture
def client_env(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def test_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(settings, "auth_secret", "test-portal-secret-with-high-entropy-12345678")
    monkeypatch.setattr(settings, "groq_api_key", "")
    monkeypatch.setattr(settings, "hindsight_api_token", "")
    monkeypatch.setattr(settings, "hindsight_api_url", "")
    app.dependency_overrides[get_db] = test_db

    # Create workspace, owner, two clients, and projects
    db = Session()
    owner_user = User(email="owner@agency.com", password_hash=hash_password("test-owner-pw-1234"))
    ws = Workspace(name="Creative Studio")
    db.add_all([owner_user, ws])
    db.flush()

    member = Membership(workspace_id=ws.id, user_id=owner_user.id, role="owner")
    db.add(member)

    client_a = Client(
        workspace_id=ws.id,
        name="Nike Brand Team",
        brand="Nike",
        industry="Footwear",
        description="Air Max launch campaign",
        memory_bank_id="bank-nike-123",
        memory_status="ready"
    )
    client_b = Client(
        workspace_id=ws.id,
        name="Spotify Studios",
        brand="Spotify",
        industry="Audio",
        description="Wrapped 2026 campaign",
        memory_bank_id="bank-spotify-456",
        memory_status="ready"
    )
    db.add_all([client_a, client_b])
    db.flush()

    proj_a1 = Project(workspace_id=ws.id, client_id=client_a.id, name="Nike Air 30s Cut", description="Main commercial")
    proj_a2 = Project(workspace_id=ws.id, client_id=client_a.id, name="Nike Air Social Cut", description="Instagram 9:16")
    proj_b1 = Project(workspace_id=ws.id, client_id=client_b.id, name="Spotify Wrapped Teaser", description="Teaser reel")
    db.add_all([proj_a1, proj_a2, proj_b1])
    db.commit()

    c_a_id, c_b_id = client_a.id, client_b.id
    p_a1_id, p_a2_id, p_b1_id = proj_a1.id, proj_a2.id, proj_b1.id
    db.close()

    yield {
        "engine": engine,
        "owner_token": issue_token(owner_user, member),
        "client_a_id": c_a_id,
        "client_b_id": c_b_id,
        "proj_a1_id": p_a1_id,
        "proj_a2_id": p_a2_id,
        "proj_b1_id": p_b1_id,
    }

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_portal_access_generation_and_client_isolation(client_env):
    owner = TestClient(app)
    owner.headers["Authorization"] = f"Bearer {client_env['owner_token']}"

    # 1. Agency editor retrieves portal link for Client A
    res = owner.get(f"/api/clients/{client_env['client_a_id']}/portal-access")
    assert res.status_code == 200
    access_a = res.json()
    assert "access_token" in access_a
    assert "passcode" in access_a
    passcode_a = access_a["passcode"]

    # 2. Client A signs in using access code
    portal_client = TestClient(app)
    login_res = portal_client.post("/api/portal/auth/login", json={"code": passcode_a})
    assert login_res.status_code == 200
    assert login_res.json()["client"]["name"] == "Nike Brand Team"
    jwt_token = login_res.json()["token"]

    portal_client.headers["Authorization"] = f"Bearer {jwt_token}"

    # 3. Client A checks me endpoint
    me_res = portal_client.get("/api/portal/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["client"]["brand"] == "Nike"
    assert me_res.json()["projects_count"] == 2

    # 4. Client A lists projects - MUST ONLY SEE Nike projects
    proj_res = portal_client.get("/api/portal/projects")
    assert proj_res.status_code == 200
    projects = proj_res.json()
    assert len(projects) == 2
    proj_ids = [p["id"] for p in projects]
    assert client_env["proj_a1_id"] in proj_ids
    assert client_env["proj_a2_id"] in proj_ids
    assert client_env["proj_b1_id"] not in proj_ids

    # 5. Client A attempts to access Client B's Spotify project directly -> MUST BE REJECTED 404
    forbidden_res = portal_client.get(f"/api/portal/projects/{client_env['proj_b1_id']}")
    assert forbidden_res.status_code == 404


def test_portal_ai_structured_draft_and_confirmation(client_env, monkeypatch):
    from app.services import groq, hindsight
    from app.schemas import ExtractionResult, ExtractionItem

    async def mock_extract(content: str):
        return ExtractionResult(
            requests=[
                ExtractionItem(
                    description="The intro pacing feels too slow, trim 2 seconds from the opening logo reveal.",
                    category="Pacing",
                    classification="explicit",
                    confidence=0.95,
                    requires_confirmation=False,
                ),
                ExtractionItem(
                    description="Make the sound design punchier during the shoe drop.",
                    category="Audio",
                    classification="explicit",
                    confidence=0.92,
                    requires_confirmation=False,
                ),
            ],
            ambiguities=["Maybe make the color grade warmer in the night scene."],
            production_risks=[],
            missing_information=[],
            required_assets=[],
        )

    async def mock_retain(bank_id, content, context, tags, document_id):
        return {"id": "mock-hindsight-id-123", "text": content}, True

    monkeypatch.setattr(settings, "groq_api_key", "mock-groq-key")
    monkeypatch.setattr(settings, "groq_model", "mock-groq-model")
    monkeypatch.setattr(settings, "hindsight_api_token", "mock-token")
    monkeypatch.setattr(settings, "hindsight_api_url", "https://api.hindsight.test")
    monkeypatch.setattr(groq, "extract_feedback", mock_extract)
    monkeypatch.setattr(hindsight, "retain_and_verify", mock_retain)
    monkeypatch.setattr(hindsight, "configured", lambda: True)

    owner = TestClient(app)
    owner.headers["Authorization"] = f"Bearer {client_env['owner_token']}"
    access_a = owner.get(f"/api/clients/{client_env['client_a_id']}/portal-access").json()

    portal = TestClient(app)
    portal.headers["X-Portal-Token"] = access_a["access_token"]

    # 1. Client submits feedback draft for AI structuring
    draft_payload = {
        "feedback_type": "text",
        "content": "The intro pacing feels too slow, trim 2 seconds from the opening logo reveal.\nMake the sound design punchier during the shoe drop.\nMaybe make the color grade warmer in the night scene."
    }
    draft_res = portal.post(f"/api/portal/projects/{client_env['proj_a1_id']}/feedback/draft", json=draft_payload)
    assert draft_res.status_code == 200
    draft_data = draft_res.json()
    assert len(draft_data["requests"]) >= 2
    # Check category classifications
    categories = [r["category"] for r in draft_data["requests"]]
    assert any("Pacing" in c for c in categories)
    assert any("Audio" in c for c in categories)
    # Ambiguity check detected for "Maybe..."
    assert len(draft_data["ambiguities"]) > 0

    # 2. Client reviews and confirms specific item before submitting
    reviewed_items = draft_data["requests"]
    # Client confirms item 1 as permanent preference, leaves item 2 as temporary cut note
    reviewed_items[0]["client_confirmed"] = True
    reviewed_items[1]["client_confirmed"] = False

    submit_payload = {
        "feedback_type": "text",
        "content": draft_payload["content"],
        "items": reviewed_items,
        "author_name": "Sarah Connor (Brand Director)"
    }
    sub_res = portal.post(f"/api/portal/projects/{client_env['proj_a1_id']}/feedback/submit", json=submit_payload)
    assert sub_res.status_code == 201
    assert sub_res.json()["status"] == "submitted"
    assert len(sub_res.json()["items"]) == len(reviewed_items)


def test_portal_fallback_parser_without_ai(client_env):
    """Ensure regex fallback works 100% offline with zero AI credentials."""
    owner = TestClient(app)
    owner.headers["Authorization"] = f"Bearer {client_env['owner_token']}"
    access_a = owner.get(f"/api/clients/{client_env['client_a_id']}/portal-access").json()

    portal = TestClient(app)
    portal.headers["X-Portal-Token"] = access_a["access_token"]

    draft_payload = {
        "feedback_type": "text",
        "content": "The intro pacing feels too slow, trim 2 seconds from the opening logo reveal.\nMake the sound design punchier during the shoe drop.\nMaybe make the color grade warmer in the night scene."
    }
    draft_res = portal.post(f"/api/portal/projects/{client_env['proj_a1_id']}/feedback/draft", json=draft_payload)
    assert draft_res.status_code == 200
    draft_data = draft_res.json()
    assert len(draft_data["requests"]) >= 2
    categories = [r["category"] for r in draft_data["requests"]]
    assert any("Pacing" in c for c in categories)
    assert any("Audio" in c for c in categories)
    assert len(draft_data["ambiguities"]) > 0


def test_portal_video_comments_and_decisions(client_env):
    owner = TestClient(app)
    owner.headers["Authorization"] = f"Bearer {client_env['owner_token']}"
    access_a = owner.get(f"/api/clients/{client_env['client_a_id']}/portal-access").json()

    portal = TestClient(app)
    portal.headers["X-Portal-Token"] = access_a["access_token"]

    # 1. Add timestamped video comment
    comment_payload = {
        "timestamp_seconds": 14.5,
        "timecode": "00:14",
        "content": "Cut to product hero close-up right on the beat drop.",
        "author_name": "Sarah Connor"
    }
    c_res = portal.post(f"/api/portal/projects/{client_env['proj_a1_id']}/comments", json=comment_payload)
    assert c_res.status_code == 201
    comment_id = c_res.json()["id"]
    assert c_res.json()["timecode"] == "00:14"

    # 2. List comments
    comments_list = portal.get(f"/api/portal/projects/{client_env['proj_a1_id']}/comments").json()
    assert len(comments_list) == 1
    assert comments_list[0]["id"] == comment_id

    # 3. Client action: Request Changes
    decision_res = portal.post(f"/api/portal/projects/{client_env['proj_a1_id']}/decision", json={
        "decision": "changes_requested",
        "notes": "Please address the timestamped comments on pacing and audio mix."
    })
    assert decision_res.status_code == 200
    assert decision_res.json()["version_status"] == "changes_requested"

    # 4. Client action: Approve
    approve_res = portal.post(f"/api/portal/projects/{client_env['proj_a1_id']}/decision", json={
        "decision": "approve",
        "notes": "Looks fantastic, ready for final color grade export!"
    })
    assert approve_res.status_code == 200
    assert approve_res.json()["version_status"] == "approved"
    assert approve_res.json()["project_status"] == "completed"

    # 5. Check feedback history status indicators
    feedback_list = portal.get(f"/api/portal/projects/{client_env['proj_a1_id']}/feedback").json()
    assert len(feedback_list) >= 2


def test_security_email_only_login_rejected_401(client_env):
    """Ensure email-only submission without passcode or token is strictly rejected (HTTP 401)."""
    client = TestClient(app)
    res = client.post("/api/portal/auth/login", json={"email": "client@nike.com"})
    assert res.status_code == 401
    assert "Passcode or access token is required" in res.json().get("detail", "")


def test_security_invalid_passcode_rejected_401(client_env):
    """Ensure invalid passcodes are strictly rejected with HTTP 401."""
    client = TestClient(app)
    res = client.post("/api/portal/auth/login", json={"code": "INVALID-PASSCODE-9999"})
    assert res.status_code == 401
    assert "Invalid client portal access token or code" in res.json().get("detail", "")


def test_security_expired_token_rejected_401(client_env):
    """Ensure expired JWT session tokens and expired access tokens return HTTP 401."""
    import jwt
    from datetime import datetime, UTC, timedelta
    
    # 1. Expired JWT
    expired_time = datetime.now(UTC) - timedelta(hours=2)
    expired_jwt = jwt.encode(
        {"sub": f"client:{client_env['client_a_id']}", "client_id": client_env['client_a_id'],
         "workspace_id": 1, "role": "client", "iat": expired_time - timedelta(hours=1), "exp": expired_time},
        settings.auth_secret,
        algorithm="HS256",
    )
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {expired_jwt}"
    res = client.get("/api/portal/auth/me")
    assert res.status_code == 401

    # 2. Expired portal access token directly
    owner = TestClient(app)
    owner.headers["Authorization"] = f"Bearer {client_env['owner_token']}"
    access_res = owner.get(f"/api/clients/{client_env['client_a_id']}/portal-access")
    token_str = access_res.json()["access_token"]

    from app.models import ClientPortalAccess
    from sqlalchemy.orm import Session as OrmSession
    with OrmSession(client_env["engine"]) as db_session:
        acc = db_session.query(ClientPortalAccess).filter_by(access_token=token_str).first()
        acc.created_at = datetime.now(UTC) - timedelta(days=60)
        db_session.commit()

    portal_client = TestClient(app)
    login_expired = portal_client.post("/api/portal/auth/login", json={"token": token_str})
    assert login_expired.status_code == 401


def test_security_cross_client_tenant_isolation_404(client_env):
    """Ensure Client A cannot read, comment, or approve Client B's projects (HTTP 404)."""
    owner = TestClient(app)
    owner.headers["Authorization"] = f"Bearer {client_env['owner_token']}"
    access_a = owner.get(f"/api/clients/{client_env['client_a_id']}/portal-access").json()

    portal_a = TestClient(app)
    login_a = portal_a.post("/api/portal/auth/login", json={"code": access_a["passcode"]})
    assert login_a.status_code == 200
    token_a = login_a.json()["token"]
    portal_a.headers["Authorization"] = f"Bearer {token_a}"

    b_proj_id = client_env["proj_b1_id"]
    assert portal_a.get(f"/api/portal/projects/{b_proj_id}").status_code == 404
    assert portal_a.get(f"/api/portal/projects/{b_proj_id}/comments").status_code == 404
    assert portal_a.post(
        f"/api/portal/projects/{b_proj_id}/comments",
        json={"content": "Sneak peek", "timestamp_seconds": 10.0, "timecode": "00:10"}
    ).status_code == 404
    assert portal_a.post(
        f"/api/portal/projects/{b_proj_id}/decision",
        json={"decision": "approve", "notes": "Unauthorized approval attempt"}
    ).status_code == 404


def test_security_unauthorized_route_access_401(client_env):
    """Ensure unauthenticated callers cannot access portal API routes without credentials (HTTP 401)."""
    unauth = TestClient(app)
    assert unauth.get("/api/portal/auth/me").status_code == 401
    assert unauth.get("/api/portal/projects").status_code == 401
    assert unauth.get(f"/api/portal/projects/{client_env['proj_a1_id']}").status_code == 401
    assert unauth.get(f"/api/portal/projects/{client_env['proj_a1_id']}/comments").status_code == 401
