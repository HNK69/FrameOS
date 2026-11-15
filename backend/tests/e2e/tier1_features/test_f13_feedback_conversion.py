"""Tier 1 Feature 13 Tests: Feedback Conversion to Production Task.

Coverage:
- test_tier1_f13_convert_delivered_feedback_to_task:
  Agency converts confirmed/delivered feedback into a ProductionTask with status 'pending' (POST /api/agency/feedback/{id}/convert-task).
- test_tier1_f13_convert_feedback_idempotent:
  Repeated conversion calls for the same feedback return already_converted=True and the existing task_id without duplicate tasks.
- test_tier1_f13_convert_feedback_ensures_processing_run:
  Feedback conversion auto-provisions a Transcript and ProcessingRun if none exists for the project.
- test_tier1_f13_task_defaults_to_pending_requiring_human_approval:
  Converted ProductionTask defaults to 'pending' status ensuring human approval safeguard before execution.
- test_tier1_f13_list_agency_delivered_feedback_ready_for_conversion:
  Agency feedback inbox filters and lists items with status 'delivered' ready for task conversion (GET /api/agency/feedback?status=delivered).
"""

from __future__ import annotations

from datetime import UTC, datetime
import pytest
from sqlalchemy import select

from app.models import ClientFeedback, ProcessingRun, ProductionTask, Project, Transcript


def test_tier1_f13_convert_delivered_feedback_to_task(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F13-1: Delivered feedback converts into a ProductionTask with status 'pending'."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Task Conversion Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        fb = ClientFeedback(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            submitted_by=client_setup["user_id"],
            idempotency_key="fb-convert-001",
            source_type="text",
            original_text="Adjust pacing on sequence 3 and trim 2s from head",
            status="delivered",
            delivered_at=datetime.now(UTC),
        )
        db.add(fb)
        db.commit()
        fb_id = fb.id
        proj_id = proj.id

    resp = agency_client.post(f"/api/agency/feedback/{fb_id}/convert-task")
    assert resp.status_code == 200
    data = resp.json()
    assert data["already_converted"] is False
    assert data["status"] == "pending"
    assert data["task_id"] > 0

    with isolated_db() as db:
        task = db.get(ProductionTask, data["task_id"])
        assert task is not None
        assert task.workspace_id == agency_setup["workspace_id"]
        assert task.client_id == client_setup["client_id"]
        assert task.project_id == proj_id
        assert task.source == "client_feedback"
        assert task.status == "pending"
        assert f"feedback_id:{fb_id}" in task.evidence


def test_tier1_f13_convert_feedback_idempotent(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F13-2: Replay of task conversion returns existing task_id with already_converted=True without duplicates."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Idempotency Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        fb = ClientFeedback(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            submitted_by=client_setup["user_id"],
            idempotency_key="fb-idemp-002",
            source_type="text",
            original_text="Normalize audio levels to -14 LUFS",
            status="delivered",
            delivered_at=datetime.now(UTC),
        )
        db.add(fb)
        db.commit()
        fb_id = fb.id

    resp1 = agency_client.post(f"/api/agency/feedback/{fb_id}/convert-task")
    assert resp1.status_code == 200
    task_id = resp1.json()["task_id"]

    resp2 = agency_client.post(f"/api/agency/feedback/{fb_id}/convert-task")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["already_converted"] is True
    assert data2["task_id"] == task_id

    with isolated_db() as db:
        tasks = db.scalars(
            select(ProductionTask).where(
                ProductionTask.project_id == proj.id,
                ProductionTask.evidence.like(f"%feedback_id:{fb_id}%"),
            )
        ).all()
        assert len(tasks) == 1


def test_tier1_f13_convert_feedback_ensures_processing_run(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F13-3: Converting feedback on a project with no prior processing run creates Transcript & ProcessingRun."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Run Provisioning Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        fb = ClientFeedback(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            submitted_by=client_setup["user_id"],
            idempotency_key="fb-auto-run-003",
            source_type="text",
            original_text="Recolor sky to dusk palette",
            status="delivered",
            delivered_at=datetime.now(UTC),
        )
        db.add(fb)
        db.commit()
        fb_id = fb.id
        proj_id = proj.id

    resp = agency_client.post(f"/api/agency/feedback/{fb_id}/convert-task")
    assert resp.status_code == 200

    with isolated_db() as db:
        runs = db.scalars(select(ProcessingRun).where(ProcessingRun.project_id == proj_id)).all()
        assert len(runs) >= 1
        run = runs[0]
        assert run.status == "completed"
        assert run.workspace_id == agency_setup["workspace_id"]

        transcript = db.get(Transcript, run.transcript_id)
        assert transcript is not None
        assert "Recolor sky to dusk palette" in transcript.content


def test_tier1_f13_task_defaults_to_pending_requiring_human_approval(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F13-4: Converted production tasks require human approval before execution (status defaults to pending)."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Human Gate Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        fb = ClientFeedback(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            submitted_by=client_setup["user_id"],
            idempotency_key="fb-pending-gate-004",
            source_type="text",
            original_text="Color balance grade revision",
            status="delivered",
            delivered_at=datetime.now(UTC),
        )
        db.add(fb)
        db.commit()
        fb_id = fb.id

    resp = agency_client.post(f"/api/agency/feedback/{fb_id}/convert-task")
    assert resp.status_code == 200
    task_id = resp.json()["task_id"]

    # Verify task via GET /api/tasks/{task_id}
    task_resp = agency_client.get(f"/api/tasks/{task_id}")
    assert task_resp.status_code == 200
    task_data = task_resp.json()
    assert task_data["status"] == "pending"
    assert task_data["source"] == "client_feedback"
    assert "resolve_workflow" in task_data
    assert task_data["requires_confirmation"] is False


def test_tier1_f13_list_agency_delivered_feedback_ready_for_conversion(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F13-5: Agency queries feedback inbox filtering strictly for delivered items ready for conversion."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Delivered Listing Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        fb1 = ClientFeedback(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            submitted_by=client_setup["user_id"],
            idempotency_key="fb-list-01",
            source_type="text",
            original_text="Note 1",
            status="awaiting_confirmation",
        )
        fb2 = ClientFeedback(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            submitted_by=client_setup["user_id"],
            idempotency_key="fb-list-02",
            source_type="text",
            original_text="Note 2",
            status="confirmed",
        )
        fb3 = ClientFeedback(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            submitted_by=client_setup["user_id"],
            idempotency_key="fb-list-03",
            source_type="text",
            original_text="Delivered Note 3",
            status="delivered",
            delivered_at=datetime.now(UTC),
        )
        db.add_all([fb1, fb2, fb3])
        db.commit()
        fb3_id = fb3.id

    resp = agency_client.get("/api/agency/feedback?status=delivered")
    assert resp.status_code == 200
    items = resp.json()
    assert all(item["status"] == "delivered" for item in items)
    ids = [item["id"] for item in items]
    assert fb3_id in ids
