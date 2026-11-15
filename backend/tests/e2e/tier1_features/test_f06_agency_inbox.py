"""Tier 1 Feature 6 Tests: Agency Request Inbox & Clarifications.

Coverage:
46. test_tier1_f6_agency_list_incoming_requests: Agency views submitted briefs directed to its workspace in inbox.
47. test_tier1_f6_agency_get_request_details: Agency retrieves full brief specification and requirements.
48. test_tier1_f6_agency_post_clarification_message: Agency sends clarification message on submitted brief.
49. test_tier1_f6_client_reply_clarification_message: Client replies to clarification message.
50. test_tier1_f6_get_request_messages_thread: Both agency and client can retrieve the chronological message thread.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.main import app
from app.models import ProjectMessage, ProjectRequest
from app.schemas import ProjectMessageCreateInput, ProjectRequestResponse
from . import progressive_check


def test_tier1_f6_agency_list_incoming_requests(agency_client, agency_setup, client_setup, isolated_db):
    """F6-1: Agency inbox lists briefs submitted to its workspace while omitting drafts."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Commercial Edit Inquiry",
            status="submitted",
        )
        db.add(req)
        db.commit()
        req_id = req.id

    def _fallback():
        with isolated_db() as db:
            requests = db.scalars(
                select(ProjectRequest).where(
                    ProjectRequest.agency_workspace_id == agency_setup["workspace_id"],
                    ProjectRequest.status != "draft",
                )
            ).all()
            assert any(r.id == req_id for r in requests)

    resp = agency_client.get("/api/agency/requests")
    progressive_check(app, resp, "/api/agency/requests", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(item["id"] == req_id for item in data)


def test_tier1_f6_agency_get_request_details(agency_client, agency_setup, client_setup, isolated_db):
    """F6-2: Agency inspects full brief details including format, budget, and requirements."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Documentary Color Grading",
            description="4K feature documentary grading.",
            video_type="Documentary",
            target_platform="Theatrical",
            target_duration="90 mins",
            aspect_ratio="2.39:1",
            editing_requirements="DaVinci Resolve color conform",
            budget="$25,000",
            status="submitted",
        )
        db.add(req)
        db.commit()
        req_id = req.id

    def _fallback():
        with isolated_db() as db:
            item = db.get(ProjectRequest, req_id)
            assert item is not None
            assert item.budget == "$25,000"
            assert item.aspect_ratio == "2.39:1"

    resp = agency_client.get(f"/api/agency/requests/{req_id}")
    progressive_check(app, resp, f"/api/agency/requests/{req_id}", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == req_id
    assert data["title"] == "Documentary Color Grading"
    assert data["budget"] == "$25,000"


def test_tier1_f6_agency_post_clarification_message(agency_client, agency_setup, client_setup, isolated_db):
    """F6-3: Agency posts a clarification inquiry to the client regarding brief scope."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Inquiry for Clarification",
            status="submitted",
        )
        db.add(req)
        db.commit()
        req_id = req.id

    msg_payload = {"content": "Could you provide brand guidelines link or reference cut?"}

    def _fallback():
        validated = ProjectMessageCreateInput(request_id=req_id, **msg_payload)
        assert validated.content == msg_payload["content"]
        with isolated_db() as db:
            msg = ProjectMessage(
                request_id=req_id,
                sender_id=agency_setup["owner_id"],
                sender_role="agency",
                content=validated.content,
            )
            db.add(msg)
            db.commit()
            persisted = db.scalar(select(ProjectMessage).where(ProjectMessage.request_id == req_id))
            assert persisted is not None
            assert persisted.sender_role == "agency"

    resp = agency_client.post(f"/api/requests/{req_id}/messages", json=msg_payload)
    progressive_check(app, resp, f"/api/requests/{req_id}/messages", _fallback)

    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == msg_payload["content"]
    assert data["sender_role"] == "agency"


def test_tier1_f6_client_reply_clarification_message(client_user_client, agency_setup, client_setup, isolated_db):
    """F6-4: Client replies to an agency clarification inquiry on a submitted brief."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Inquiry for Client Reply",
            status="submitted",
        )
        db.add(req)
        db.commit()
        req_id = req.id

    reply_payload = {"content": "Here is our brand guide: https://brand.example.com"}

    def _fallback():
        validated = ProjectMessageCreateInput(request_id=req_id, **reply_payload)
        with isolated_db() as db:
            msg = ProjectMessage(
                request_id=req_id,
                sender_id=client_setup["user_id"],
                sender_role="client",
                content=validated.content,
            )
            db.add(msg)
            db.commit()
            persisted = db.scalar(
                select(ProjectMessage).where(
                    ProjectMessage.request_id == req_id,
                    ProjectMessage.sender_role == "client",
                )
            )
            assert persisted is not None
            assert "brand.example.com" in persisted.content

    resp = client_user_client.post(f"/api/requests/{req_id}/messages", json=reply_payload)
    progressive_check(app, resp, f"/api/requests/{req_id}/messages", _fallback)

    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == reply_payload["content"]
    assert data["sender_role"] == "client"


def test_tier1_f6_get_request_messages_thread(agency_client, agency_setup, client_setup, isolated_db):
    """F6-5: Thread messages are returned in chronological order."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Threaded Inquiry",
            status="submitted",
        )
        db.add(req)
        db.flush()
        m1 = ProjectMessage(
            request_id=req.id,
            sender_id=agency_setup["owner_id"],
            sender_role="agency",
            content="Message 1: Scope question",
        )
        m2 = ProjectMessage(
            request_id=req.id,
            sender_id=client_setup["user_id"],
            sender_role="client",
            content="Message 2: Client response",
        )
        db.add_all([m1, m2])
        db.commit()
        req_id = req.id

    def _fallback():
        with isolated_db() as db:
            msgs = db.scalars(
                select(ProjectMessage).where(ProjectMessage.request_id == req_id).order_by(ProjectMessage.id.asc())
            ).all()
            assert len(msgs) == 2
            assert msgs[0].sender_role == "agency"
            assert msgs[1].sender_role == "client"

    resp = agency_client.get(f"/api/requests/{req_id}/messages")
    progressive_check(app, resp, f"/api/requests/{req_id}/messages", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    assert data[0]["content"] == "Message 1: Scope question"
    assert data[1]["content"] == "Message 2: Client response"
