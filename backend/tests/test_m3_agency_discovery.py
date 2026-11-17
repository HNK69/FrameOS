"""Milestone 3 Comprehensive Test Suite: Agency Discovery & Profile Management.

Covers the complete 50-test matrix across groups:
- Group 1: Profile Retrieval and Default State (Tests 1-4)
- Group 2: Profile Update (PUT /api/agency/profile) (Tests 5-10)
- Group 3: Publishing Gate Validation (Tests 11-16)
- Group 4: Explicit Publishing and Readiness Checklist (Tests 17-20)
- Group 5: Explicit Unpublishing (Tests 21-23)
- Group 6: Public Discovery Catalog (GET /api/discovery/agencies) (Tests 24-32)
- Group 7: Detailed Agency View (GET /api/discovery/agencies/{workspace_id}) (Tests 33-39)
- Group 8: Cross-Tenant Security & RBAC (Tests 40-46)
- Group 9: Zero Fabricated Data (Tests 47-49)
- Group 10: International / Unicode Discovery & Serialization (Test 50)
"""

from __future__ import annotations

import json
from datetime import UTC

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import AgencyProfile, Membership, User, Workspace
from app.security import hash_password, issue_client_session_token, issue_token

# ==============================================================================
# Helper Functions & Test Fixture Builders
# ==============================================================================

def create_agency_fixture(
    db: Session,
    email: str,
    agency_name: str,
    is_published: bool = False,
    role: str = "owner",
) -> tuple[User, Workspace, Membership, AgencyProfile, str]:
    """Creates a User, Workspace, Membership, and AgencyProfile for testing."""
    user = User(
        email=email,
        password_hash=hash_password("Pass12345678!"),
        role="agency_owner" if role == "owner" else "agency_member",
        full_name=f"{agency_name} {role.capitalize()}",
    )
    ws = Workspace(name=agency_name)
    db.add_all([user, ws])
    db.flush()

    mem = Membership(user_id=user.id, workspace_id=ws.id, role=role)
    db.add(mem)
    db.flush()

    profile = AgencyProfile(workspace_id=ws.id, is_published=is_published, contact_email=email)
    db.add(profile)
    db.commit()

    token = issue_token(user, mem)
    return user, ws, mem, profile, token


def create_client_fixture(db: Session, email: str) -> tuple[User, str]:
    """Creates a Client user and session token for testing."""
    user = User(
        email=email,
        password_hash=hash_password("ClientPass1234!"),
        role="client",
        full_name="Client Test User",
    )
    db.add(user)
    db.commit()

    token = issue_client_session_token(user)
    return user, token


# ==============================================================================
# Group 1: Profile Retrieval and Default State (Tests 1-4)
# ==============================================================================

def test_01_profile_retrieval_default_state(isolated_db):
    """Test 1: Newly registered agency returns default profile with unready publishing status."""
    with TestClient(app) as client:
        reg_payload = {
            "email": "agency_reg_1@frameops.com",
            "password": "Password12345!",
            "full_name": "Studio One Owner",
            "agency_name": "Studio One",
        }
        reg_resp = client.post("/api/auth/register/agency", json=reg_payload)
        assert reg_resp.status_code == 201

        resp = client.get("/api/agency/profile")
        assert resp.status_code == 200
        data = resp.json()

        assert data["is_published"] is False
        assert data["published_at"] is None
        assert data["specializations"] == []
        assert data["services"] == []
        assert data["portfolio"] == []
        assert data["is_ready_to_publish"] is False
        assert data["can_publish"] is False
        for req in ["description", "specializations", "services"]:
            assert req in data["missing_publish_fields"]
            assert req in data["missing_fields"]


def test_02_profile_retrieval_workspace_name(isolated_db):
    """Test 2: Profile response correctly embeds workspace name."""
    with isolated_db() as db:
        _, ws, _, _, token = create_agency_fixture(db, "apex@apex.test", "Apex Creative Studio")

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.get("/api/agency/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["workspace_name"] == "Apex Creative Studio"
        assert data["workspace_id"] == ws.id


def test_03_profile_lazy_creation_if_missing(isolated_db):
    """Test 3: If workspace has no AgencyProfile row in DB, GET lazily creates one."""
    with isolated_db() as db:
        user = User(
            email="lazy_owner@frameops.test",
            password_hash=hash_password("Pass12345678!"),
            role="agency_owner",
            full_name="Lazy Owner",
        )
        ws = Workspace(name="Lazy Studio")
        db.add_all([user, ws])
        db.flush()
        mem = Membership(user_id=user.id, workspace_id=ws.id, role="owner")
        db.add(mem)
        db.commit()
        token = issue_token(user, mem)

        # Verify no AgencyProfile row exists initially
        p_count = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == ws.id))
        assert p_count is None

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.get("/api/agency/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["workspace_id"] == ws.id
        assert data["is_published"] is False

    with isolated_db() as db:
        created = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == ws.id))
        assert created is not None
        assert created.workspace_id == ws.id


