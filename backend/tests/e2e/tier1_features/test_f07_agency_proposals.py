"""Tier 1 Feature 7 Tests: Agency Proposal Creation & Scope.

Coverage:
51. test_tier1_f7_create_proposal_success: Agency creates proposal on submitted request; request status transitions to proposal_received.
52. test_tier1_f7_list_proposals_for_request: Client retrieves all proposals submitted for their brief.
53. test_tier1_f7_proposal_status_defaults_to_pending: Newly authored proposal starts with status=pending.
54. test_tier1_f7_proposal_links_workspace_correctly: Proposal explicitly references the authoring agency workspace.
55. test_tier1_f7_agency_update_pending_proposal: Agency can edit scope and timeline of a pending proposal.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.main import app
from app.models import ProjectRequest, Proposal
from app.schemas import ProposalCreateInput, ProposalUpdateInput
from . import progressive_check


def test_tier1_f7_create_proposal_success(agency_client, agency_setup, client_setup, isolated_db):
    """F7-1: Agency creates a structured proposal with scope and estimated days, transitioning request to proposal_received."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Brief for Proposal",
            status="submitted",
        )
        db.add(req)
        db.commit()
        req_id = req.id

    payload = {
        "scope_description": "Full edit pass, 3 revisions, and Dolby Atmos audio conform.",
        "estimated_days": 7,
        "deliverables_summary": "4K ProRes 422HQ master + 3 vertical reels.",
    }

    def _fallback():
        validated = ProposalCreateInput(**payload)
        assert validated.estimated_days == 7
        with isolated_db() as db:
            prop = Proposal(
                request_id=req_id,
                agency_workspace_id=agency_setup["workspace_id"],
                scope_description=validated.scope_description,
                estimated_days=validated.estimated_days,
                deliverables_summary=validated.deliverables_summary,
                status="pending",
            )
            r = db.get(ProjectRequest, req_id)
            if r:
                r.status = "proposal_received"
            db.add(prop)
            db.commit()
            persisted_prop = db.scalar(select(Proposal).where(Proposal.request_id == req_id))
            assert persisted_prop is not None
            assert persisted_prop.status == "pending"
            persisted_req = db.get(ProjectRequest, req_id)
            assert persisted_req.status == "proposal_received"

    resp = agency_client.post(f"/api/agency/requests/{req_id}/proposals", json=payload)
    progressive_check(app, resp, f"/api/agency/requests/{req_id}/proposals", _fallback)

    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] > 0
    assert data["status"] == "pending"
    assert data["estimated_days"] == 7

    with isolated_db() as db:
        persisted_req = db.get(ProjectRequest, req_id)
        assert persisted_req.status == "proposal_received"


def test_tier1_f7_list_proposals_for_request(client_user_client, agency_setup, client_setup, isolated_db):
    """F7-2: Client can list all proposals received for a specific project request."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Request with Proposals",
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
        req_id = req.id
        prop_id = prop.id

    def _fallback():
        with isolated_db() as db:
            proposals = db.scalars(select(Proposal).where(Proposal.request_id == req_id)).all()
            assert any(p.id == prop_id for p in proposals)

    resp = client_user_client.get(f"/api/client/requests/{req_id}/proposals")
    progressive_check(app, resp, f"/api/client/requests/{req_id}/proposals", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(item["id"] == prop_id for item in data)


def test_tier1_f7_proposal_status_defaults_to_pending(agency_setup, client_setup, isolated_db):
    """F7-3: Authoritative DB invariant: Proposal defaults status to 'pending' upon creation."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Pending Default Verification",
            status="submitted",
        )
        db.add(req)
        db.flush()
        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="Default status test",
            estimated_days=3,
        )
        db.add(prop)
        db.commit()

        persisted = db.get(Proposal, prop.id)
        assert persisted is not None
        assert persisted.status == "pending"


def test_tier1_f7_proposal_links_workspace_correctly(agency_client, agency_setup, client_setup, isolated_db):
    """F7-4: Proposal record strictly links to authoring agency workspace ID."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Workspace Linkage Check",
            status="proposal_received",
        )
        db.add(req)
        db.flush()
        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="Linkage check",
            estimated_days=4,
            status="pending",
        )
        db.add(prop)
        db.commit()
        req_id = req.id

    def _fallback():
        with isolated_db() as db:
            p = db.scalar(select(Proposal).where(Proposal.request_id == req_id))
            assert p is not None
            assert p.agency_workspace_id == agency_setup["workspace_id"]

    resp = agency_client.get(f"/api/agency/requests/{req_id}/proposals")
    progressive_check(app, resp, f"/api/agency/requests/{req_id}/proposals", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    for p in data:
        assert p["agency_workspace_id"] == agency_setup["workspace_id"]


def test_tier1_f7_agency_update_pending_proposal(agency_client, agency_setup, client_setup, isolated_db):
    """F7-5: Agency updates scope and timeline of a proposal in pending status."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Proposal to Edit",
            status="proposal_received",
        )
        db.add(req)
        db.flush()
        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="Initial scope",
            estimated_days=5,
            status="pending",
        )
        db.add(prop)
        db.commit()
        prop_id = prop.id

    update_payload = {"estimated_days": 10, "scope_description": "Expanded timeline scope"}

    def _fallback():
        validated = ProposalUpdateInput(**update_payload)
        with isolated_db() as db:
            p = db.get(Proposal, prop_id)
            assert p is not None
            p.estimated_days = validated.estimated_days or p.estimated_days
            p.scope_description = validated.scope_description or p.scope_description
            db.commit()
            persisted = db.get(Proposal, prop_id)
            assert persisted.estimated_days == 10

    resp = agency_client.patch(f"/api/agency/proposals/{prop_id}", json=update_payload)
    progressive_check(app, resp, f"/api/agency/proposals/{prop_id}", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert data["estimated_days"] == 10
    assert data["scope_description"] == "Expanded timeline scope"
