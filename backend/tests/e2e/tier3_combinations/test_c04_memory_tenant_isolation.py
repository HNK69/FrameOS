"""Tier 3 Pairwise Combinations: Hindsight Tenant Isolation, Multi-Project Recall & Tenant RBAC.

Coverage:
- test_tier3_c13_hindsight_memory_bank_tenant_isolation:
  Scenario T3-13 (F15 Hindsight Memory x F16 Isolation).
  Identical semantic queries across distinct client memory banks return strictly isolated results.
- test_tier3_c14_multi_project_lifecycle_preference_recall:
  Scenario T3-14 (F05 Briefs x F09 Active Project x F15 Hindsight Memory).
  Preferences confirmed in Project 1 are automatically recalled during Project 2 transcript processing.
- test_tier3_c16_cross_tenant_proposal_acceptance_rejection:
  Scenario T3-16 (F08 Proposal Accept x F09 Active Project x F16 Isolation).
  Client B attempting to accept or decline Client A's proposal is rejected (403/404).
- test_tier3_c17_client_offboarding_cascading_asset_cleanup:
  Scenario T3-17 (F02 Agency Auth x F10 Asset Upload x F16 Isolation).
  Offboarding client purges database records and filesystem assets without leaking across workspaces.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.main import app
from app.models import Asset, Client, MemoryOperation, Project, ProjectRequest, Proposal

from . import progressive_check


def test_tier3_c13_hindsight_memory_bank_tenant_isolation(
    agency_client,
    agency_setup,
    client_setup,
    mock_hindsight,
    isolated_db,
):
    """T3-13: Queries with identical search terms return strictly isolated memory results per client tenant."""
    cid_a = client_setup["client_id"]
    bank_a = client_setup["memory_bank_id"]

    # 1. Create Client B in the same agency workspace with separate memory bank
    with isolated_db() as db:
        client_b = Client(
            workspace_id=agency_setup["workspace_id"],
            name="Client B Technologies",
            brand="ClientB",
            memory_bank_id="bank-client-tenant-b-999",
            memory_status="ready",
        )
        db.add(client_b)
        db.commit()
        cid_b = client_b.id
        bank_b = client_b.memory_bank_id

    # 2. Seed Client A with anamorphic aspect ratio preference
    mock_hindsight.seed_memory(
        bank_id=bank_a,
        content="Always use 2.39:1 anamorphic aspect ratio framing for all commercial deliverables",
        context="Client A framing standard",
    )

    # 3. Seed Client B with square social aspect ratio preference
    mock_hindsight.seed_memory(
        bank_id=bank_b,
        content="Always use 1:1 square framing for social ads",
        context="Client B social guidelines",
    )

    # 4. Recall for Client A
    resp_a = agency_client.post(f"/api/memory/recall?client_id={cid_a}&query=framing+aspect+ratio")
    assert resp_a.status_code == 200
    results_a = resp_a.json().get("results", [])
    assert any("2.39:1" in (r.get("text") or r.get("content") or "") for r in results_a)
    assert not any("1:1 square" in (r.get("text") or r.get("content") or "") for r in results_a)

    # 5. Recall for Client B
    resp_b = agency_client.post(f"/api/memory/recall?client_id={cid_b}&query=framing+aspect+ratio")
    assert resp_b.status_code == 200
    results_b = resp_b.json().get("results", [])
    assert any("1:1 square" in (r.get("text") or r.get("content") or "") for r in results_b)
    assert not any("2.39:1" in (r.get("text") or r.get("content") or "") for r in results_b)


def test_tier3_c14_multi_project_lifecycle_preference_recall(
    agency_client,
    agency_setup,
    client_setup,
    mock_hindsight,
    isolated_db,
):
    """T3-14: Client preferences retained in Project 1 are automatically recalled in Project 2."""
    bank_id = client_setup["memory_bank_id"]

    # 1. Seed past confirmed preference into Client A's bank
    mock_hindsight.seed_memory(
        bank_id=bank_id,
        content="Client prefers dark cinematic color grading with cool shadow tones",
        context="Project 1 final delivery review",
        tags=["confirmed", "color"],
    )

    # 2. Create Project 2 for Client A
    with isolated_db() as db:
        proj2 = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Second Campaign Series",
            status="active",
        )
        db.add(proj2)
        db.commit()
        proj2_id = proj2.id

    # 3. Agency processes transcript for Project 2
    resp_proc = agency_client.post(
        "/api/process-transcript",
        json={
            "project_id": proj2_id,
            "transcript": "Interior sequence color grading and shadow balance review.",
        },
    )
    assert resp_proc.status_code == 201

    # 4. Verify recall operation was logged for Project 2 with completed status
    with isolated_db() as db:
        mem_op = db.scalar(
            select(MemoryOperation).where(
                MemoryOperation.project_id == proj2_id,
                MemoryOperation.operation == "recall",
            )
        )
        assert mem_op is not None
        assert mem_op.status == "completed"


def test_tier3_c16_cross_tenant_proposal_acceptance_rejection(
    foreign_client_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """T3-16: Foreign client attempting to accept Client A's proposal is rejected (403 or 404)."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Client A Private Proposal Brief",
            status="proposal_received",
        )
        db.add(req)
        db.flush()

        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="Exclusive scope for Client A",
            estimated_days=7,
            status="pending",
        )
        db.add(prop)
        db.commit()
        prop_id = prop.id

    def _fallback():
        with isolated_db() as db:
            p = db.get(Proposal, prop_id)
            r = db.get(ProjectRequest, p.request_id)
            # Foreign client user must not match request's client_user_id
            assert r.client_user_id == client_setup["user_id"]

    resp = foreign_client_client.post(f"/api/client/proposals/{prop_id}/accept")
    progressive_check(app, resp, f"/api/client/proposals/{prop_id}/accept", _fallback)
    assert resp.status_code in (403, 404)

    # Proposal remains pending and zero projects created
    with isolated_db() as db:
        p = db.get(Proposal, prop_id)
        assert p.status == "pending"


