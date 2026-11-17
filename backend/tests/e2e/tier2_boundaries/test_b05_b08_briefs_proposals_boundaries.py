"""Tier 2 Boundary, Error, and Security Tests: Features 5 to 8.

Coverage:
- Feature 5: Structured Briefs Boundaries (Tests 61 to 65)
  61. test_tier2_f5_create_brief_nonexistent_agency: 404 Not Found when agency_workspace_id does not exist.
  62. test_tier2_f5_create_brief_empty_title: 422 Unprocessable Entity when title is blank.
  63. test_tier2_f5_agency_user_cannot_create_client_brief: 403 Forbidden when agency user attempts client brief creation.
  64. test_tier2_f5_client_cannot_access_other_client_draft: 403 Forbidden or 404 Not Found on cross-client draft access.
  65. test_tier2_f5_create_brief_invalid_status: 422 Unprocessable Entity when status is not 'draft' or 'submitted'.
- Feature 6: Agency Request Inbox & Clarifications Boundaries (Tests 66 to 70)
  66. test_tier2_f6_agency_cannot_see_client_drafts: Agency inbox strictly omits client draft briefs.
  67. test_tier2_f6_agency_b_cannot_view_agency_a_request: 403/404 on cross-agency inquiry snooping.
  68. test_tier2_f6_post_message_empty_content: 422 Unprocessable Entity on empty message content.
  69. test_tier2_f6_unrelated_client_cannot_message_request: 403/404 when unrelated client messages another client's request.
  70. test_tier2_f6_unauthenticated_cannot_access_messages: 401 Unauthorized when accessing messages without auth.
- Feature 7: Agency Proposals Boundaries (Tests 71 to 75)
  71. test_tier2_f7_proposal_invalid_estimated_days: 422 Unprocessable Entity when estimated_days <= 0 or > 365.
  72. test_tier2_f7_proposal_empty_scope_description: 422 Unprocessable Entity when scope_description is empty.
  73. test_tier2_f7_agency_cannot_propose_on_other_agency_request: 403/404 when Agency B proposes on Agency A's brief.
  74. test_tier2_f7_cannot_propose_on_draft_request: 400 Bad Request or 404 Not Found when creating proposal on draft brief.
  75. test_tier2_f7_client_cannot_create_proposal: 403 Forbidden when client user attempts to author a proposal.
- Feature 8: Proposal Acceptance Lifecycle Boundaries (Tests 76 to 80)
  76. test_tier2_f8_unrelated_client_cannot_accept_proposal: 403/404 when Client B attempts to accept Client A's proposal.
  77. test_tier2_f8_agency_cannot_accept_own_proposal: 403 Forbidden when agency attempts to accept proposals.
  78. test_tier2_f8_cannot_accept_already_accepted_proposal: 400 Bad Request on double acceptance of an accepted proposal.
  79. test_tier2_f8_cannot_accept_declined_proposal: 400 Bad Request when attempting to accept a declined proposal.
  80. test_tier2_f8_accept_nonexistent_proposal: 404 Not Found when accepting nonexistent proposal ID 999999.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app.main import app
from app.models import ProjectRequest, Proposal, Workspace
from app.schemas import (
    ProjectMessageCreateInput,
    ProjectRequestCreateInput,
    ProposalCreateInput,
)

from . import progressive_check

# ==============================================================================
# Feature 5: Structured Briefs Boundaries (Tests 61-65)
# ==============================================================================

def test_tier2_f5_create_brief_nonexistent_agency(client_user_client, client_setup, isolated_db):
    """F5-B1: Submitting a brief to nonexistent agency workspace returns 404 Not Found."""
    payload = {
        "agency_workspace_id": 999999,
        "title": "Brief to Phantom Agency",
        "status": "submitted",
    }

    def _fallback():
        with isolated_db() as db:
            ws = db.get(Workspace, 999999)
            assert ws is None

    resp = client_user_client.post("/api/client/requests", json=payload)
    progressive_check(app, resp, "/api/client/requests", _fallback)
    assert resp.status_code in (400, 404)


def test_tier2_f5_create_brief_empty_title(client_user_client, agency_setup):
    """F5-B2: Empty title is rejected with 422 Unprocessable Entity."""
    payload = {
        "agency_workspace_id": agency_setup["workspace_id"],
        "title": "",
        "status": "submitted",
    }

    def _fallback():
        with pytest.raises(ValidationError):
            ProjectRequestCreateInput(**payload)

    resp = client_user_client.post("/api/client/requests", json=payload)
    progressive_check(app, resp, "/api/client/requests", _fallback)
    assert resp.status_code == 422


def test_tier2_f5_agency_user_cannot_create_client_brief(agency_client, agency_setup):
    """F5-B3: Agency session cannot create briefs via client endpoint (403 Forbidden)."""
    payload = {
        "agency_workspace_id": agency_setup["workspace_id"],
        "title": "Agency Attempt to Author Brief",
        "status": "submitted",
    }

    resp = agency_client.post("/api/client/requests", json=payload)
    progressive_check(app, resp, "/api/client/requests", lambda: None)
    assert resp.status_code in (401, 403)


def test_tier2_f5_client_cannot_access_other_client_draft(foreign_client_client, client_setup, agency_setup, isolated_db):
    """F5-B4: Client B cannot view or access Client A's draft brief (cross-tenant isolation)."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Private Draft of Client A",
            status="draft",
        )
        db.add(req)
        db.commit()
        req_id = req.id

    def _fallback():
        with isolated_db() as db:
            r = db.get(ProjectRequest, req_id)
            assert r is not None
            assert r.client_user_id == client_setup["user_id"]

    resp = foreign_client_client.get(f"/api/client/requests/{req_id}")
    progressive_check(app, resp, f"/api/client/requests/{req_id}", _fallback)
    assert resp.status_code in (403, 404)