def test_04_profile_retrieval_corrupted_json_resilience(isolated_db):
    """Test 4: Non-list JSON in database string columns safely evaluates to empty lists."""
    with isolated_db() as db:
        user, ws, mem, profile, token = create_agency_fixture(db, "corrupt@frameops.test", "Corrupt Agency")
        profile.specializations = "corrupted {"
        profile.services = "null"
        profile.portfolio = "123"
        db.commit()

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.get("/api/agency/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["specializations"] == []
        assert data["services"] == []
        assert data["portfolio"] == []


# ==============================================================================
# Group 2: Profile Update (PUT /api/agency/profile) (Tests 5-10)
# ==============================================================================

def test_05_profile_update_text_fields(isolated_db):
    """Test 5: Updating text fields correctly updates values in response and DB."""
    with isolated_db() as db:
        _, _, _, _, token = create_agency_fixture(db, "apex_text@apex.test", "Apex Text Studio")

    payload = {
        "tagline": "Top Studio Visuals",
        "description": "We produce commercial advertisements",
        "contact_email": "ads@apex.test",
        "contact_phone": "+1234567890",
        "website": "https://apex.test",
    }
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.put("/api/agency/profile", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["tagline"] == "Top Studio Visuals"
        assert data["description"] == "We produce commercial advertisements"
        assert data["contact_email"] == "ads@apex.test"
        assert data["contact_phone"] == "+1234567890"
        assert data["website"] == "https://apex.test"


def test_06_profile_update_string_lists(isolated_db):
    """Test 6: Updating specializations and services serializes lists to JSON strings in DB."""
    with isolated_db() as db:
        _, ws, _, _, token = create_agency_fixture(db, "lists@apex.test", "Apex Lists Studio")

    payload = {
        "specializations": ["Short-form", "Commercials"],
        "services": ["Color Grading", "Sound Design"],
    }
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.put("/api/agency/profile", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["specializations"] == ["Short-form", "Commercials"]
        assert data["services"] == ["Color Grading", "Sound Design"]

    with isolated_db() as db:
        p = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == ws.id))
        assert json.loads(p.specializations) == ["Short-form", "Commercials"]
        assert json.loads(p.services) == ["Color Grading", "Sound Design"]


def test_07_profile_update_portfolio_items(isolated_db):
    """Test 7: Updating portfolio serializes structured items correctly."""
    with isolated_db() as db:
        _, ws, _, _, token = create_agency_fixture(db, "portfolio@apex.test", "Apex Portfolio Studio")

    payload = {
        "portfolio": [
            {
                "title": "Nike Campaign",
                "video_url": "https://vimeo.com/12345",
                "thumbnail_url": "https://vimeo.com/thumb.jpg",
                "description": "Master color grading pass",
            }
        ]
    }
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.put("/api/agency/profile", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["portfolio"]) == 1
        assert data["portfolio"][0]["title"] == "Nike Campaign"

    with isolated_db() as db:
        p = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == ws.id))
        assert len(p.portfolio_list) == 1
        assert p.portfolio_list[0]["title"] == "Nike Campaign"


def test_08_profile_update_partial_and_empty_fields(isolated_db):
    """Test 8: Updating partial fields does not overwrite omitted fields with defaults."""
    with isolated_db() as db:
        _, ws, _, _, token = create_agency_fixture(db, "partial@apex.test", "Apex Partial Studio")

    # First update: set full profile
    first_payload = {
        "tagline": "Initial Tagline",
        "description": "Initial Description",
        "specializations": ["VFX"],
        "services": ["3D Animation"],
        "contact_email": "initial@apex.test",
    }
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        r1 = client.put("/api/agency/profile", json=first_payload)
        assert r1.status_code == 200

        # Second update: only update tagline
        r2 = client.put("/api/agency/profile", json={"tagline": "Updated Tagline Only"})
        assert r2.status_code == 200
        data = r2.json()
        assert data["tagline"] == "Updated Tagline Only"
        assert data["description"] == "Initial Description"
        assert data["specializations"] == ["VFX"]
        assert data["services"] == ["3D Animation"]
        assert data["contact_email"] == "initial@apex.test"


def test_09_profile_update_whitespace_stripping(isolated_db):
    """Test 9: Leading and trailing whitespace is stripped from text fields."""
    with isolated_db() as db:
        _, _, _, _, token = create_agency_fixture(db, "strip@apex.test", "Apex Strip Studio")

    payload = {
        "tagline": "   Padded Tagline Text   ",
        "description": "   Padded Description Text   ",
    }
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.put("/api/agency/profile", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["tagline"] == "Padded Tagline Text"
        assert data["description"] == "Padded Description Text"


def test_10_profile_update_persists_in_database(isolated_db):
    """Test 10: Profile updates persist in database and update updated_at timestamp."""
    with isolated_db() as db:
        _, ws, _, profile, token = create_agency_fixture(db, "persist@apex.test", "Apex Persist Studio")
        initial_updated = profile.updated_at

    payload = {
        "tagline": "Database Persisted Tagline",
        "contact_email": "verified@apex.test",
    }
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.put("/api/agency/profile", json=payload)
        assert resp.status_code == 200

    with isolated_db() as db:
        refreshed = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == ws.id))
        assert refreshed.tagline == "Database Persisted Tagline"
        assert refreshed.contact_email == "verified@apex.test"
        ref_updated = refreshed.updated_at.replace(tzinfo=UTC) if refreshed.updated_at and refreshed.updated_at.tzinfo is None else refreshed.updated_at
        init_updated = initial_updated.replace(tzinfo=UTC) if initial_updated and initial_updated.tzinfo is None else initial_updated
        assert ref_updated >= init_updated


