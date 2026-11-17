"""Tier 1 Feature 5 Tests: Structured Brief Creation & Drafts.

Coverage:
41. test_tier1_f5_create_submitted_brief: Client submits a fully structured project brief directly to an agency.
42. test_tier1_f5_create_draft_brief: Client saves a project brief in draft status for later completion.
43. test_tier1_f5_list_client_briefs: Client retrieves list of all own project briefs (drafts and submitted).
44. test_tier1_f5_update_draft_brief: Client updates content fields of a saved draft brief.
45. test_tier1_f5_transition_draft_to_submitted: Client transitions a draft brief to submitted status.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.main import app
from app.models import ProjectRequest
from app.schemas import ProjectRequestCreateInput, ProjectRequestUpdateInput
from . import progressive_check


def test_tier1_f5_create_submitted_brief(client_user_client, client_setup, agency_setup, isolated_db):
    """F5-1: Client creates and immediately submits a structured project brief."""
    payload = {
        "agency_workspace_id": agency_setup["workspace_id"],
        "title": "Nike Brand Commercial 2026",
        "description": "High-energy commercial focusing on urban runners.",
        "video_type": "Commercial",
        "target_platform": "YouTube & Instagram",
        "target_duration": "60 seconds",
        "budget": "$10,000",
        "status": "submitted",
    }

    def _fallback():
        validated = ProjectRequestCreateInput(**payload)
        assert validated.title == "Nike Brand Commercial 2026"
        assert validated.status == "submitted"
        with isolated_db() as db:
            pr = ProjectRequest(
                client_user_id=client_setup["user_id"],
                agency_workspace_id=payload["agency_workspace_id"],
                title=validated.title,
                description=validated.description,
                video_type=validated.video_type,
                target_platform=validated.target_platform,
                target_duration=validated.target_duration,
                budget=validated.budget,
                status=validated.status,
            )
            db.add(pr)
            db.commit()
            persisted = db.scalar(select(ProjectRequest).where(ProjectRequest.title == payload["title"]))
            assert persisted is not None
            assert persisted.status == "submitted"
            assert persisted.client_user_id == client_setup["user_id"]

    resp = client_user_client.post("/api/client/requests", json=payload)
    progressive_check(app, resp, "/api/client/requests", _fallback)

    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] > 0
    assert data["status"] == "submitted"
    assert data["client_user_id"] == client_setup["user_id"]
    assert data["agency_workspace_id"] == agency_setup["workspace_id"]


def test_tier1_f5_create_draft_brief(client_user_client, client_setup, agency_setup, isolated_db):
    """F5-2: Client saves an incomplete project brief as a draft."""
    payload = {
        "agency_workspace_id": agency_setup["workspace_id"],
        "title": "Early Stage Brand Teaser",
        "status": "draft",
    }

    def _fallback():
        validated = ProjectRequestCreateInput(**payload)
        assert validated.status == "draft"
        with isolated_db() as db:
            pr = ProjectRequest(
                client_user_id=client_setup["user_id"],
                agency_workspace_id=payload["agency_workspace_id"],
                title=validated.title,
                status=validated.status,
            )
            db.add(pr)
            db.commit()
            persisted = db.scalar(select(ProjectRequest).where(ProjectRequest.title == payload["title"]))
            assert persisted is not None
            assert persisted.status == "draft"

    resp = client_user_client.post("/api/client/requests", json=payload)
    progressive_check(app, resp, "/api/client/requests", _fallback)

    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] > 0
    assert data["status"] == "draft"


def test_tier1_f5_list_client_briefs(client_user_client, client_setup, agency_setup, isolated_db):
    """F5-3: Client retrieves all authored briefs including drafts and submitted requests."""
    # Seed one draft and one submitted brief in isolated_db
    with isolated_db() as db:
        r1 = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Seeded Brief Draft 1",
            status="draft",
        )
        r2 = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Seeded Brief Submitted 2",
            status="submitted",
        )
        db.add_all([r1, r2])
        db.commit()

    def _fallback():
        with isolated_db() as db:
            items = db.scalars(
                select(ProjectRequest).where(ProjectRequest.client_user_id == client_setup["user_id"])
            ).all()
            assert len(items) >= 2

    resp = client_user_client.get("/api/client/requests")
    progressive_check(app, resp, "/api/client/requests", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2


def test_tier1_f5_update_draft_brief(client_user_client, client_setup, agency_setup, isolated_db):
    """F5-4: Client modifies details of an existing draft brief."""
    with isolated_db() as db:
        draft = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Draft to Update",
            description="Initial brief note",
            status="draft",
        )
        db.add(draft)
        db.commit()
        draft_id = draft.id

    update_payload = {
        "description": "Refined creative brief with expanded scope.",
        "budget": "$15,000",
    }

    def _fallback():
        validated = ProjectRequestUpdateInput(**update_payload)
        with isolated_db() as db:
            pr = db.get(ProjectRequest, draft_id)
            assert pr is not None
            pr.description = validated.description or pr.description
            pr.budget = validated.budget or pr.budget
            db.commit()
            refreshed = db.get(ProjectRequest, draft_id)
            assert refreshed.description == "Refined creative brief with expanded scope."
            assert refreshed.budget == "$15,000"

    resp = client_user_client.patch(f"/api/client/requests/{draft_id}", json=update_payload)
    progressive_check(app, resp, f"/api/client/requests/{draft_id}", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert data["description"] == "Refined creative brief with expanded scope."
    assert data["budget"] == "$15,000"


def test_tier1_f5_transition_draft_to_submitted(client_user_client, client_setup, agency_setup, isolated_db):
    """F5-5: Client transitions a draft brief into submitted status, publishing it to agency inbox."""
    with isolated_db() as db:
        draft = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Draft Ready to Submit",
            status="draft",
        )
        db.add(draft)
        db.commit()
        draft_id = draft.id

    transition_payload = {"status": "submitted"}

    def _fallback():
        with isolated_db() as db:
            pr = db.get(ProjectRequest, draft_id)
            assert pr is not None
            pr.status = "submitted"
            db.commit()
            persisted = db.get(ProjectRequest, draft_id)
            assert persisted.status == "submitted"

    resp = client_user_client.patch(f"/api/client/requests/{draft_id}", json=transition_payload)
    progressive_check(app, resp, f"/api/client/requests/{draft_id}", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "submitted"
