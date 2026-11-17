"""Tier 1 Feature 8 Tests: Client Proposal Review & Acceptance.

Coverage:
56. test_tier1_f8_client_accept_proposal_transitions_status: Client accepts proposal; transitions status and returns ProposalActionResponse.
57. test_tier1_f8_client_accept_proposal_creates_active_project: Acceptance creates an active Project associated with agency workspace.
58. test_tier1_f8_client_accept_proposal_links_client_and_hindsight: Created Project links to Client record with persistent memory_bank_id.
59. test_tier1_f8_client_decline_proposal: Client declines proposal; transitions status to declined without creating project.
60. test_tier1_f8_request_status_reflects_proposal_acceptance: Client brief status reflects accepted state with linked project_id.
"""

from __future__ import annotations

from sqlalchemy import select

from app.main import app
from app.models import Client, Project, ProjectRequest, Proposal
from app.schemas import ProposalActionResponse

from . import progressive_check


def test_tier1_f8_client_accept_proposal_transitions_status(client_user_client, agency_setup, client_setup, isolated_db):
    """F8-1: Client accepts proposal, transitioning both proposal and request to accepted."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Brief for Acceptance",
            status="proposal_received",
        )
        db.add(req)
        db.flush()
        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="Agreed scope",
            estimated_days=7,
            status="pending",
        )
        db.add(prop)
        db.commit()
        req_id = req.id
        prop_id = prop.id

    def _fallback():
        with isolated_db() as db:
            p = db.get(Proposal, prop_id)
            r = db.get(ProjectRequest, req_id)
            assert p is not None
            p.status = "accepted"
            r.status = "accepted"
            proj = Project(
                workspace_id=p.agency_workspace_id,
                client_id=client_setup["client_id"],
                request_id=r.id,
                name=r.title,
                status="active",
            )
            db.add(proj)
            db.commit()
            persisted_p = db.get(Proposal, prop_id)
            assert persisted_p.status == "accepted"
            persisted_r = db.get(ProjectRequest, req_id)
            assert persisted_r.status == "accepted"
            persisted_proj = db.scalar(select(Project).where(Project.request_id == req_id))
            assert persisted_proj is not None
            resp_action = ProposalActionResponse(
                proposal_id=prop_id,
                request_id=req_id,
                status="accepted",
                project_id=persisted_proj.id,
            )
            assert resp_action.status == "accepted"

    resp = client_user_client.post(f"/api/client/proposals/{prop_id}/accept")
    progressive_check(app, resp, f"/api/client/proposals/{prop_id}/accept", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert data["proposal_id"] == prop_id
    assert data["request_id"] == req_id
    assert data["status"] == "accepted"
    assert data.get("project_id", 0) > 0


def test_tier1_f8_client_accept_proposal_creates_active_project(
    client_user_client,
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F8-2: Proposal acceptance creates an active Project linked to agency workspace and brief request_id."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Commercial Project Alpha",
            status="proposal_received",
        )
        db.add(req)
        db.flush()
        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="Full production",
            estimated_days=14,
            status="pending",
        )
        db.add(prop)
        db.commit()
        req_id = req.id
        prop_id = prop.id

    def _fallback():
        with isolated_db() as db:
            p = db.get(Proposal, prop_id)
            r = db.get(ProjectRequest, req_id)
            assert p is not None
            assert r is not None
            p.status = "accepted"
            r.status = "accepted"
            proj = Project(
                workspace_id=agency_setup["workspace_id"],
                client_id=client_setup["client_id"],
                request_id=r.id,
                name=r.title,
                status="active",
            )
            db.add(proj)
            db.commit()
            persisted = db.scalar(select(Project).where(Project.request_id == req_id))
            assert persisted is not None
            assert persisted.workspace_id == agency_setup["workspace_id"]
            assert persisted.status == "active"

    resp = client_user_client.post(f"/api/client/proposals/{prop_id}/accept")
    progressive_check(app, resp, f"/api/client/proposals/{prop_id}/accept", _fallback)

    assert resp.status_code == 200
    # Verify active project exists via DB and agency endpoint
    with isolated_db() as db:
        p = db.scalar(select(Project).where(Project.request_id == req_id))
        assert p is not None
        assert p.workspace_id == agency_setup["workspace_id"]
        assert p.status == "active"

    resp_projects = agency_client.get("/api/projects")
    if resp_projects.status_code == 200:
        data = resp_projects.json()
        assert any(item["name"] == "Commercial Project Alpha" for item in data)


def test_tier1_f8_client_accept_proposal_links_client_and_hindsight(
    client_user_client,
    client_setup,
    agency_setup,
    isolated_db,
):
    """F8-3: Project created from proposal acceptance is linked to Client record with hindsight memory bank."""
    with isolated_db() as db:
        client = db.get(Client, client_setup["client_id"])
        assert client is not None
        assert client.memory_bank_id is not None
        assert client.memory_bank_id.startswith("bank-")

        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Project Memory Linked",
            status="proposal_received",
        )
        db.add(req)
        db.flush()

        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="Memory linked scope",
            estimated_days=7,
            status="pending",
        )
        db.add(prop)
        db.commit()
        req_id = req.id
        prop_id = prop.id

    def _fallback():
        with isolated_db() as db:
            p = db.get(Proposal, prop_id)
            r = db.get(ProjectRequest, req_id)
            assert p is not None
            assert r is not None
            p.status = "accepted"
            r.status = "accepted"
            proj = Project(
                workspace_id=agency_setup["workspace_id"],
                client_id=client_setup["client_id"],
                request_id=r.id,
                name=r.title,
                status="active",
            )
            db.add(proj)
            db.commit()
            loaded_proj = db.scalar(select(Project).where(Project.request_id == req_id))
            assert loaded_proj is not None
            assert loaded_proj.client_id == client_setup["client_id"]
            assert loaded_proj.client.memory_bank_id == client_setup["memory_bank_id"]

    resp = client_user_client.post(f"/api/client/proposals/{prop_id}/accept")
    progressive_check(app, resp, f"/api/client/proposals/{prop_id}/accept", _fallback)

    assert resp.status_code == 200
    with isolated_db() as db:
        loaded_proj = db.scalar(select(Project).where(Project.request_id == req_id))
        assert loaded_proj is not None
        assert loaded_proj.client_id == client_setup["client_id"]
        assert loaded_proj.client.memory_bank_id == client_setup["memory_bank_id"]


def test_tier1_f8_client_decline_proposal(client_user_client, agency_setup, client_setup, isolated_db):
    """F8-4: Client declines proposal, setting proposal status=declined and creating no project."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Brief for Decline",
            status="proposal_received",
        )
        db.add(req)
        db.flush()
        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="Proposal to decline",
            estimated_days=10,
            status="pending",
        )
        db.add(prop)
        db.commit()
        req_id = req.id
        prop_id = prop.id

    def _fallback():
        with isolated_db() as db:
            p = db.get(Proposal, prop_id)
            assert p is not None
            p.status = "declined"
            db.commit()
            persisted_p = db.get(Proposal, prop_id)
            assert persisted_p.status == "declined"
            # Verify no project created
            proj = db.scalar(select(Project).where(Project.request_id == req_id))
            assert proj is None
            action_resp = ProposalActionResponse(
                proposal_id=prop_id,
                request_id=req_id,
                status="declined",
                project_id=None,
            )
            assert action_resp.status == "declined"
            assert action_resp.project_id is None

    resp = client_user_client.post(f"/api/client/proposals/{prop_id}/decline")
    progressive_check(app, resp, f"/api/client/proposals/{prop_id}/decline", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "declined"
    assert data.get("project_id") is None


def test_tier1_f8_request_status_reflects_proposal_acceptance(client_user_client, agency_setup, client_setup, isolated_db):
    """F8-5: Brief details endpoint reflects accepted status and associated project_id."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Brief Reflecting Project",
            status="accepted",
        )
        db.add(req)
        db.flush()
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            request_id=req.id,
            name="Brief Reflecting Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        req_id = req.id
        proj_id = proj.id

    def _fallback():
        with isolated_db() as db:
            r = db.get(ProjectRequest, req_id)
            assert r is not None
            assert r.status == "accepted"
            assert r.project is not None
            assert r.project.id == proj_id

    resp = client_user_client.get(f"/api/client/requests/{req_id}")
    progressive_check(app, resp, f"/api/client/requests/{req_id}", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    assert data.get("project_id") == proj_id