# ==============================================================================
# Group 3: Publishing Gate Validation (Tests 11-16)
# ==============================================================================

def test_11_publish_gate_rejects_missing_description(isolated_db):
    """Test 11: Publish is rejected with 400 when description is blank."""
    with isolated_db() as db:
        _, _, _, _, token = create_agency_fixture(db, "no_desc@test.com", "No Desc Studio")

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        client.put(
            "/api/agency/profile",
            json={
                "description": "",
                "contact_email": "valid@test.com",
                "specializations": ["commercial"],
                "services": ["editing"],
            },
        )
        resp = client.post("/api/agency/profile/publish")
        assert resp.status_code == 400
        data = resp.json()
        assert "description" in str(data)


def test_12_publish_gate_rejects_missing_contact_email(isolated_db):
    """Test 12: Publish is rejected with 400 when contact_email is blank."""
    with isolated_db() as db:
        _, _, _, _, token = create_agency_fixture(db, "no_email@test.com", "No Email Studio")

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        client.put(
            "/api/agency/profile",
            json={
                "description": "Valid studio description",
                "contact_email": "",
                "specializations": ["commercial"],
                "services": ["editing"],
            },
        )
        resp = client.post("/api/agency/profile/publish")
        assert resp.status_code == 400
        data = resp.json()
        assert "contact_email" in str(data)


def test_13_publish_gate_rejects_missing_specializations(isolated_db):
    """Test 13: Publish is rejected with 400 when specializations array is empty."""
    with isolated_db() as db:
        _, _, _, _, token = create_agency_fixture(db, "no_spec@test.com", "No Spec Studio")

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        client.put(
            "/api/agency/profile",
            json={
                "description": "Valid description",
                "contact_email": "valid@test.com",
                "specializations": [],
                "services": ["editing"],
            },
        )
        resp = client.post("/api/agency/profile/publish")
        assert resp.status_code == 400
        data = resp.json()
        assert "specializations" in str(data)


def test_14_publish_gate_rejects_missing_services(isolated_db):
    """Test 14: Publish is rejected with 400 when services array is empty."""
    with isolated_db() as db:
        _, _, _, _, token = create_agency_fixture(db, "no_srv@test.com", "No Srv Studio")

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        client.put(
            "/api/agency/profile",
            json={
                "description": "Valid description",
                "contact_email": "valid@test.com",
                "specializations": ["commercial"],
                "services": [],
            },
        )
        resp = client.post("/api/agency/profile/publish")
        assert resp.status_code == 400
        data = resp.json()
        assert "services" in str(data)


def test_15_publish_gate_rejects_all_missing_fields(isolated_db):
    """Test 15: Publish on completely unconfigured profile lists all missing requirements."""
    with isolated_db() as db:
        _, _, _, profile, token = create_agency_fixture(db, "", "Empty Studio")
        profile.description = ""
        profile.contact_email = ""
        profile.specializations = "[]"
        profile.services = "[]"
        db.commit()

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.post("/api/agency/profile/publish")
        assert resp.status_code == 400
        detail = resp.json().get("detail", {})
        missing = detail.get("missing_fields", [])
        for f in ["description", "contact_email", "specializations", "services"]:
            assert f in missing


def test_16_publish_gate_preserves_unpublished_state_on_failure(isolated_db):
    """Test 16: When publishing gate fails, database remains is_published=False with published_at=None."""
    with isolated_db() as db:
        _, ws, _, profile, token = create_agency_fixture(db, "", "Fail Studio")
        profile.description = ""
        profile.specializations = "[]"
        db.commit()

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.post("/api/agency/profile/publish")
        assert resp.status_code == 400

    with isolated_db() as db:
        refreshed = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == ws.id))
        assert refreshed.is_published is False
        assert refreshed.published_at is None


# ==============================================================================
# Group 4: Explicit Publishing and Readiness Checklist (Tests 17-20)
# ==============================================================================

def test_17_readiness_checklist_evaluation(isolated_db):
    """Test 17: Populating all required fields marks profile ready to publish."""
    with isolated_db() as db:
        _, _, _, _, token = create_agency_fixture(db, "ready@test.com", "Ready Studio")

    payload = {
        "description": "Full service video studio",
        "contact_email": "ready@test.com",
        "specializations": ["commercial"],
        "services": ["editing"],
    }
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        client.put("/api/agency/profile", json=payload)

        resp = client.get("/api/agency/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_ready_to_publish"] is True
        assert data["can_publish"] is True
        assert data["missing_publish_fields"] == []
        assert data["missing_fields"] == []