def test_tier2_f5_create_brief_invalid_status(client_user_client, agency_setup):
    """F5-B5: Status outside allowed set (draft, submitted) returns 422 Unprocessable Entity."""
    payload = {
        "agency_workspace_id": agency_setup["workspace_id"],
        "title": "Brief with Illegal Status",
        "status": "invalid_status_xyz",
    }

    def _fallback():
        with pytest.raises(ValidationError):
            ProjectRequestCreateInput(**payload)

    resp = client_user_client.post("/api/client/requests", json=payload)
    progressive_check(app, resp, "/api/client/requests", _fallback)
    assert resp.status_code == 422


# ==============================================================================
# Feature 6: Agency Request Inbox & Clarifications Boundaries (Tests 66-70)
# ==============================================================================

def test_tier2_f6_agency_cannot_see_client_drafts(agency_client, agency_setup, client_setup, isolated_db):
    """F6-B1: Agency inbox does not leak client draft briefs."""
    with isolated_db() as db:
        draft = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Unfinished Private Client Draft",
            status="draft",
        )
        db.add(draft)
        db.commit()
        draft_id = draft.id

    def _fallback():
        with isolated_db() as db:
            agency_visible = db.scalars(
                select(ProjectRequest).where(
                    ProjectRequest.agency_workspace_id == agency_setup["workspace_id"],
                    ProjectRequest.status != "draft",
                )
            ).all()
            assert all(r.id != draft_id for r in agency_visible)

    resp = agency_client.get("/api/agency/requests")
    progressive_check(app, resp, "/api/agency/requests", _fallback)
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["id"] != draft_id for item in data)


def test_tier2_f6_agency_b_cannot_view_agency_a_request(foreign_agency_client, agency_setup, client_setup, isolated_db):
    """F6-B2: Agency B cannot view requests directed to Agency A (cross-agency isolation)."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Private Brief for Agency A",
            status="submitted",
        )
        db.add(req)
        db.commit()
        req_id = req.id

    def _fallback():
        with isolated_db() as db:
            r = db.get(ProjectRequest, req_id)
            assert r is not None
            assert r.agency_workspace_id == agency_setup["workspace_id"]

    resp = foreign_agency_client.get(f"/api/agency/requests/{req_id}")
    progressive_check(app, resp, f"/api/agency/requests/{req_id}", _fallback)
    assert resp.status_code in (403, 404)


def test_tier2_f6_post_message_empty_content(agency_client, agency_setup, client_setup, isolated_db):
    """F6-B3: Empty message content returns 422 Unprocessable Entity."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Message Validation Brief",
            status="submitted",
        )
        db.add(req)
        db.commit()
        req_id = req.id

    def _fallback():
        with pytest.raises(ValidationError):
            ProjectMessageCreateInput(request_id=req_id, content="")

    resp = agency_client.post(f"/api/requests/{req_id}/messages", json={"content": ""})
    progressive_check(app, resp, f"/api/requests/{req_id}/messages", _fallback)
    assert resp.status_code == 422


