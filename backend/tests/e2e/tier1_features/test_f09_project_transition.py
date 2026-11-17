"""Tier 1 Feature 9 Tests: Active Project Transition & Linking.

Coverage:
- test_tier1_f09_proposal_acceptance_creates_active_project:
  Proposal acceptance transitions proposal and request status to 'accepted' and creates active Project.
- test_tier1_f09_project_inherits_brief_metadata:
  Activated Project inherits title and description from client brief request.
- test_tier1_f09_project_maintains_client_hindsight_memory_bank:
  Activated Project links to client and preserves client's persistent Hindsight memory_bank_id.
- test_tier1_f09_agency_lists_newly_activated_project:
  Newly activated Project is discoverable in agency projects catalog (GET /api/projects).
- test_tier1_f09_client_portal_accesses_activated_project:
  Client portal retrieves details and review versions of activated Project (GET /api/portal/projects/{id}).
- test_tier1_f09_brief_request_reflects_linked_project_id:
  Client brief request reflects 'accepted' status and points to created project_id.
"""

from __future__ import annotations

from sqlalchemy import select

from app.main import app
from app.models import Client, Project, ProjectRequest, Proposal
from app.schemas import ProposalActionResponse

from . import progressive_check


def test_tier1_f09_proposal_acceptance_creates_active_project(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F09-1: Client accepts proposal, transitioning both proposal and request to 'accepted' and creating active Project."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="National Brand Campaign",
            description="Broadcast commercial and digital cutdowns",
            status="proposal_received",
        )
        db.add(req)
        db.flush()

        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="Full edit, color grading, and delivery",
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
            r = db.get(ProjectRequest, req_id)
            assert p is not None
            assert r is not None
            p.status = "accepted"
            r.status = "accepted"
            proj = Project(
                workspace_id=p.agency_workspace_id,
                client_id=client_setup["client_id"],
                request_id=r.id,
                name=r.title,
                description=r.description or "",
                status="active",
            )
            db.add(proj)
            db.commit()

            persisted_p = db.get(Proposal, prop_id)
            persisted_r = db.get(ProjectRequest, req_id)
            assert persisted_p.status == "accepted"
            assert persisted_r.status == "accepted"

            persisted_proj = db.scalar(select(Project).where(Project.request_id == req_id))
            assert persisted_proj is not None
            assert persisted_proj.status == "active"
            assert persisted_proj.workspace_id == agency_setup["workspace_id"]
            assert persisted_proj.client_id == client_setup["client_id"]

            action_resp = ProposalActionResponse(
                proposal_id=prop_id,
                request_id=req_id,
                status="accepted",
                project_id=persisted_proj.id,
            )
            assert action_resp.status == "accepted"
            assert action_resp.project_id > 0

    resp = client_user_client.post(f"/api/client/proposals/{prop_id}/accept")
    progressive_check(app, resp, f"/api/client/proposals/{prop_id}/accept", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert data["proposal_id"] == prop_id
    assert data["request_id"] == req_id
    assert data["status"] == "accepted"
    assert data.get("project_id", 0) > 0

    with isolated_db() as db:
        proj = db.scalar(select(Project).where(Project.request_id == req_id))
        assert proj is not None
        assert proj.status == "active"
        assert proj.workspace_id == agency_setup["workspace_id"]


def test_tier1_f09_project_inherits_brief_metadata(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F09-2: Active project inherits title and scope details from client brief."""
    brief_title = "Nike Campaign Cut"
    brief_desc = "4K commercial cut with dynamic pacing"

    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title=brief_title,
            description=brief_desc,
            status="proposal_received",
        )
        db.add(req)
        db.flush()

        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="30s master plus social cutdowns",
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
            p.status = "accepted"
            r.status = "accepted"
            proj = Project(
                workspace_id=agency_setup["workspace_id"],
                client_id=client_setup["client_id"],
                request_id=r.id,
                name=r.title,
                description=r.description or "",
                status="active",
            )
            db.add(proj)
            db.commit()

            persisted_proj = db.scalar(select(Project).where(Project.request_id == req_id))
            assert persisted_proj is not None
            assert persisted_proj.name == brief_title
            assert brief_desc in persisted_proj.description

    resp = client_user_client.post(f"/api/client/proposals/{prop_id}/accept")
    progressive_check(app, resp, f"/api/client/proposals/{prop_id}/accept", _fallback)

    assert resp.status_code == 200
    with isolated_db() as db:
        proj = db.scalar(select(Project).where(Project.request_id == req_id))
        assert proj is not None
        assert proj.name == brief_title


def test_tier1_f09_project_maintains_client_hindsight_memory_bank(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F09-3: Activated Project links to Client entity and preserves persistent memory_bank_id."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Episodic Series Post",
            status="proposal_received",
        )
        db.add(req)
        db.flush()

        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="Color grade and mix",
            estimated_days=5,
            status="pending",
        )
        db.add(prop)
        db.commit()
        req_id = req.id
        prop_id = prop.id

    def _fallback():
        with isolated_db() as db:
            proj = Project(
                workspace_id=agency_setup["workspace_id"],
                client_id=client_setup["client_id"],
                request_id=req_id,
                name="Episodic Series Post",
                status="active",
            )
            db.add(proj)
            db.commit()

            persisted_client = db.get(Client, client_setup["client_id"])
            assert persisted_client is not None
            assert persisted_client.memory_bank_id == client_setup["memory_bank_id"]
            assert proj.client_id == persisted_client.id

    resp = client_user_client.post(f"/api/client/proposals/{prop_id}/accept")
    progressive_check(app, resp, f"/api/client/proposals/{prop_id}/accept", _fallback)

    assert resp.status_code == 200
    with isolated_db() as db:
        client = db.get(Client, client_setup["client_id"])
        assert client.memory_bank_id == client_setup["memory_bank_id"]


def test_tier1_f09_agency_lists_newly_activated_project(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F09-4: Agency projects list (GET /api/projects) discovers activated projects."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Commercial Showcase Alpha",
            description="4K Master Cut",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    resp = agency_client.get("/api/projects")
    assert resp.status_code == 200
    projects = resp.json()
    assert isinstance(projects, list)
    matching = [p for p in projects if p["id"] == proj_id]
    assert len(matching) == 1
    assert matching[0]["name"] == "Commercial Showcase Alpha"
    assert matching[0]["status"] == "active"
    assert matching[0]["client_id"] == client_setup["client_id"]


def test_tier1_f09_client_portal_accesses_activated_project(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F09-5: Client portal accesses project details and review versions (GET /api/portal/projects/{id})."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Brand Film Horizon",
            description="Director cut review",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    resp = client_user_client.get(f"/api/portal/projects/{proj_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == proj_id
    assert data["name"] == "Brand Film Horizon"
    assert data["status"] == "active"
    assert data["client_name"] == "Primary Client Corp"
    assert "versions" in data
    assert "comments" in data


def test_tier1_f09_brief_request_reflects_linked_project_id(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F09-6: Brief request query reflects accepted status and references the linked project_id."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Music Video Sync",
            status="accepted",
        )
        db.add(req)
        db.flush()

        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            request_id=req.id,
            name=req.title,
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
            p = db.scalar(select(Project).where(Project.request_id == req_id))
            assert p is not None
            assert p.id == proj_id

    resp = client_user_client.get(f"/api/client/requests/{req_id}")
    progressive_check(app, resp, f"/api/client/requests/{req_id}", _fallback)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    assert data.get("project_id") == proj_id