def test_18_publish_success_sets_published_and_timestamp(isolated_db):
    """Test 18: Successful publish sets is_published=True and records published_at timestamp."""
    with isolated_db() as db:
        _, ws, _, _, token = create_agency_fixture(db, "pub_succ@test.com", "Publish Success Studio")

    payload = {
        "description": "Award winning agency",
        "contact_email": "contact@pubsucc.com",
        "specializations": ["cinematic"],
        "services": ["color_grading"],
    }
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        client.put("/api/agency/profile", json=payload)

        resp = client.post("/api/agency/profile/publish")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_published"] is True
        assert data["published_at"] is not None

    with isolated_db() as db:
        p = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == ws.id))
        assert p.is_published is True
        assert p.published_at is not None


def test_19_publish_idempotent(isolated_db):
    """Test 19: Calling publish on an already published profile succeeds idempotently."""
    with isolated_db() as db:
        _, ws, _, _, token = create_agency_fixture(db, "idemp@test.com", "Idempotent Studio")

    payload = {
        "description": "Reliable agency",
        "contact_email": "info@idemp.com",
        "specializations": ["social"],
        "services": ["editing"],
    }
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        client.put("/api/agency/profile", json=payload)

        r1 = client.post("/api/agency/profile/publish")
        assert r1.status_code == 200
        assert r1.json()["is_published"] is True

        r2 = client.post("/api/agency/profile/publish")
        assert r2.status_code == 200
        assert r2.json()["is_published"] is True


def test_20_profile_update_preserves_published_status(isolated_db):
    """Test 20: Editing profile attributes on a published profile preserves published state."""
    with isolated_db() as db:
        _, ws, _, _, token = create_agency_fixture(db, "preserve@test.com", "Preserve Studio")

    setup_payload = {
        "description": "High impact video",
        "contact_email": "preserve@test.com",
        "specializations": ["commercial"],
        "services": ["sound"],
    }
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        client.put("/api/agency/profile", json=setup_payload)
        client.post("/api/agency/profile/publish")

        # Now edit tagline
        resp = client.put("/api/agency/profile", json={"tagline": "New Studio Tagline"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["tagline"] == "New Studio Tagline"
        assert data["is_published"] is True

    with isolated_db() as db:
        p = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == ws.id))
        assert p.is_published is True


# ==============================================================================
# Group 5: Explicit Unpublishing (Tests 21-23)
# ==============================================================================

def test_21_unpublish_sets_is_published_false(isolated_db):
    """Test 21: Calling unpublish transitions profile to unpublished state."""
    with isolated_db() as db:
        _, ws, _, _, token = create_agency_fixture(db, "unpub@test.com", "Unpublish Studio", is_published=True)

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.post("/api/agency/profile/unpublish")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_published"] is False

    with isolated_db() as db:
        p = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == ws.id))
        assert p.is_published is False


def test_22_unpublish_idempotent(isolated_db):
    """Test 22: Calling unpublish on an already unpublished profile returns 200 safely."""
    with isolated_db() as db:
        _, _, _, _, token = create_agency_fixture(db, "unpub_idemp@test.com", "Unpub Idemp Studio", is_published=False)

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.post("/api/agency/profile/unpublish")
        assert resp.status_code == 200
        assert resp.json()["is_published"] is False


def test_23_unpublish_immediately_removes_from_discovery(isolated_db):
    """Test 23: Profile published appears in discovery, and upon unpublishing immediately disappears."""
    with isolated_db() as db:
        _, ws, _, _, token = create_agency_fixture(db, "toggle@test.com", "Toggle Discovery Studio")

    payload = {
        "description": "Toggle agency description",
        "contact_email": "toggle@test.com",
        "specializations": ["promo"],
        "services": ["editing"],
    }
    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        client.put("/api/agency/profile", json=payload)
        client.post("/api/agency/profile/publish")

        # Verify visible in public discovery catalog
        pub_resp = client.get("/api/discovery/agencies")
        assert pub_resp.status_code == 200
        assert any(item["workspace_id"] == ws.id for item in pub_resp.json())

        # Unpublish
        client.post("/api/agency/profile/unpublish")

        # Verify immediately removed from public discovery catalog
        unpub_resp = client.get("/api/discovery/agencies")
        assert unpub_resp.status_code == 200
        assert all(item["workspace_id"] != ws.id for item in unpub_resp.json())


# ==============================================================================
# Group 6: Public Discovery Catalog (GET /api/discovery/agencies) (Tests 24-32)
# ==============================================================================

def test_24_discovery_catalog_returns_only_published(isolated_db):
    """Test 24: Public catalog lists published agencies and strictly omits unpublished ones."""
    with isolated_db() as db:
        _, ws1, _, _, _ = create_agency_fixture(db, "pub1@test.com", "Published Agency 1", is_published=True)
        _, ws2, _, _, _ = create_agency_fixture(db, "unpub2@test.com", "Unpublished Agency 2", is_published=False)

    with TestClient(app) as client:
        resp = client.get("/api/discovery/agencies")
        assert resp.status_code == 200
        data = resp.json()
        returned_ids = [item["workspace_id"] for item in data]
        assert ws1.id in returned_ids
        assert ws2.id not in returned_ids