def test_tier2_f6_unrelated_client_cannot_message_request(foreign_client_client, agency_setup, client_setup, isolated_db):
    """F6-B4: Unrelated Client B cannot send clarification messages on Client A's brief."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Client A Private Brief",
            status="submitted",
        )
        db.add(req)
        db.commit()
        req_id = req.id

    def _fallback():
        with isolated_db() as db:
            r = db.get(ProjectRequest, req_id)
            assert r is not None
            assert r.client_user_id == client_setup["user_id"]

    resp = foreign_client_client.post(f"/api/requests/{req_id}/messages", json={"content": "Intruder inquiry"})
    progressive_check(app, resp, f"/api/requests/{req_id}/messages", _fallback)
    assert resp.status_code in (403, 404)


def test_tier2_f6_unauthenticated_cannot_access_messages(agency_setup, client_setup, isolated_db):
    """F6-B5: Accessing request messages without authentication returns 401 Unauthorized."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Unauthenticated Message Check",
            status="submitted",
        )
        db.add(req)
        db.commit()
        req_id = req.id

    with TestClient(app) as client:
        resp = client.get(f"/api/requests/{req_id}/messages")
        progressive_check(app, resp, f"/api/requests/{req_id}/messages", lambda: None)
        assert resp.status_code == 401


# ==============================================================================
# Feature 7: Agency Proposals Boundaries (Tests 71-75)
# ==============================================================================

def test_tier2_f7_proposal_invalid_estimated_days(agency_client, agency_setup, client_setup, isolated_db):
    """F7-B1: Estimated days <= 0 or > 365 returns 422 Unprocessable Entity."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Days Validation Check",
            status="submitted",
        )
        db.add(req)
        db.commit()
        req_id = req.id

    def _fallback():
        with pytest.raises(ValidationError):
            ProposalCreateInput(scope_description="Valid scope", estimated_days=0)
        with pytest.raises(ValidationError):
            ProposalCreateInput(scope_description="Valid scope", estimated_days=500)

    resp = agency_client.post(
        f"/api/agency/requests/{req_id}/proposals",
        json={"scope_description": "Valid scope", "estimated_days": 0},
    )
    progressive_check(app, resp, f"/api/agency/requests/{req_id}/proposals", _fallback)
    assert resp.status_code == 422


def test_tier2_f7_proposal_empty_scope_description(agency_client, agency_setup, client_setup, isolated_db):
    """F7-B2: Empty scope description returns 422 Unprocessable Entity."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Scope Validation Check",
            status="submitted",
        )
        db.add(req)
        db.commit()
        req_id = req.id

    def _fallback():
        with pytest.raises(ValidationError):
            ProposalCreateInput(scope_description="", estimated_days=5)

    resp = agency_client.post(
        f"/api/agency/requests/{req_id}/proposals",
        json={"scope_description": "", "estimated_days": 5},
    )
    progressive_check(app, resp, f"/api/agency/requests/{req_id}/proposals", _fallback)
    assert resp.status_code == 422


def test_tier2_f7_agency_cannot_propose_on_other_agency_request(foreign_agency_client, agency_setup, client_setup, isolated_db):
    """F7-B3: Agency B cannot submit proposal for request submitted to Agency A."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Agency A Exclusive Request",
            status="submitted",
        )
        db.add(req)
        db.commit()
        req_id = req.id

    def _fallback():
        with isolated_db() as db:
            r = db.get(ProjectRequest, req_id)
            assert r is not None
            assert r.agency_workspace_id == agency_setup["workspace_id"]

    resp = foreign_agency_client.post(
        f"/api/agency/requests/{req_id}/proposals",
        json={"scope_description": "Unauthorized proposal", "estimated_days": 5},
    )
    progressive_check(app, resp, f"/api/agency/requests/{req_id}/proposals", _fallback)
    assert resp.status_code in (403, 404)


def test_tier2_f7_cannot_propose_on_draft_request(agency_client, agency_setup, client_setup, isolated_db):
    """F7-B4: Agency cannot create a proposal on a brief that remains in draft status."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Incomplete Draft Brief",
            status="draft",
        )
        db.add(req)
        db.commit()
        req_id = req.id

    def _fallback():
        with isolated_db() as db:
            r = db.get(ProjectRequest, req_id)
            assert r is not None
            assert r.status == "draft"

    resp = agency_client.post(
        f"/api/agency/requests/{req_id}/proposals",
        json={"scope_description": "Premature proposal", "estimated_days": 5},
    )
    progressive_check(app, resp, f"/api/agency/requests/{req_id}/proposals", _fallback)
    assert resp.status_code in (400, 404)


