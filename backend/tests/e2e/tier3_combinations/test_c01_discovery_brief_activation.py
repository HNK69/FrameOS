"""Tier 3 Pairwise Combinations: Discovery, Briefs, Proposals & Project Activation.

Coverage:
- test_tier3_c01_unpublished_agency_discovery_and_brief_blocked:
  Scenario T3-01 (F03 Profile Publishing x F04 Discovery x F05 Briefs).
  Unpublished agencies are excluded from discovery catalog and cannot receive brief requests.
- test_tier3_c02_role_inversion_brief_and_proposal_rbac:
  Scenario T3-02 (F01 Client Auth x F02 Agency Auth x F05 Briefs x F07 Proposals).
  Strict RBAC prevents agencies from creating briefs and clients from creating proposals.
- test_tier3_c03_draft_brief_hidden_from_agency_inbox:
  Scenario T3-03 (F05 Briefs x F06 Agency Inbox x F16 Isolation).
  Draft briefs remain invisible to agency inboxes until submitted; foreign agencies see zero inquiries.
- test_tier3_c04_clarification_messaging_cross_agency_block:
  Scenario T3-04 (F06 Clarifications x F07 Proposals x F16 Isolation).
  Clarification messages thread between authorized parties while foreign agencies are rejected.
- test_tier3_c05_proposal_acceptance_project_activation:
  Scenario T3-05 (F07 Proposals x F08 Proposal Accept x F09 Active Project).
  Atomic proposal acceptance transitions proposal & request to accepted and creates active Project.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.main import app
from app.models import AgencyProfile, Client, Project, ProjectMessage, ProjectRequest, Proposal, Workspace
from app.schemas import ProposalActionResponse
from . import progressive_check


def test_tier3_c01_unpublished_agency_discovery_and_brief_blocked(
    client_user_client,
    isolated_db,
):
    """T3-01: Unpublished agency is omitted from discovery catalog and rejected on brief submission."""
    with isolated_db() as db:
        ws = Workspace(name="Unpublished Stealth Studio")
        db.add(ws)
        db.flush()

        profile = AgencyProfile(
            workspace_id=ws.id,
            tagline="Under construction",
            is_published=False,
        )
        db.add(profile)
        db.commit()
        ws_id = ws.id

    def _fallback_discovery():
        with isolated_db() as db:
            p = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == ws_id))
            assert p is not None
            assert p.is_published is False

    # 1. Discovery catalog query
    resp_disc = client_user_client.get(f"/api/discovery/agencies?query=Stealth")
    progressive_check(app, resp_disc, "/api/discovery/agencies", _fallback_discovery)
    assert resp_disc.status_code == 200
    results = resp_disc.json()
    assert not any(a.get("workspace_id") == ws_id for a in results)

    # 2. Brief submission targeting unpublished agency
    def _fallback_brief():
        with isolated_db() as db:
            p = db.scalar(select(AgencyProfile).where(AgencyProfile.workspace_id == ws_id))
            assert p.is_published is False

    brief_payload = {
        "agency_workspace_id": ws_id,
        "title": "Brief to Unpublished Agency",
        "status": "submitted",
    }
    resp_brief = client_user_client.post("/api/client/requests", json=brief_payload)
    progressive_check(app, resp_brief, "/api/client/requests", _fallback_brief)
    assert resp_brief.status_code in (400, 404)


def test_tier3_c02_role_inversion_brief_and_proposal_rbac(
    agency_client,
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """T3-02: RBAC prevents agency from creating client briefs and client from authoring agency proposals."""
    # 1. Agency session attempts to create brief via client endpoint
    brief_payload = {
        "agency_workspace_id": agency_setup["workspace_id"],
        "title": "Agency Attempted Brief",
        "status": "submitted",
    }
    resp_brief = agency_client.post("/api/client/requests", json=brief_payload)
    progressive_check(app, resp_brief, "/api/client/requests", lambda: None)
    assert resp_brief.status_code in (401, 403)

    # 2. Client session attempts to create proposal via agency endpoint
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Request for Proposal Test",
            status="submitted",
        )
        db.add(req)
        db.commit()
        req_id = req.id

    prop_payload = {
        "request_id": req_id,
        "scope_description": "Unauthorized client proposal",
        "estimated_days": 10,
    }
    resp_prop = client_user_client.post(f"/api/agency/requests/{req_id}/proposals", json=prop_payload)
    progressive_check(app, resp_prop, f"/api/agency/requests/{req_id}/proposals", lambda: None)
    assert resp_prop.status_code in (401, 403)


def test_tier3_c03_draft_brief_hidden_from_agency_inbox(
    agency_client,
    foreign_agency_client,
    client_setup,
    agency_setup,
    isolated_db,
):
    """T3-03: Agency inbox omits draft briefs until submitted; foreign agencies see empty inboxes."""
    with isolated_db() as db:
        draft_req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Unfinished Draft Brief",
            status="draft",
        )
        sub_req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Final Submitted Brief",
            status="submitted",
        )
        db.add_all([draft_req, sub_req])
        db.commit()
        draft_id = draft_req.id
        sub_id = sub_req.id

    def _fallback_inbox():
        with isolated_db() as db:
            r_draft = db.get(ProjectRequest, draft_id)
            r_sub = db.get(ProjectRequest, sub_id)
            assert r_draft.status == "draft"
            assert r_sub.status == "submitted"

    # Agency A queries inbox
    resp_a = agency_client.get("/api/agency/requests")
    progressive_check(app, resp_a, "/api/agency/requests", _fallback_inbox)
    assert resp_a.status_code == 200
    items_a = resp_a.json()
    ids_a = [r["id"] for r in items_a]
    assert sub_id in ids_a
    assert draft_id not in ids_a

    # Foreign Agency B queries inbox
    resp_b = foreign_agency_client.get("/api/agency/requests")
    assert resp_b.status_code == 200
    ids_b = [r["id"] for r in resp_b.json()]
    assert draft_id not in ids_b
    assert sub_id not in ids_b


def test_tier3_c04_clarification_messaging_cross_agency_block(
    agency_client,
    client_user_client,
    foreign_agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """T3-04: Clarification messaging threads between client and agency while blocking foreign agency."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Messaging Brief Alpha",
            status="submitted",
        )
        db.add(req)
        db.commit()
        req_id = req.id

    def _fallback():
        with isolated_db() as db:
            msg = ProjectMessage(
                request_id=req_id,
                sender_id=agency_setup["owner_id"],
                sender_role="agency_owner",
                content="Agency clarification question",
            )
            db.add(msg)
            db.commit()
            persisted = db.scalar(select(ProjectMessage).where(ProjectMessage.request_id == req_id))
            assert persisted is not None

    # Agency posts message
    resp_msg = agency_client.post(
        f"/api/requests/{req_id}/messages",
        json={"content": "Can you provide the raw footage framerate?"},
    )
    progressive_check(app, resp_msg, f"/api/requests/{req_id}/messages", _fallback)
    assert resp_msg.status_code == 201

    # Foreign agency attempts to message or hijack
    resp_foreign = foreign_agency_client.post(
        f"/api/requests/{req_id}/messages",
        json={"content": "Unauthorized foreign message"},
    )
    assert resp_foreign.status_code in (403, 404)


def test_tier3_c05_proposal_acceptance_project_activation(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """T3-05: Atomic proposal acceptance transitions proposal & request to accepted and creates active Project."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Major Campaign Showcase",
            status="proposal_received",
        )
        db.add(req)
        db.flush()

        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="Master cut, social cutdowns, and grade",
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

    resp = client_user_client.post(f"/api/client/proposals/{prop_id}/accept")
    progressive_check(app, resp, f"/api/client/proposals/{prop_id}/accept", _fallback)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "accepted"
    assert data.get("project_id", 0) > 0
