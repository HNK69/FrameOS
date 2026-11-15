"""M4 Tests — Project Requests, Proposals & Acceptance Flow."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.main import app as fastapi_app
from app.db import get_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client(isolated_db: sessionmaker):
    with TestClient(fastapi_app, raise_server_exceptions=True) as c:
        yield c


def _register_client(client, email="client1@example.com", name="Test Client"):
    r = client.post("/api/auth/register/client", json={
        "email": email,
        "password": "securePass123",
        "full_name": name,
        "company_name": "Test Co",
    })
    assert r.status_code == 201, r.text
    return r.json()


def _register_agency(client, email="agency1@example.com", agency_name="Pixel Studio"):
    r = client.post("/api/auth/register/agency", json={
        "email": email,
        "password": "securePass456",
        "full_name": "Agency Owner",
        "agency_name": agency_name,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def _publish_agency(client, workspace_id):
    """Update agency profile to meet publishing requirements then publish."""
    client.put("/api/agency/profile", json={
        "description": "Professional video editing agency specializing in corporate content.",
        "contact_email": "agency1@example.com",
        "specializations": ["Corporate Video", "Motion Graphics"],
        "services": ["Video Editing", "Color Grading"],
    })
    r = client.post("/api/agency/profile/publish")
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Test Groups
# ---------------------------------------------------------------------------

class TestClientRequestLifecycle:
    def test_client_cannot_request_unpublished_agency(self, client):
        agency_data = _register_agency(client)
        workspace_id = agency_data["workspace_id"]

        client_data = _register_client(client)
        _login(client, "client1@example.com", "securePass123")

        r = client.post("/api/client/requests", json={
            "agency_workspace_id": workspace_id,
            "title": "My Video Project",
            "status": "submitted",
        })
        assert r.status_code == 404

    def test_client_submits_request_to_published_agency(self, client):
        agency_data = _register_agency(client)
        workspace_id = agency_data["workspace_id"]
        _publish_agency(client, workspace_id)

        _register_client(client)
        _login(client, "client1@example.com", "securePass123")

        r = client.post("/api/client/requests", json={
            "agency_workspace_id": workspace_id,
            "title": "Brand Video Q4",
            "description": "Need a 90-second brand video for Q4 campaign.",
            "video_type": "brand",
            "target_platform": "YouTube",
            "budget": "$5000-$8000",
            "status": "submitted",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "Brand Video Q4"
        assert data["status"] == "submitted"
        assert data["agency_workspace_id"] == workspace_id

    def test_client_lists_own_requests(self, client):
        agency_data = _register_agency(client)
        workspace_id = agency_data["workspace_id"]
        _publish_agency(client, workspace_id)

        _register_client(client)
        _login(client, "client1@example.com", "securePass123")

        client.post("/api/client/requests", json={
            "agency_workspace_id": workspace_id,
            "title": "Project Alpha",
            "status": "submitted",
        })
        client.post("/api/client/requests", json={
            "agency_workspace_id": workspace_id,
            "title": "Project Beta",
            "status": "draft",
        })

        r = client.get("/api/client/requests")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_client_gets_specific_request(self, client):
        agency_data = _register_agency(client)
        workspace_id = agency_data["workspace_id"]
        _publish_agency(client, workspace_id)

        _register_client(client)
        _login(client, "client1@example.com", "securePass123")

        create_r = client.post("/api/client/requests", json={
            "agency_workspace_id": workspace_id,
            "title": "Single Request",
            "status": "submitted",
        })
        req_id = create_r.json()["id"]

        r = client.get(f"/api/client/requests/{req_id}")
        assert r.status_code == 200
        assert r.json()["id"] == req_id

    def test_client_cannot_see_other_clients_requests(self, client):
        agency_data = _register_agency(client)
        workspace_id = agency_data["workspace_id"]
        _publish_agency(client, workspace_id)

        _register_client(client, email="client_a@example.com", name="Client A")
        _login(client, "client_a@example.com", "securePass123")
        create_r = client.post("/api/client/requests", json={
            "agency_workspace_id": workspace_id,
            "title": "Client A Request",
            "status": "submitted",
        })
        req_id = create_r.json()["id"]

        _register_client(client, email="client_b@example.com", name="Client B")
        _login(client, "client_b@example.com", "securePass123")

        r = client.get(f"/api/client/requests/{req_id}")
        assert r.status_code == 404

    def test_client_updates_draft_request(self, client):
        agency_data = _register_agency(client)
        workspace_id = agency_data["workspace_id"]
        _publish_agency(client, workspace_id)

        _register_client(client)
        _login(client, "client1@example.com", "securePass123")

        create_r = client.post("/api/client/requests", json={
            "agency_workspace_id": workspace_id,
            "title": "Draft Request",
            "status": "draft",
        })
        req_id = create_r.json()["id"]

        r = client.patch(f"/api/client/requests/{req_id}", json={
            "title": "Updated Draft Request",
            "budget": "$3000",
        })
        assert r.status_code == 200
        assert r.json()["title"] == "Updated Draft Request"


class TestAgencyProposalFlow:
    def test_agency_sees_incoming_requests(self, client):
        agency_data = _register_agency(client)
        workspace_id = agency_data["workspace_id"]
        _publish_agency(client, workspace_id)

        _register_client(client)
        _login(client, "client1@example.com", "securePass123")
        client.post("/api/client/requests", json={
            "agency_workspace_id": workspace_id,
            "title": "Incoming Request",
            "status": "submitted",
        })

        _login(client, "agency1@example.com", "securePass456")
        r = client.get("/api/agency/requests")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["title"] == "Incoming Request"

    def test_agency_submits_proposal(self, client):
        agency_data = _register_agency(client)
        workspace_id = agency_data["workspace_id"]
        _publish_agency(client, workspace_id)

        _register_client(client)
        _login(client, "client1@example.com", "securePass123")
        create_r = client.post("/api/client/requests", json={
            "agency_workspace_id": workspace_id,
            "title": "Project Gamma",
            "status": "submitted",
        })
        req_id = create_r.json()["id"]

        _login(client, "agency1@example.com", "securePass456")
        r = client.post(f"/api/agency/requests/{req_id}/proposals", json={
            "scope_description": "We will produce a 90-second brand film.",
            "estimated_days": 14,
            "deliverables_summary": "1x final edit, 3x revisions included",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["scope_description"] == "We will produce a 90-second brand film."
        assert data["status"] == "pending"

    def test_agency_cannot_duplicate_proposal(self, client):
        agency_data = _register_agency(client)
        workspace_id = agency_data["workspace_id"]
        _publish_agency(client, workspace_id)

        _register_client(client)
        _login(client, "client1@example.com", "securePass123")
        create_r = client.post("/api/client/requests", json={
            "agency_workspace_id": workspace_id,
            "title": "Duplicate Test",
            "status": "submitted",
        })
        req_id = create_r.json()["id"]

        _login(client, "agency1@example.com", "securePass456")
        client.post(f"/api/agency/requests/{req_id}/proposals", json={
            "scope_description": "First proposal",
            "estimated_days": 7,
        })
        r = client.post(f"/api/agency/requests/{req_id}/proposals", json={
            "scope_description": "Duplicate attempt",
            "estimated_days": 10,
        })
        assert r.status_code == 409

    def test_request_status_becomes_proposal_received_after_proposal(self, client):
        agency_data = _register_agency(client)
        workspace_id = agency_data["workspace_id"]
        _publish_agency(client, workspace_id)

        _register_client(client)
        _login(client, "client1@example.com", "securePass123")
        create_r = client.post("/api/client/requests", json={
            "agency_workspace_id": workspace_id,
            "title": "Status Check",
            "status": "submitted",
        })
        req_id = create_r.json()["id"]

        _login(client, "agency1@example.com", "securePass456")
        client.post(f"/api/agency/requests/{req_id}/proposals", json={
            "scope_description": "Full production package",
            "estimated_days": 21,
        })

        _login(client, "client1@example.com", "securePass123")
        r = client.get(f"/api/client/requests/{req_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "proposal_received"


class TestProposalAcceptanceFlow:
    def test_client_accepts_proposal_creates_project(self, client):
        agency_data = _register_agency(client)
        workspace_id = agency_data["workspace_id"]
        _publish_agency(client, workspace_id)

        _register_client(client)
        _login(client, "client1@example.com", "securePass123")
        create_r = client.post("/api/client/requests", json={
            "agency_workspace_id": workspace_id,
            "title": "Acceptance Test Project",
            "status": "submitted",
        })
        req_id = create_r.json()["id"]

        _login(client, "agency1@example.com", "securePass456")
        prop_r = client.post(f"/api/agency/requests/{req_id}/proposals", json={
            "scope_description": "Complete production",
            "estimated_days": 14,
        })
        prop_id = prop_r.json()["id"]

        _login(client, "client1@example.com", "securePass123")
        r = client.post(f"/api/client/requests/{req_id}/proposals/{prop_id}/accept")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "accepted"
        assert data["project_id"] is not None

    def test_client_declines_proposal(self, client):
        agency_data = _register_agency(client)
        workspace_id = agency_data["workspace_id"]
        _publish_agency(client, workspace_id)

        _register_client(client)
        _login(client, "client1@example.com", "securePass123")
        create_r = client.post("/api/client/requests", json={
            "agency_workspace_id": workspace_id,
            "title": "Decline Test",
            "status": "submitted",
        })
        req_id = create_r.json()["id"]

        _login(client, "agency1@example.com", "securePass456")
        prop_r = client.post(f"/api/agency/requests/{req_id}/proposals", json={
            "scope_description": "Proposal to decline",
            "estimated_days": 7,
        })
        prop_id = prop_r.json()["id"]

        _login(client, "client1@example.com", "securePass123")
        r = client.post(f"/api/client/requests/{req_id}/proposals/{prop_id}/decline")
        assert r.status_code == 200
        assert r.json()["status"] == "declined"

    def test_cannot_accept_already_accepted_proposal(self, client):
        agency_data = _register_agency(client)
        workspace_id = agency_data["workspace_id"]
        _publish_agency(client, workspace_id)

        _register_client(client)
        _login(client, "client1@example.com", "securePass123")
        create_r = client.post("/api/client/requests", json={
            "agency_workspace_id": workspace_id,
            "title": "Double Accept Test",
            "status": "submitted",
        })
        req_id = create_r.json()["id"]

        _login(client, "agency1@example.com", "securePass456")
        prop_r = client.post(f"/api/agency/requests/{req_id}/proposals", json={
            "scope_description": "Accepted once",
            "estimated_days": 10,
        })
        prop_id = prop_r.json()["id"]

        _login(client, "client1@example.com", "securePass123")
        client.post(f"/api/client/requests/{req_id}/proposals/{prop_id}/accept")
        r = client.post(f"/api/client/requests/{req_id}/proposals/{prop_id}/accept")
        assert r.status_code == 400


class TestClientProfile:
    def test_client_gets_profile(self, client):
        _register_client(client)
        _login(client, "client1@example.com", "securePass123")
        r = client.get("/api/client/profile")
        assert r.status_code == 200
        assert r.json()["email"] == "client1@example.com"

    def test_agency_cannot_access_client_profile(self, client):
        _register_agency(client)
        _login(client, "agency1@example.com", "securePass456")
        r = client.get("/api/client/profile")
        assert r.status_code == 403


class TestMessaging:
    def test_client_sends_message(self, client):
        agency_data = _register_agency(client)
        workspace_id = agency_data["workspace_id"]
        _publish_agency(client, workspace_id)

        _register_client(client)
        _login(client, "client1@example.com", "securePass123")
        create_r = client.post("/api/client/requests", json={
            "agency_workspace_id": workspace_id,
            "title": "Messaging Test",
            "status": "submitted",
        })
        req_id = create_r.json()["id"]

        r = client.post("/api/messages", json={
            "request_id": req_id,
            "content": "Hello, excited to work with you!",
        })
        assert r.status_code == 201
        assert r.json()["sender_role"] == "client"

    def test_agency_sends_reply(self, client):
        agency_data = _register_agency(client)
        workspace_id = agency_data["workspace_id"]
        _publish_agency(client, workspace_id)

        _register_client(client)
        _login(client, "client1@example.com", "securePass123")
        create_r = client.post("/api/client/requests", json={
            "agency_workspace_id": workspace_id,
            "title": "Agency Reply Test",
            "status": "submitted",
        })
        req_id = create_r.json()["id"]

        _login(client, "agency1@example.com", "securePass456")
        r = client.post("/api/agency/messages", json={
            "request_id": req_id,
            "content": "Thank you for your interest! We'd love to help.",
        })
        assert r.status_code == 201
        assert r.json()["sender_role"] == "agency"

    def test_client_lists_thread(self, client):
        agency_data = _register_agency(client)
        workspace_id = agency_data["workspace_id"]
        _publish_agency(client, workspace_id)

        _register_client(client)
        _login(client, "client1@example.com", "securePass123")
        create_r = client.post("/api/client/requests", json={
            "agency_workspace_id": workspace_id,
            "title": "Thread Test",
            "status": "submitted",
        })
        req_id = create_r.json()["id"]
        client.post("/api/messages", json={"request_id": req_id, "content": "Client msg 1"})

        _login(client, "agency1@example.com", "securePass456")
        client.post("/api/agency/messages", json={"request_id": req_id, "content": "Agency reply"})

        _login(client, "client1@example.com", "securePass123")
        r = client.get(f"/api/requests/{req_id}/messages")
        assert r.status_code == 200
        assert len(r.json()) == 2
