"""Tier 2 Boundary, Error, and Security Tests: Features 13 to 14.

Coverage:
- Feature 13: Feedback Conversion Boundaries (Tests 105 to 109)
  105. test_tier2_b13_convert_unconfirmed_feedback_fails: Unconfirmed feedback cannot be converted (409 Conflict).
  106. test_tier2_b13_convert_undelivered_confirmed_feedback_fails: Undelivered feedback cannot be converted (409 Conflict).
  107. test_tier2_b13_convert_nonexistent_feedback_returns_404: Nonexistent feedback conversion returns 404 Not Found.
  108. test_tier2_b13_foreign_agency_cannot_convert_feedback: Foreign agency cannot convert Agency A feedback (404 Not Found).
  109. test_tier2_b13_client_cannot_call_convert_task: Client accounts cannot convert feedback (403 Forbidden).
- Feature 14: Editor Correction Boundaries (Tests 110 to 114)
  110. test_tier2_b14_task_feedback_correct_without_correction_text_fails: Action 'correct' without correction text rejected (422).
  111. test_tier2_b14_task_update_invalid_status: Invalid status string rejected with 422 Validation Error.
  112. test_tier2_b14_task_update_invalid_priority: Invalid priority string rejected with 422 Validation Error.
  113. test_tier2_b14_task_update_oversized_instruction: Instructions exceeding 5,000 chars rejected with 422.
  114. test_tier2_b14_foreign_agency_cannot_modify_task: Foreign agency modifying Agency A task rejected with 404.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.models import ClientFeedback, ProcessingRun, ProductionTask, Project, Transcript

# ==============================================================================
# Feature 13: Feedback Conversion Boundaries (Tests 105-109)
# ==============================================================================

def test_tier2_b13_convert_unconfirmed_feedback_fails(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B13-1: Unconfirmed feedback with status 'awaiting_confirmation' cannot be converted (409 Conflict)."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Unconfirmed Conversion Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        fb = ClientFeedback(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            submitted_by=client_setup["user_id"],
            idempotency_key="fb-b13-unconf-01",
            source_type="text",
            original_text="Rough note requiring confirmation",
            status="awaiting_confirmation",
        )
        db.add(fb)
        db.commit()
        fb_id = fb.id

    resp = agency_client.post(f"/api/agency/feedback/{fb_id}/convert-task")
    assert resp.status_code == 409


def test_tier2_b13_convert_undelivered_confirmed_feedback_fails(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B13-2: Confirmed feedback that has not yet been delivered cannot be converted (409 Conflict)."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Undelivered Conversion Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        fb = ClientFeedback(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            submitted_by=client_setup["user_id"],
            idempotency_key="fb-b13-undeliv-02",
            source_type="text",
            original_text="Confirmed note but not delivered yet",
            status="confirmed",
            client_confirmed_at=datetime.now(UTC),
        )
        db.add(fb)
        db.commit()
        fb_id = fb.id

    resp = agency_client.post(f"/api/agency/feedback/{fb_id}/convert-task")
    assert resp.status_code == 409


def test_tier2_b13_convert_nonexistent_feedback_returns_404(
    agency_client,
):
    """B13-3: Converting nonexistent feedback ID 999999 returns 404 Not Found."""
    resp = agency_client.post("/api/agency/feedback/999999/convert-task")
    assert resp.status_code == 404


def test_tier2_b13_foreign_agency_cannot_convert_feedback(
    foreign_agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B13-4: Foreign agency cannot convert Agency A's feedback (returns 404 Not Found)."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Agency A Feedback Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        fb = ClientFeedback(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            submitted_by=client_setup["user_id"],
            idempotency_key="fb-b13-cross-04",
            source_type="text",
            original_text="Delivered note for Agency A",
            status="delivered",
            delivered_at=datetime.now(UTC),
        )
        db.add(fb)
        db.commit()
        fb_id = fb.id

    resp = foreign_agency_client.post(f"/api/agency/feedback/{fb_id}/convert-task")
    assert resp.status_code == 404


def test_tier2_b13_client_cannot_call_convert_task(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B13-5: Client accounts calling convert-task receive 403 Forbidden."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Client Guard Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        fb = ClientFeedback(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            submitted_by=client_setup["user_id"],
            idempotency_key="fb-b13-role-05",
            source_type="text",
            original_text="Delivered feedback",
            status="delivered",
            delivered_at=datetime.now(UTC),
        )
        db.add(fb)
        db.commit()
        fb_id = fb.id

    resp = client_user_client.post(f"/api/agency/feedback/{fb_id}/convert-task")
    assert resp.status_code == 403


# ==============================================================================
# Feature 14: Editor Correction Boundaries (Tests 110-114)
# ==============================================================================

def test_tier2_b14_task_feedback_correct_without_correction_text_fails(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B14-1: Task feedback with action 'correct' but empty correction text returns 422."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Empty Correction Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        tr = Transcript(project_id=proj.id, content="Sample transcript", created_by=agency_setup["owner_id"])
        db.add(tr)
        db.flush()

        run = ProcessingRun(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            transcript_id=tr.id,
            idempotency_key="run-b14-01",
            status="completed",
        )
        db.add(run)
        db.flush()

        task = ProductionTask(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            run_id=run.id,
            title="Audio Task",
            category="Audio",
            instruction="Initial instruction",
            resolve_workflow="Workflow A",
            source="ai_extraction",
            confidence=0.8,
            status="pending",
        )
        db.add(task)
        db.commit()
        task_id = task.id

    payload = {"action": "correct", "correction": "   "}
    resp = agency_client.post(f"/api/tasks/{task_id}/feedback", json=payload)
    assert resp.status_code == 422


def test_tier2_b14_task_update_invalid_status(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B14-2: Updating task status to non-enum value returns 422 Validation Error."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Status Enum Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        tr = Transcript(project_id=proj.id, content="Sample transcript", created_by=agency_setup["owner_id"])
        db.add(tr)
        db.flush()

        run = ProcessingRun(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            transcript_id=tr.id,
            idempotency_key="run-b14-02",
            status="completed",
        )
        db.add(run)
        db.flush()

        task = ProductionTask(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            run_id=run.id,
            title="Editorial Task",
            category="Editorial",
            instruction="Initial cut",
            resolve_workflow="Workflow B",
            source="ai_extraction",
            confidence=0.8,
            status="pending",
        )
        db.add(task)
        db.commit()
        task_id = task.id

    payload = {"status": "destroyed_and_removed"}
    resp = agency_client.patch(f"/api/tasks/{task_id}", json=payload)
    assert resp.status_code == 422


def test_tier2_b14_task_update_invalid_priority(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B14-3: Updating task priority to non-enum value returns 422 Validation Error."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Priority Enum Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        tr = Transcript(project_id=proj.id, content="Sample transcript", created_by=agency_setup["owner_id"])
        db.add(tr)
        db.flush()

        run = ProcessingRun(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            transcript_id=tr.id,
            idempotency_key="run-b14-03",
            status="completed",
        )
        db.add(run)
        db.flush()

        task = ProductionTask(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            run_id=run.id,
            title="Priority Task",
            category="Editorial",
            instruction="Review pacing",
            resolve_workflow="Workflow C",
            source="ai_extraction",
            confidence=0.85,
            status="pending",
        )
        db.add(task)
        db.commit()
        task_id = task.id

    payload = {"priority": "ultra_critical_super_urgent"}
    resp = agency_client.patch(f"/api/tasks/{task_id}", json=payload)
    assert resp.status_code == 422


def test_tier2_b14_task_update_oversized_instruction(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B14-4: Updating task instruction with text exceeding 5,000 characters returns 422."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Oversized Task Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        tr = Transcript(project_id=proj.id, content="Sample transcript", created_by=agency_setup["owner_id"])
        db.add(tr)
        db.flush()

        run = ProcessingRun(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            transcript_id=tr.id,
            idempotency_key="run-b14-04",
            status="completed",
        )
        db.add(run)
        db.flush()

        task = ProductionTask(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            run_id=run.id,
            title="Length Limit Task",
            category="Editorial",
            instruction="Original short note",
            resolve_workflow="Workflow D",
            source="ai_extraction",
            confidence=0.9,
            status="pending",
        )
        db.add(task)
        db.commit()
        task_id = task.id

    payload = {"instruction": "Z" * 5001}
    resp = agency_client.patch(f"/api/tasks/{task_id}", json=payload)
    assert resp.status_code == 422


def test_tier2_b14_foreign_agency_cannot_modify_task(
    foreign_agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B14-5: Foreign agency attempting to patch Agency A's task receives 404 Not Found."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Agency A Restricted Task Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        tr = Transcript(project_id=proj.id, content="Sample transcript", created_by=agency_setup["owner_id"])
        db.add(tr)
        db.flush()

        run = ProcessingRun(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            transcript_id=tr.id,
            idempotency_key="run-b14-05",
            status="completed",
        )
        db.add(run)
        db.flush()

        task = ProductionTask(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            run_id=run.id,
            title="Private Task",
            category="Color",
            instruction="Do not touch",
            resolve_workflow="Workflow E",
            source="ai_extraction",
            confidence=0.92,
            status="pending",
        )
        db.add(task)
        db.commit()
        task_id = task.id

    payload = {"status": "in_progress", "priority": "urgent"}
    resp = foreign_agency_client.patch(f"/api/tasks/{task_id}", json=payload)
    assert resp.status_code == 404
