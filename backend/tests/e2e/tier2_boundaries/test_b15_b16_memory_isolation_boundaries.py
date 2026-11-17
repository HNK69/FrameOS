"""Tier 2 Boundary, Error, and Security Tests: Features 15 to 16.

Coverage:
- Feature 15: Hindsight Memory Boundaries (Tests 115 to 119)
  115. test_tier2_b15_retain_with_client_confirmed_mismatched_provenance_fails: Confirmed memory without client_confirmed provenance returns 422.
  116. test_tier2_b15_retain_mismatched_project_and_client_fails: Mismatched project and client in retain payload returns 422.
  117. test_tier2_b15_memory_bank_tenant_leak_prevention: Semantic recall for Client B never leaks Client A's memory bank entries.
  118. test_tier2_b15_hindsight_service_down_graceful_degradation: Hindsight outage degrades memory operation safely without crashing pipeline.
  119. test_tier2_b15_oversized_idempotency_key_fails: Idempotency-Key exceeding 120 characters rejected with 422.
- Feature 16: Cross-Tenant Isolation Boundaries (Tests 120 to 124)
  120. test_tier2_b16_client_a_cannot_access_client_b_portal_project: Client A portal access to Client B project returns 404.
  121. test_tier2_b16_client_a_cannot_comment_on_client_b_deliverable: Client A comment on Client B project returns 404.
  122. test_tier2_b16_client_a_cannot_submit_decision_on_client_b_deliverable: Client A decision on Client B project returns 404.
  123. test_tier2_b16_tampered_portal_token_rejected_with_401: Tampered JWT portal session token rejected with 401.
  124. test_tier2_b16_foreign_agency_cannot_access_adaptive_knowledge: Foreign agency querying Client A adaptive knowledge returns 404.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import Client, MemoryOperation, Project

# ==============================================================================
# Feature 15: Hindsight Memory Boundaries (Tests 115-119)
# ==============================================================================

def test_tier2_b15_retain_with_client_confirmed_mismatched_provenance_fails(
    agency_client,
    client_setup,
):
    """B15-1: client_confirmed=True with provenance other than client_confirmed is rejected with 422."""
    payload = {
        "client_id": client_setup["client_id"],
        "content": "Subjective note",
        "provenance": "reusable_client_knowledge",
        "client_confirmed": True,
    }
    resp = agency_client.post("/api/memory/retain", json=payload)
    assert resp.status_code == 422


def test_tier2_b15_retain_mismatched_project_and_client_fails(
    agency_client,
    agency_setup,
    client_setup,
    foreign_client_setup,
    isolated_db,
):
    """B15-2: Retain request with project_id belonging to a different client is rejected with 422."""
    with isolated_db() as db:
        # Create a second client in the same workspace to test mismatch within workspace
        client2 = Client(
            workspace_id=agency_setup["workspace_id"],
            name="Second Client Corp",
            memory_bank_id="bank-client-secondary-002",
        )
        db.add(client2)
        db.flush()

        proj_client2 = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client2.id,
            name="Client 2 Project",
            status="active",
        )
        db.add(proj_client2)
        db.commit()
        proj2_id = proj_client2.id

    payload = {
        "client_id": client_setup["client_id"],
        "project_id": proj2_id,
        "content": "Cross-client mismatched preference",
        "provenance": "reusable_client_knowledge",
        "client_confirmed": False,
    }
    resp = agency_client.post("/api/memory/retain", json=payload)
    assert resp.status_code == 422


def test_tier2_b15_memory_bank_tenant_leak_prevention(
    agency_client,
    agency_setup,
    client_setup,
    mock_hindsight,
    isolated_db,
):
    """B15-3: Recalling memories for Client 2 never leaks entries from Client 1's isolated bank."""
    with isolated_db() as db:
        client2 = Client(
            workspace_id=agency_setup["workspace_id"],
            name="Unrelated Tenant Client",
            memory_bank_id="bank-client-unrelated-003",
        )
        db.add(client2)
        db.commit()
        client2_id = client2.id

    # Seed Client 1's bank with sensitive brand note
    mock_hindsight.seed_memory(
        bank_id=client_setup["memory_bank_id"],
        content="Confidential Brand Color: #0A192F Navy Blue",
        context="Client 1 Brand Guidelines",
    )

    # Query recall for Client 2 with identical query
    resp = agency_client.post(f"/api/memory/recall?client_id={client2_id}&query=brand+color+navy+blue")
    assert resp.status_code == 200
    results = resp.json().get("results", [])
    assert not any("Navy Blue" in (r.get("text") or r.get("content") or "") for r in results)