def test_25_discovery_catalog_filter_by_specialization(isolated_db):
    """Test 25: Filtering discovery catalog by specialization returns only matching agencies."""
    with isolated_db() as db:
        _, ws1, _, p1, _ = create_agency_fixture(db, "spec1@test.com", "Agency 3D", is_published=True)
        p1.specializations = '["3D Animation", "Motion Design"]'
        _, ws2, _, p2, _ = create_agency_fixture(db, "spec2@test.com", "Agency Live Action", is_published=True)
        p2.specializations = '["Live Action", "Documentary"]'
        db.commit()

    with TestClient(app) as client:
        resp = client.get("/api/discovery/agencies?specialization=3D")
        assert resp.status_code == 200
        data = resp.json()
        ids = [item["workspace_id"] for item in data]
        assert ws1.id in ids
        assert ws2.id not in ids


def test_26_discovery_catalog_filter_by_service(isolated_db):
    """Test 26: Filtering discovery catalog by service returns only matching agencies."""
    with isolated_db() as db:
        _, ws1, _, p1, _ = create_agency_fixture(db, "srv1@test.com", "Agency Color", is_published=True)
        p1.services = '["Color Grading", "Conform"]'
        _, ws2, _, p2, _ = create_agency_fixture(db, "srv2@test.com", "Agency Audio", is_published=True)
        p2.services = '["Sound Design", "Audio Mixing"]'
        db.commit()

    with TestClient(app) as client:
        resp = client.get("/api/discovery/agencies?service=Color")
        assert resp.status_code == 200
        data = resp.json()
        ids = [item["workspace_id"] for item in data]
        assert ws1.id in ids
        assert ws2.id not in ids


def test_27_discovery_catalog_filter_by_category(isolated_db):
    """Test 27: Category filter matches against either specialization or service."""
    with isolated_db() as db:
        _, ws1, _, p1, _ = create_agency_fixture(db, "cat1@test.com", "Category Match Agency", is_published=True)
        p1.specializations = '["Commercial Editing"]'
        p1.services = '["Finishing"]'
        db.commit()

    with TestClient(app) as client:
        resp = client.get("/api/discovery/agencies?category=Commercial")
        assert resp.status_code == 200
        data = resp.json()
        assert any(item["workspace_id"] == ws1.id for item in data)


def test_28_discovery_catalog_text_search_query(isolated_db):
    """Test 28: Search query matches workspace name, tagline, or description case-insensitively."""
    with isolated_db() as db:
        _, ws, _, p, _ = create_agency_fixture(db, "search@test.com", "Velociraptor Productions", is_published=True)
        p.tagline = "Blazing fast turnover"
        p.description = "Boutique agency specializing in high tempo reels"
        db.commit()

    with TestClient(app) as client:
        # Match by name
        r1 = client.get("/api/discovery/agencies?query=velociraptor")
        assert r1.status_code == 200
        assert any(item["workspace_id"] == ws.id for item in r1.json())

        # Match by tagline
        r2 = client.get("/api/discovery/agencies?query=blazing")
        assert r2.status_code == 200
        assert any(item["workspace_id"] == ws.id for item in r2.json())

        # Match by description
        r3 = client.get("/api/discovery/agencies?query=high tempo")
        assert r3.status_code == 200
        assert any(item["workspace_id"] == ws.id for item in r3.json())


def test_29_discovery_catalog_combined_filters(isolated_db):
    """Test 29: Multiple filter parameters restrict results to items satisfying all conditions."""
    with isolated_db() as db:
        _, ws1, _, p1, _ = create_agency_fixture(db, "comb1@test.com", "Apex Motion", is_published=True)
        p1.specializations = '["Commercial"]'
        p1.services = '["3D"]'

        _, ws2, _, p2, _ = create_agency_fixture(db, "comb2@test.com", "Apex Sound", is_published=True)
        p2.specializations = '["Commercial"]'
        p2.services = '["Audio Mixing"]'
        db.commit()

    with TestClient(app) as client:
        resp = client.get("/api/discovery/agencies?query=Apex&service=3D")
        assert resp.status_code == 200
        data = resp.json()
        ids = [item["workspace_id"] for item in data]
        assert ws1.id in ids
        assert ws2.id not in ids


def test_30_discovery_catalog_no_matches_returns_empty_list(isolated_db):
    """Test 30: When query matches nothing, return HTTP 200 with empty list."""
    with TestClient(app) as client:
        resp = client.get("/api/discovery/agencies?query=NonExistentAgencyQuery_999999")
        assert resp.status_code == 200
        assert resp.json() == []


def test_31_discovery_catalog_unauthenticated_access(isolated_db):
    """Test 31: Public discovery endpoint requires no authentication header or cookie."""
    with TestClient(app) as client:
        resp = client.get("/api/discovery/agencies")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