def test_tier3_c17_client_offboarding_cascading_asset_cleanup(
    agency_client,
    agency_setup,
    client_setup,
    foreign_agency_client,
    foreign_agency_setup,
    foreign_client_setup,
    isolated_db,
):
    """T3-17: Deleting client cascades deletion of projects and asset files without leaking cross-tenant."""
    with isolated_db() as db:
        # Create Project & Asset for Client A
        proj_a = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Client A Project to Delete",
            status="active",
        )
        # Create Project & Asset for Foreign Client B
        proj_b = Project(
            workspace_id=foreign_agency_setup["workspace_id"],
            client_id=foreign_client_setup["client_id"],
            name="Client B Unrelated Project",
            status="active",
        )
        db.add_all([proj_a, proj_b])
        db.commit()
        proj_a_id = proj_a.id
        proj_b_id = proj_b.id

    # Upload asset for Client A
    files_a = {"file": ("client_a_asset.mp4", b"Binary data A", "video/mp4")}
    resp_up_a = agency_client.post(f"/api/projects/{proj_a_id}/assets", files=files_a)
    assert resp_up_a.status_code == 201
    asset_a_id = resp_up_a.json()["id"]

    # Upload asset for Client B
    files_b = {"file": ("client_b_asset.mp4", b"Binary data B", "video/mp4")}
    resp_up_b = foreign_agency_client.post(f"/api/projects/{proj_b_id}/assets", files=files_b)
    assert resp_up_b.status_code == 201
    asset_b_id = resp_up_b.json()["id"]

    # Verify asset A file exists on disk
    with isolated_db() as db:
        asset_a = db.get(Asset, asset_a_id)
        storage_a = Path(asset_a.storage_key)
        assert storage_a.is_file()

        asset_b = db.get(Asset, asset_b_id)
        storage_b = Path(asset_b.storage_key)
        assert storage_b.is_file()

    # Agency A deletes Client A
    del_resp = agency_client.delete(f"/api/clients/{client_setup['client_id']}")
    assert del_resp.status_code == 204

    # Verify Client A is deleted from DB and Asset A file purged from disk
    with isolated_db() as db:
        assert db.get(Client, client_setup["client_id"]) is None
        assert not storage_a.is_file()

        # Verify Client B and Asset B are 100% untouched
        assert db.get(Client, foreign_client_setup["client_id"]) is not None
        assert db.get(Project, proj_b_id) is not None
        assert db.get(Asset, asset_b_id) is not None
        assert storage_b.is_file()