def test_tier2_f7_client_cannot_create_proposal(client_user_client, agency_setup, client_setup, isolated_db):
    """F7-B5: Client session cannot invoke agency proposal creation endpoint (403 Forbidden)."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Proposal Authorization Check",
            status="submitted",
        )
        db.add(req)
        db.commit()
        req_id = req.id

    resp = client_user_client.post(
        f"/api/agency/requests/{req_id}/proposals",
        json={"scope_description": "Client attempting agency operation", "estimated_days": 5},
    )
    progressive_check(app, resp, f"/api/agency/requests/{req_id}/proposals", lambda: None)
    assert resp.status_code in (401, 403)


# ==============================================================================
# Feature 8: Proposal Acceptance Lifecycle Boundaries (Tests 76-80)
# ==============================================================================

def test_tier2_f8_unrelated_client_cannot_accept_proposal(foreign_client_client, agency_setup, client_setup, isolated_db):
    """F8-B1: Client B cannot accept proposal for Client A's request."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Client A Protected Brief",
            status="proposal_received",
        )
        db.add(req)
        db.flush()
        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="Client A scope",
            estimated_days=7,
            status="pending",
        )
        db.add(prop)
        db.commit()
        prop_id = prop.id

    def _fallback():
        with isolated_db() as db:
            p = db.get(Proposal, prop_id)
            assert p is not None
            assert p.request.client_user_id == client_setup["user_id"]

    resp = foreign_client_client.post(f"/api/client/proposals/{prop_id}/accept")
    progressive_check(app, resp, f"/api/client/proposals/{prop_id}/accept", _fallback)
    assert resp.status_code in (403, 404)


def test_tier2_f8_agency_cannot_accept_own_proposal(agency_client, agency_setup, client_setup, isolated_db):
    """F8-B2: Agency session cannot call client proposal acceptance route (403 Forbidden)."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Self-Accept Defense Brief",
            status="proposal_received",
        )
        db.add(req)
        db.flush()
        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="Proposal scope",
            estimated_days=5,
            status="pending",
        )
        db.add(prop)
        db.commit()
        prop_id = prop.id

    resp = agency_client.post(f"/api/client/proposals/{prop_id}/accept")
    progressive_check(app, resp, f"/api/client/proposals/{prop_id}/accept", lambda: None)
    assert resp.status_code in (401, 403)


def test_tier2_f8_cannot_accept_already_accepted_proposal(client_user_client, agency_setup, client_setup, isolated_db):
    """F8-B3: Terminal state defense: Cannot re-accept an already accepted proposal (400 Bad Request)."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Double Accept Defense Brief",
            status="accepted",
        )
        db.add(req)
        db.flush()
        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="Already accepted scope",
            estimated_days=5,
            status="accepted",
        )
        db.add(prop)
        db.commit()
        prop_id = prop.id

    def _fallback():
        with isolated_db() as db:
            p = db.get(Proposal, prop_id)
            assert p is not None
            assert p.status == "accepted"

    resp = client_user_client.post(f"/api/client/proposals/{prop_id}/accept")
    progressive_check(app, resp, f"/api/client/proposals/{prop_id}/accept", _fallback)
    assert resp.status_code == 400


def test_tier2_f8_cannot_accept_declined_proposal(client_user_client, agency_setup, client_setup, isolated_db):
    """F8-B4: Terminal state defense: Cannot accept a proposal that was previously declined (400 Bad Request)."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Declined State Defense Brief",
            status="declined",
        )
        db.add(req)
        db.flush()
        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="Declined scope",
            estimated_days=5,
            status="declined",
        )
        db.add(prop)
        db.commit()
        prop_id = prop.id

    def _fallback():
        with isolated_db() as db:
            p = db.get(Proposal, prop_id)
            assert p is not None
            assert p.status == "declined"

    resp = client_user_client.post(f"/api/client/proposals/{prop_id}/accept")
    progressive_check(app, resp, f"/api/client/proposals/{prop_id}/accept", _fallback)
    assert resp.status_code == 400


def test_tier2_f8_accept_nonexistent_proposal(client_user_client, client_setup, isolated_db):
    """F8-B5: Accepting nonexistent proposal ID returns 404 Not Found."""
    def _fallback():
        with isolated_db() as db:
            p = db.get(Proposal, 999999)
            assert p is None

    resp = client_user_client.post("/api/client/proposals/999999/accept")
    progressive_check(app, resp, "/api/client/proposals/999999/accept", _fallback)
    assert resp.status_code == 404