def test_32_discovery_catalog_sql_injection_resilience(isolated_db):
    """Test 32: Malicious SQL or script payloads in query parameters are safely handled."""
    with TestClient(app) as client:
        resp1 = client.get("/api/discovery/agencies?query=' OR 1=1 --")
        assert resp1.status_code == 200
        assert resp1.json() == []

        resp2 = client.get("/api/discovery/agencies?specialization=<script>alert(1)</script>")
        assert resp2.status_code == 200
        assert resp2.json() == []


# ==============================================================================
# Group 7: Detailed Agency View (GET /api/discovery/agencies/{workspace_id}) (Tests 33-39)
# ==============================================================================

def test_33_discovery_detail_published_public_access(isolated_db):
    """Test 33: Unauthenticated visitor can view full details of a published agency."""
    with isolated_db() as db:
        _, ws, _, p, _ = create_agency_fixture(db, "public_detail@test.com", "Public Detail Studio", is_published=True)
        p.tagline = "Publicly accessible tagline"
        p.description = "Publicly accessible description"
        p.specializations = '["commercial"]'
        p.services = '["editing"]'
        p.portfolio = json.dumps([{"title": "Demo Reel", "video_url": "https://vimeo.com/1", "thumbnail_url": "", "description": "Demo"}])
        db.commit()

    with TestClient(app) as client:
        resp = client.get(f"/api/discovery/agencies/{ws.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["workspace_id"] == ws.id
        assert data["name"] == "Public Detail Studio"
        assert data["tagline"] == "Publicly accessible tagline"
        assert len(data["portfolio"]) == 1
        assert data["is_published"] is True


def test_34_discovery_detail_unpublished_returns_404_unauthenticated(isolated_db):
    """Test 34: Unauthenticated request to unpublished agency returns 404."""
    with isolated_db() as db:
        _, ws, _, _, _ = create_agency_fixture(db, "unpub_public@test.com", "Secret Agency", is_published=False)

    with TestClient(app) as client:
        resp = client.get(f"/api/discovery/agencies/{ws.id}")
        assert resp.status_code == 404


def test_35_discovery_detail_unpublished_returns_404_for_client(isolated_db):
    """Test 35: Authenticated client accessing an unpublished agency receives 404."""
    with isolated_db() as db:
        _, ws, _, _, _ = create_agency_fixture(db, "secret_agency@test.com", "Secret Agency 2", is_published=False)
        _, client_token = create_client_fixture(db, "curious_client@test.com")

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {client_token}"
        resp = client.get(f"/api/discovery/agencies/{ws.id}")
        assert resp.status_code == 404


def test_36_discovery_detail_unpublished_returns_404_for_other_agency(isolated_db):
    """Test 36: Authenticated agency user from Workspace B receives 404 for unpublished Agency A."""
    with isolated_db() as db:
        _, ws_a, _, _, _ = create_agency_fixture(db, "agency_a@test.com", "Agency A Draft", is_published=False)
        _, ws_b, _, _, token_b = create_agency_fixture(db, "agency_b@test.com", "Agency B Active", is_published=True)

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token_b}"
        resp = client.get(f"/api/discovery/agencies/{ws_a.id}")
        assert resp.status_code == 404