def test_tier2_b15_hindsight_service_down_graceful_degradation(
    agency_client,
    agency_setup,
    client_setup,
    mock_hindsight,
    isolated_db,
):
    """B15-4: Hindsight outage during transcript processing logs degraded status without crashing pipeline."""
    mock_hindsight.should_fail = True

    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Degradation Test Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    payload = {"project_id": proj_id, "transcript": "Apply high contrast color grade."}
    resp = agency_client.post("/api/process-transcript", json=payload)
    assert resp.status_code == 201

    with isolated_db() as db:
        op = db.scalar(
            select(MemoryOperation).where(
                MemoryOperation.project_id == proj_id,
                MemoryOperation.operation == "recall",
            )
        )
        assert op is not None
        assert op.status == "degraded"


def test_tier2_b15_oversized_idempotency_key_fails(
    agency_client,
    client_setup,
):
    """B15-5: Idempotency-Key exceeding 120 characters is rejected with 422 Unprocessable Entity."""
    payload = {
        "client_id": client_setup["client_id"],
        "content": "Valid content text",
        "provenance": "reusable_client_knowledge",
        "client_confirmed": False,
    }
    headers = {"Idempotency-Key": "X" * 121}
    resp = agency_client.post("/api/memory/retain", json=payload, headers=headers)
    assert resp.status_code == 422


# ==============================================================================
# Feature 16: Cross-Tenant Isolation Boundaries (Tests 120-124)
# ==============================================================================

def test_tier2_b16_client_a_cannot_access_client_b_portal_project(
    client_user_client,
    foreign_agency_setup,
    foreign_client_setup,
    isolated_db,
):
    """B16-1: Client A cannot view or retrieve Client B's project in the portal (returns 404)."""
    with isolated_db() as db:
        proj_b = Project(
            workspace_id=foreign_agency_setup["workspace_id"],
            client_id=foreign_client_setup["client_id"],
            name="Client B Private Film",
            status="active",
        )
        db.add(proj_b)
        db.commit()
        proj_b_id = proj_b.id

    resp = client_user_client.get(f"/api/portal/projects/{proj_b_id}")
    assert resp.status_code == 404


def test_tier2_b16_client_a_cannot_comment_on_client_b_deliverable(
    client_user_client,
    foreign_agency_setup,
    foreign_client_setup,
    isolated_db,
):
    """B16-2: Client A cannot post comments to Client B's project (returns 404 Not Found)."""
    with isolated_db() as db:
        proj_b = Project(
            workspace_id=foreign_agency_setup["workspace_id"],
            client_id=foreign_client_setup["client_id"],
            name="Client B Protected Project",
            status="active",
        )
        db.add(proj_b)
        db.commit()
        proj_b_id = proj_b.id

    payload = {
        "timestamp_seconds": 15.0,
        "timecode": "00:00:15:00",
        "content": "Intruder comment from Client A",
    }
    resp = client_user_client.post(f"/api/portal/projects/{proj_b_id}/comments", json=payload)
    assert resp.status_code == 404


def test_tier2_b16_client_a_cannot_submit_decision_on_client_b_deliverable(
    client_user_client,
    foreign_agency_setup,
    foreign_client_setup,
    isolated_db,
):
    """B16-3: Client A cannot submit review decisions for Client B's project (returns 404 Not Found)."""
    with isolated_db() as db:
        proj_b = Project(
            workspace_id=foreign_agency_setup["workspace_id"],
            client_id=foreign_client_setup["client_id"],
            name="Client B Approval Project",
            status="in_review",
        )
        db.add(proj_b)
        db.commit()
        proj_b_id = proj_b.id

    payload = {"decision": "approve"}
    resp = client_user_client.post(f"/api/portal/projects/{proj_b_id}/decision", json=payload)
    assert resp.status_code == 404


def test_tier2_b16_tampered_portal_token_rejected_with_401(isolated_db):
    """B16-4: Requests presenting a forged or tampered portal JWT signature return 401 Unauthorized."""
    with TestClient(app) as test_client:
        tampered_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjbGllbnRfaWQiOjEsIndvcmtzcGFjZV9pZCI6MSwicm9sZSI6ImNsaWVudCJ9.FAKESIGNATURE_FORGED_123456789"
        test_client.cookies.set("frameops_portal_session", tampered_token)

        resp = test_client.get("/api/portal/projects")
        assert resp.status_code == 401


def test_tier2_b16_foreign_agency_cannot_access_adaptive_knowledge(
    foreign_agency_client,
    client_setup,
):
    """B16-5: Foreign agency cannot view Client A's adaptive knowledge breakdown (returns 404 Not Found)."""
    cid = client_setup["client_id"]
    resp = foreign_agency_client.get(f"/api/clients/{cid}/adaptive-knowledge")
    assert resp.status_code == 404
