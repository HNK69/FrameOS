"""Tier 3 Pairwise Combinations: AI Extraction, Tasks, Human Editor Correction & Memory Retention.

Coverage:
- test_tier3_c10_ai_feedback_task_conversion_human_approval_gate:
  Scenario T3-10 (F11 AI Extraction x F13 Task Conversion).
  Delivered client feedback converts to ProductionTask requiring human approval (status='pending').
- test_tier3_c11_human_editor_correction_provenance_preservation:
  Scenario T3-11 (F13 Task Conversion x F14 Editor Provenance).
  Editor corrections update task instruction while preserving original AI recommendation in audit table.
- test_tier3_c12_unconfirmed_note_memory_retention_rejection:
  Scenario T3-12 (F14 Editor Provenance x F15 Hindsight Memory).
  Unconfirmed subjective notes cannot be saved as client_confirmed memory; confirmed preferences succeed.
- test_tier3_c18_full_intelligence_roundtrip_feedback_to_hindsight:
  Scenario T3-18 (F11 AI Extraction x F13 Task Conversion x F14 Editor Provenance x F15 Hindsight Memory).
  Full end-to-end intelligence cycle: Raw Feedback -> Extraction -> Task -> Correction -> Confirmation -> Hindsight.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.models import (
    ClientFeedback,
    Feedback,
    ProcessingRun,
    ProductionTask,
    Project,
    Transcript,
)


def test_tier3_c10_ai_feedback_task_conversion_human_approval_gate(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """T3-10: Client confirmed feedback is delivered and converted to task requiring human review."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Gate Workflow Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        fb = ClientFeedback(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            submitted_by=client_setup["user_id"],
            idempotency_key="fb-c10-gate-01",
            source_type="text",
            original_text="Adjust pacing and trim 2s from hook",
            status="confirmed",
            client_confirmed_at=datetime.now(UTC),
        )
        db.add(fb)
        db.commit()
        fb_id = fb.id

    # 1. Agency delivers feedback
    resp_deliv = agency_client.post(f"/api/agency/feedback/{fb_id}/deliver")
    assert resp_deliv.status_code == 200
    assert resp_deliv.json()["status"] == "delivered"

    # 2. Agency converts feedback to production task
    resp_conv = agency_client.post(f"/api/agency/feedback/{fb_id}/convert-task")
    assert resp_conv.status_code == 200
    task_id = resp_conv.json()["task_id"]

    # 3. Query task: verify status is 'pending' (human review gate)
    resp_task = agency_client.get(f"/api/tasks/{task_id}")
    assert resp_task.status_code == 200
    task_data = resp_task.json()
    assert task_data["status"] == "pending"
    assert task_data["source"] == "client_feedback"


def test_tier3_c11_human_editor_correction_provenance_preservation(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """T3-11: Editor corrects AI task, preserving initial instruction and recording audit history."""
    ai_note = "Add heavy vignette to all edge shots"
    editor_note = "Disable vignette, boost midtones by 5%"

    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Provenance Preservation Project",
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
            idempotency_key="run-c11-01",
            status="completed",
        )
        db.add(run)
        db.flush()

        task = ProductionTask(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            run_id=run.id,
            title="Edge Vignette Task",
            category="Color",
            instruction=ai_note,
            resolve_workflow="Open Color page vignette node",
            source="ai_extraction",
            confidence=0.85,
            status="pending",
        )
        db.add(task)
        db.commit()
        task_id = task.id

    payload = {
        "instruction": editor_note,
        "correction_note": "Client prefers natural clean edge lighting",
    }
    resp = agency_client.patch(f"/api/tasks/{task_id}", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["instruction"] == editor_note
    assert data["is_corrected"] is True
    assert data["original_recommendation"] == ai_note

    with isolated_db() as db:
        fb_row = db.scalar(select(Feedback).where(Feedback.task_id == task_id))
        assert fb_row is not None
        assert fb_row.action == "correct"
        assert fb_row.original_recommendation == ai_note
        assert fb_row.author_id == agency_setup["owner_id"]


def test_tier3_c12_unconfirmed_note_memory_retention_rejection(
    agency_client,
    client_setup,
    mock_hindsight,
):
    """T3-12: Unconfirmed notes with false provenance are rejected; confirmed memories succeed."""
    cid = client_setup["client_id"]

    # 1. Invalid combination: client_confirmed=True with mismatched provenance
    invalid_payload = {
        "client_id": cid,
        "content": "Unverified editorial note",
        "provenance": "editor_correction",
        "client_confirmed": True,
    }
    resp_inv = agency_client.post("/api/memory/retain", json=invalid_payload)
    assert resp_inv.status_code == 422

    # 2. Valid confirmed preference
    valid_payload = {
        "client_id": cid,
        "content": "Always frame corporate interviews in 16:9 center cut",
        "provenance": "client_confirmed",
        "client_confirmed": True,
    }
    resp_val = agency_client.post("/api/memory/retain", json=valid_payload)
    assert resp_val.status_code == 200
    assert resp_val.json()["status"] == "completed"

    bank_id = client_setup["memory_bank_id"]
    memories = mock_hindsight._banks.get(bank_id, [])
    assert any("center cut" in (m.get("text") or m.get("content") or "") for m in memories)


def test_tier3_c18_full_intelligence_roundtrip_feedback_to_hindsight(
    agency_client,
    agency_setup,
    client_setup,
    mock_hindsight,
    isolated_db,
):
    """T3-18: Full intelligence roundtrip: Transcript -> Extraction -> Task -> Correction -> Confirmation -> Hindsight."""
    # 1. Start with Project
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Full Roundtrip Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    # 2. Agency runs process-transcript
    transcript = (
        "1. Warm up the color grade on indoor office scenes.\n"
        "2. Balance dialogue track against the background music."
    )
    resp_proc = agency_client.post(
        "/api/process-transcript",
        json={"project_id": proj_id, "transcript": transcript},
    )
    assert resp_proc.status_code == 201

    # 3. Retrieve created task
    resp_tasks = agency_client.get(f"/api/tasks?project_id={proj_id}")
    assert resp_tasks.status_code == 200
    tasks = resp_tasks.json()
    assert len(tasks) >= 1
    task = tasks[0]
    task_id = task["id"]

    # 4. Human editor corrects task and client confirms reusable brand framing
    correction_payload = {
        "instruction": "Apply warm organic 3200K color grade across all indoor scenes",
        "correction_note": "Client confirmed recurring warm color aesthetic",
        "client_confirmed": True,
        "knowledge_type": "reusable_client_knowledge",
    }
    resp_patch = agency_client.patch(f"/api/tasks/{task_id}", json=correction_payload)
    assert resp_patch.status_code == 200
    patch_data = resp_patch.json()
    assert patch_data["is_corrected"] is True

    # 5. Verify Hindsight retained the confirmed preference
    bank_id = client_setup["memory_bank_id"]
    bank_memories = mock_hindsight._banks.get(bank_id, [])
    assert any("warm" in (m.get("text") or m.get("content") or "").lower() for m in bank_memories)

    # 6. Verify full audit history on task
    resp_audit = agency_client.get(f"/api/tasks/{task_id}")
    assert resp_audit.status_code == 200
    audit_data = resp_audit.json()
    assert len(audit_data.get("feedback_history", [])) >= 1
    latest_hist = audit_data["feedback_history"][0]
    assert latest_hist["author_id"] == agency_setup["owner_id"]
    assert latest_hist["action"] == "correct"