def test_37_discovery_detail_unpublished_preview_mode_for_owner(isolated_db):
    """Test 37: Workspace owner can view their own unpublished agency profile in preview mode."""
    with isolated_db() as db:
        _, ws, _, p, token = create_agency_fixture(db, "owner_prev@test.com", "Preview Studio", is_published=False)
        p.tagline = "Draft Tagline"
        db.commit()

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        resp = client.get(f"/api/discovery/agencies/{ws.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["workspace_id"] == ws.id
        assert data["tagline"] == "Draft Tagline"
        assert data["is_published"] is False


def test_38_discovery_detail_unpublished_preview_mode_for_member(isolated_db):
    """Test 38: Agency member (non-owner) can preview their unpublished agency profile."""
    with isolated_db() as db:
        _, ws, _, p, _ = create_agency_fixture(db, "owner_m@test.com", "Member Preview Studio", is_published=False)
        p.tagline = "Member Viewable Draft"
        # Create an agency member in the same workspace
        member_user = User(
            email="member_user@test.com",
            password_hash=hash_password("Pass12345678!"),
            role="agency_member",
            full_name="Staff Editor",
        )
        db.add(member_user)
        db.flush()
        mem = Membership(user_id=member_user.id, workspace_id=ws.id, role="member")
        db.add(mem)
        db.commit()
        member_token = issue_token(member_user, mem)

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {member_token}"
        resp = client.get(f"/api/discovery/agencies/{ws.id}")
        assert resp.status_code == 200
        assert resp.json()["workspace_id"] == ws.id


def test_39_discovery_detail_nonexistent_workspace_returns_404(isolated_db):
    """Test 39: Querying a non-existent agency ID returns 404 Not Found."""
    with TestClient(app) as client:
        resp = client.get("/api/discovery/agencies/999999")
        assert resp.status_code == 404


# ==============================================================================
# Group 8: Cross-Tenant Security & RBAC (Tests 40-46)
# ==============================================================================

def test_40_client_cannot_get_agency_profile(isolated_db):
    """Test 40: Client user receives 403 when requesting GET /api/agency/profile."""
    with isolated_db() as db:
        _, client_token = create_client_fixture(db, "client40@test.com")

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {client_token}"
        resp = client.get("/api/agency/profile")
        assert resp.status_code == 403


def test_41_client_cannot_put_agency_profile(isolated_db):
    """Test 41: Client user receives 403 when requesting PUT /api/agency/profile."""
    with isolated_db() as db:
        _, client_token = create_client_fixture(db, "client41@test.com")

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {client_token}"
        resp = client.put("/api/agency/profile", json={"tagline": "Malicious Deface"})
        assert resp.status_code == 403


def test_42_client_cannot_publish_agency_profile(isolated_db):
    """Test 42: Client user receives 403 when requesting POST /api/agency/profile/publish."""
    with isolated_db() as db:
        _, client_token = create_client_fixture(db, "client42@test.com")

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {client_token}"
        resp = client.post("/api/agency/profile/publish")
        assert resp.status_code == 403


def test_43_client_cannot_unpublish_agency_profile(isolated_db):
    """Test 43: Client user receives 403 when requesting POST /api/agency/profile/unpublish."""
    with isolated_db() as db:
        _, client_token = create_client_fixture(db, "client43@test.com")

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {client_token}"
        resp = client.post("/api/agency/profile/unpublish")
        assert resp.status_code == 403


def test_44_unauthenticated_cannot_mutate_profile(isolated_db):
    """Test 44: Unauthenticated caller receives 401 on profile mutation endpoints."""
    with TestClient(app) as client:
        r_put = client.put("/api/agency/profile", json={"tagline": "Hack"})
        assert r_put.status_code == 401

        r_pub = client.post("/api/agency/profile/publish")
        assert r_pub.status_code == 401

        r_unpub = client.post("/api/agency/profile/unpublish")
        assert r_unpub.status_code == 401


def test_45_agency_isolation_get_profile(isolated_db):
    """Test 45: Agency A calling GET /api/agency/profile receives only Agency A's profile."""
    with isolated_db() as db:
        _, ws_a, _, p_a, token_a = create_agency_fixture(db, "owner_a@test.com", "Agency Alpha")
        p_a.tagline = "Alpha Unique Tagline"
        _, ws_b, _, p_b, token_b = create_agency_fixture(db, "owner_b@test.com", "Agency Beta")
        p_b.tagline = "Beta Unique Tagline"
        db.commit()

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token_a}"
        resp = client.get("/api/agency/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["workspace_id"] == ws_a.id
        assert data["tagline"] == "Alpha Unique Tagline"


def test_46_agency_isolation_put_profile(isolated_db):
    """Test 46: Agency A modifying profile does not alter Agency B's profile."""
    with isolated_db() as db:
        _, ws_a, _, p_a, token_a = create_agency_fixture(db, "owner_a2@test.com", "Agency A2")
        p_a.tagline = "Alpha Original"
        _, ws_b, _, p_b, token_b = create_agency_fixture(db, "owner_b2@test.com", "Agency B2")
        p_b.tagline = "Beta Untouched"
        db.commit()

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token_a}"
        resp = client.put("/api/agency/profile", json={"tagline": "Alpha Modified"})
        assert resp.status_code == 200

    with isolated_db() as db:
        beta_refreshed = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == ws_b.id))
        assert beta_refreshed.tagline == "Beta Untouched"


# ==============================================================================
# Group 9: Zero Fabricated Data (Tests 47-49)
# ==============================================================================

def test_47_zero_fabricated_ratings_or_reviews(isolated_db):
    """Test 47: Verify response schemas contain zero fabricated rating or review metrics."""
    with isolated_db() as db:
        _, ws, _, _, token = create_agency_fixture(db, "real_data@test.com", "Real Data Studio", is_published=True)

    with TestClient(app) as client:
        # Discovery list
        r_list = client.get("/api/discovery/agencies")
        assert r_list.status_code == 200
        for item in r_list.json():
            for forbidden in ["rating", "star_rating", "stars", "review_count", "reviews", "testimonials"]:
                assert forbidden not in item, f"Fabricated metric '{forbidden}' found in discovery list"

        # Discovery detail
        r_detail = client.get(f"/api/discovery/agencies/{ws.id}")
        assert r_detail.status_code == 200
        detail_data = r_detail.json()
        for forbidden in ["rating", "star_rating", "stars", "review_count", "reviews", "testimonials"]:
            assert forbidden not in detail_data, f"Fabricated metric '{forbidden}' found in discovery detail"

        # Private profile
        client.headers["Authorization"] = f"Bearer {token}"
        r_prof = client.get("/api/agency/profile")
        assert r_prof.status_code == 200
        prof_data = r_prof.json()
        for forbidden in ["rating", "star_rating", "stars", "review_count", "reviews", "testimonials"]:
            assert forbidden not in prof_data, f"Fabricated metric '{forbidden}' found in agency profile"


