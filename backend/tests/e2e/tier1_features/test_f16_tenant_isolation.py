"""Tier 1 Feature 16 Tests: Cross-Tenant Access Isolation.

Coverage:
- test_tier1_f16_foreign_agency_cannot_access_client:
  Foreign agency cannot view or access another agency's client record (GET /api/clients/{id} returns 404).
- test_tier1_f16_foreign_agency_cannot_access_project:
  Foreign agency cannot view or access another agency's project (GET /api/projects/{id} returns 404).
- test_tier1_f16_foreign_agency_cannot_view_or_patch_tasks:
  Foreign agency cannot view, list, or patch tasks owned by another workspace (404 Not Found).
- test_tier1_f16_client_user_cannot_access_agency_endpoints:
  Client users calling agency endpoints receive 403 Forbidden.
- test_tier1_f16_unauthenticated_request_rejected_with_401:
  Requests lacking credentials to protected endpoints return 401 Unauthorized.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.models import ProcessingRun, ProductionTask, Project, Transcript


def test_tier1_f16_foreign_agency_cannot_access_client(
    foreign_agency_client,
    client_setup,
):
    """F16-1: Foreign agency cannot view Client A's record (returns 404 Not Found)."""
    cid = client_setup["client_id"]
    resp = foreign_agency_client.get(f"/api/clients/{cid}")
    assert resp.status_code == 404


def test_tier1_f16_foreign_agency_cannot_access_project(
    foreign_agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F16-2: Foreign agency cannot access Project A (returns 404 Not Found)."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Agency A Secret Film",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    resp = foreign_agency_client.get(f"/api/projects/{proj_id}")
    assert resp.status_code == 404


def test_tier1_f16_foreign_agency_cannot_view_or_patch_tasks(
    foreign_agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F16-3: Foreign agency cannot view, list, or patch tasks from Agency A."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Agency A Confidential Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        tr = Transcript(project_id=proj.id, content="Secret notes", created_by=agency_setup["owner_id"])
        db.add(tr)
        db.flush()

        run = ProcessingRun(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            transcript_id=tr.id,
            idempotency_key="run-cross-tenant-03",
            status="completed",
        )
        db.add(run)
        db.flush()

        task = ProductionTask(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            run_id=run.id,
            title="Confidential Grade",
            category="Color",
            instruction="Apply secret LUT",
            resolve_workflow="Apply custom 3D LUT in Color page",
            source="ai_extraction",
            confidence=0.95,
            status="pending",
        )
        db.add(task)
        db.commit()
        task_id = task.id

    # 1. Foreign agency GET /api/tasks/{id} returns 404
    resp_get = foreign_agency_client.get(f"/api/tasks/{task_id}")
    assert resp_get.status_code == 404

    # 2. Foreign agency PATCH /api/tasks/{id} returns 404
    resp_patch = foreign_agency_client.patch(
        f"/api/tasks/{task_id}",
        json={"instruction": "Tampered instruction"},
    )
    assert resp_patch.status_code == 404

    # 3. Foreign agency GET /api/tasks returns empty or does not contain Agency A's task
    resp_list = foreign_agency_client.get("/api/tasks")
    assert resp_list.status_code == 200
    task_ids = [t["id"] for t in resp_list.json()]
    assert task_id not in task_ids


def test_tier1_f16_client_user_cannot_access_agency_endpoints(
    client_user_client,
):
    """F16-4: Client role accounts are rejected with 403 Forbidden on agency endpoints."""
    # 1. Feedback inbox
    resp_fb = client_user_client.get("/api/agency/feedback")
    assert resp_fb.status_code == 403

    # 2. Task list
    resp_tasks = client_user_client.get("/api/tasks")
    assert resp_tasks.status_code == 403

    # 3. Production analytics
    resp_analytics = client_user_client.get("/api/production-analytics")
    assert resp_analytics.status_code == 403


def test_tier1_f16_unauthenticated_request_rejected_with_401():
    """F16-5: Anonymous calls to protected endpoints are rejected with 401 Unauthorized."""
    with TestClient(app) as anonymous_client:
        # 1. GET /api/tasks without auth
        resp1 = anonymous_client.get("/api/tasks")
        assert resp1.status_code == 401

        # 2. POST /api/memory/retain without auth
        resp2 = anonymous_client.post(
            "/api/memory/retain",
            json={
                "client_id": 1,
                "content": "Test text",
                "provenance": "client_confirmed",
                "client_confirmed": True,
            },
        )
        assert resp2.status_code == 401