def test_48_zero_artificial_badges_or_trust_scores(isolated_db):
    """Test 48: Verify responses contain zero artificial badges, ranks, or trust scores."""
    with isolated_db() as db:
        _, ws, _, _, _ = create_agency_fixture(db, "badge_free@test.com", "Badge Free Studio", is_published=True)

    with TestClient(app) as client:
        resp = client.get(f"/api/discovery/agencies/{ws.id}")
        assert resp.status_code == 200
        data = resp.json()
        for forbidden in ["badge", "badges", "trust_score", "verified_badge", "rank", "score"]:
            assert forbidden not in data, f"Artificial trust badge '{forbidden}' found in response"


def test_49_portfolio_contains_only_actual_entries(isolated_db):
    """Test 49: Portfolio in discovery detail returns only genuine user-created entries."""
    with isolated_db() as db:
        _, ws, _, p, _ = create_agency_fixture(db, "portfolio_genuine@test.com", "Genuine Studio", is_published=True)
        genuine_entries = [
            {"title": "Doc Edit", "video_url": "https://vimeo.com/doc", "thumbnail_url": "", "description": "45m doc"},
            {"title": "Music Video", "video_url": "https://vimeo.com/mv", "thumbnail_url": "", "description": "Rock video"},
        ]
        p.portfolio = json.dumps(genuine_entries)
        db.commit()

    with TestClient(app) as client:
        resp = client.get(f"/api/discovery/agencies/{ws.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["portfolio"]) == 2
        titles = [item["title"] for item in data["portfolio"]]
        assert titles == ["Doc Edit", "Music Video"]


def test_discovery_catalog_unicode_specializations_and_services(isolated_db):
    """Test 50: Verify that agency profile updated with non-ASCII specializations and services
    is successfully discoverable via discovery queries with international terms.
    """
    with isolated_db() as db:
        user, ws, mem, profile, token = create_agency_fixture(
            db, "tokyo_studio@test.com", "Tokyo Animation Studio", is_published=False
        )

    with TestClient(app) as client:
        client.headers["Authorization"] = f"Bearer {token}"
        # Update profile with non-ASCII Unicode strings
        update_payload = {
            "description": "Premiere animation and editing studio based in Tokyo and Barcelona.",
            "contact_email": "contact@tokyo-studio.com",
            "specializations": ["アニメーション", "Edición"],
            "services": ["Vidéo Editing", "カラーグレーディング"],
            "portfolio": [
                {
                    "title": "Anime Short Film アニメ作品",
                    "video_url": "https://vimeo.com/anime123",
                    "thumbnail_url": "",
                    "description": "Award-winning short",
                }
            ],
        }
        r_update = client.put("/api/agency/profile", json=update_payload)
        assert r_update.status_code == 200
        assert r_update.json()["specializations"] == ["アニメーション", "Edición"]
        assert r_update.json()["services"] == ["Vidéo Editing", "カラーグレーディング"]

        # Publish profile
        r_pub = client.post("/api/agency/profile/publish")
        assert r_pub.status_code == 200
        assert r_pub.json()["is_published"] is True

        # Unauthenticated / client discovery queries
        client.headers.pop("Authorization", None)

        # 1. Query specialization=アニメーション
        r1 = client.get("/api/discovery/agencies?specialization=アニメーション")
        assert r1.status_code == 200
        results1 = r1.json()
        assert len(results1) >= 1
        found_ids1 = [item["workspace_id"] for item in results1]
        assert ws.id in found_ids1
        tokyo_item = next(item for item in results1 if item["workspace_id"] == ws.id)
        assert "アニメーション" in tokyo_item["specializations"]

        # 2. Query specialization=Edición
        r2 = client.get("/api/discovery/agencies?specialization=Edición")
        assert r2.status_code == 200
        results2 = r2.json()
        assert len(results2) >= 1
        found_ids2 = [item["workspace_id"] for item in results2]
        assert ws.id in found_ids2

        # 3. Query service=Vidéo
        r3 = client.get("/api/discovery/agencies?service=Vidéo")
        assert r3.status_code == 200
        results3 = r3.json()
        assert len(results3) >= 1
        found_ids3 = [item["workspace_id"] for item in results3]
        assert ws.id in found_ids3

        # 4. Query category=アニメーション and category=Vidéo
        r4 = client.get("/api/discovery/agencies?category=アニメーション")
        assert r4.status_code == 200
        assert ws.id in [item["workspace_id"] for item in r4.json()]

        # 5. Direct detail endpoint GET /api/discovery/agencies/{ws.id}
        r5 = client.get(f"/api/discovery/agencies/{ws.id}")
        assert r5.status_code == 200
        detail_data = r5.json()
        assert detail_data["specializations"] == ["アニメーション", "Edición"]
        assert detail_data["services"] == ["Vidéo Editing", "カラーグレーディング"]
        assert detail_data["portfolio"][0]["title"] == "Anime Short Film アニメ作品"

