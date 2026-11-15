"""Tier 1 Feature 14 Tests: Human Editor Correction & Provenance.

Coverage:
- test_tier1_f14_editor_updates_task_status_and_priority:
  Agency editor updates task status and priority with validation (PATCH /api/tasks/{id}).
- test_tier1_f14_editor_correction_preserves_original_recommendation:
  Editor instruction revision preserves original AI recommendation and stores latest correction note.
- test_tier1_f14_editor_correction_records_feedback_audit_trail:
  Audit history tracks editor author_id, action='correct', timestamps, and text deltas in feedback history.
- test_tier1_f14_post_task_feedback_with_correction:
  Explicit task feedback endpoint records human correction audit row (POST /api/tasks/{id}/feedback).
- test_tier1_f14_editor_confirmed_preference_triggers_memory_operation:
  Client-confirmed editor revision triggers Hindsight retention and logs MemoryOperation row.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Feedback, MemoryOperation, ProcessingRun, ProductionTask, Project, Transcript


def test_tier1_f14_editor_updates_task_status_and_priority(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F14-1: Editor updates task status to 'in_progress' and priority to 'high'."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Task Update Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        tr = Transcript(project_id=proj.id, content="Initial transcript", created_by=agency_setup["owner_id"])
        db.add(tr)
        db.flush()

        run = ProcessingRun(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            transcript_id=tr.id,
            idempotency_key="run-task-update-01",
            status="completed",
        )
        db.add(run)
        db.flush()

        task = ProductionTask(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            run_id=run.id,
            title="Initial Cut Task",
            category="Editorial",
            instruction="Rough assemble sequence 1",
            resolve_workflow="Perform assembly cut in timeline",
            source="ai_extraction",
            confidence=0.85,
            status="pending",
            priority="medium",
        )
        db.add(task)
        db.commit()
        task_id = task.id

    payload = {"status": "in_progress", "priority": "high"}
    resp = agency_client.patch(f"/api/tasks/{task_id}", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "in_progress"
    assert data["priority"] == "high"

    with isolated_db() as db:
        persisted = db.get(ProductionTask, task_id)
        assert persisted.status == "in_progress"
        assert persisted.priority == "high"


def test_tier1_f14_editor_correction_preserves_original_recommendation(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F14-2: Editor instruction modification preserves initial recommendation and sets is_corrected=True."""
    original_ai_note = "Apply heavy 16mm grain across entire timeline"
    editor_new_note = "Use subtle 35mm fine grain at 15% opacity"

    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Correction Provenance Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        tr = Transcript(project_id=proj.id, content="AI generated transcript", created_by=agency_setup["owner_id"])
        db.add(tr)
        db.flush()

        run = ProcessingRun(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            transcript_id=tr.id,
            idempotency_key="run-provenance-02",
            status="completed",
        )
        db.add(run)
        db.flush()

        task = ProductionTask(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            run_id=run.id,
            title="Grain Grade Task",
            category="Color",
            instruction=original_ai_note,
            resolve_workflow="Apply film grain effect in Resolve Color page",
            source="ai_extraction",
            confidence=0.88,
            status="pending",
            priority="medium",
        )
        db.add(task)
        db.commit()
        task_id = task.id

    payload = {
        "instruction": editor_new_note,
        "correction_note": "Client prefers clean subtle texture",
    }
    resp = agency_client.patch(f"/api/tasks/{task_id}", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["instruction"] == editor_new_note
    assert data["is_corrected"] is True
    assert data["original_recommendation"] == original_ai_note
    assert data["latest_correction"] == "Client prefers clean subtle texture"


def test_tier1_f14_editor_correction_records_feedback_audit_trail(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F14-3: Editor corrections persist audit records in feedback history with author_id and timestamp."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Audit History Project",
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
            idempotency_key="run-audit-03",
            status="completed",
        )
        db.add(run)
        db.flush()

        task = ProductionTask(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            run_id=run.id,
            title="Pacing Task",
            category="Editorial",
            instruction="Cut scene at 10.0s",
            resolve_workflow="Blade edit point in Edit page",
            source="ai_extraction",
            confidence=0.90,
            status="pending",
        )
        db.add(task)
        db.commit()
        task_id = task.id

    # Editor patches task
    agency_client.patch(
        f"/api/tasks/{task_id}",
        json={"instruction": "Cut scene at 8.5s", "correction_note": "Tighten beat"},
    )

    # Query task details
    resp = agency_client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data.get("feedback_history", [])) >= 1
    audit = data["feedback_history"][0]
    assert audit["author_id"] == agency_setup["owner_id"]
    assert audit["action"] == "correct"
    assert audit["original_recommendation"] == "Cut scene at 10.0s"
    assert audit["correction"] == "Tighten beat"


def test_tier1_f14_post_task_feedback_with_correction(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F14-4: POST /api/tasks/{id}/feedback records human feedback action with correction."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Direct Feedback Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        tr = Transcript(project_id=proj.id, content="Content text", created_by=agency_setup["owner_id"])
        db.add(tr)
        db.flush()

        run = ProcessingRun(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            transcript_id=tr.id,
            idempotency_key="run-post-fb-04",
            status="completed",
        )
        db.add(run)
        db.flush()

        task = ProductionTask(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            run_id=run.id,
            title="Audio Track EQ",
            category="Audio",
            instruction="Boost high frequencies +4dB",
            resolve_workflow="Adjust Fairlight track EQ band 4",
            source="ai_extraction",
            confidence=0.82,
            status="pending",
        )
        db.add(task)
        db.commit()
        task_id = task.id

    payload = {
        "action": "correct",
        "correction": "Adjust dialogue track EQ -2dB at 4kHz",
        "client_confirmed": False,
    }
    resp = agency_client.post(f"/api/tasks/{task_id}/feedback", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == task_id
    assert data.get("task_status") == "corrected" or data.get("status") == "corrected"
    assert data["feedback_id"] > 0

    with isolated_db() as db:
        fb = db.get(Feedback, data["feedback_id"])
        assert fb is not None
        assert fb.correction == "Adjust dialogue track EQ -2dB at 4kHz"
        assert fb.action == "correct"


def test_tier1_f14_editor_confirmed_preference_triggers_memory_operation(
    agency_client,
    agency_setup,
    client_setup,
    mock_hindsight,
    isolated_db,
):
    """F14-5: Client-confirmed editor correction retains into Hindsight memory bank and logs MemoryOperation."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Memory Retention Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        tr = Transcript(project_id=proj.id, content="Transcript data", created_by=agency_setup["owner_id"])
        db.add(tr)
        db.flush()

        run = ProcessingRun(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            transcript_id=tr.id,
            idempotency_key="run-memory-05",
            status="completed",
        )
        db.add(run)
        db.flush()

        task = ProductionTask(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            run_id=run.id,
            title="Aspect Ratio Standard",
            category="Editorial",
            instruction="Set timeline to 16:9",
            resolve_workflow="Set timeline resolution to 3840x1606",
            source="ai_extraction",
            confidence=0.91,
            status="pending",
        )
        db.add(task)
        db.commit()
        task_id = task.id

    payload = {
        "instruction": "Always use 2.39:1 anamorphic aspect ratio",
        "correction_note": "Client confirmed recurring 2.39:1 brand framing",
        "client_confirmed": True,
        "knowledge_type": "reusable_client_knowledge",
    }
    resp = agency_client.patch(f"/api/tasks/{task_id}", json=payload)
    assert resp.status_code == 200

    with isolated_db() as db:
        mem_ops = db.scalars(
            select(MemoryOperation).where(
                MemoryOperation.client_id == client_setup["client_id"],
                MemoryOperation.operation == "retain",
            )
        ).all()
        assert len(mem_ops) >= 1
        latest_op = mem_ops[-1]
        assert latest_op.status == "completed"
        assert latest_op.provenance == "reusable_client_knowledge"

    # Verify memory bank in mock Hindsight
    bank_memories = mock_hindsight._banks.get(client_setup["memory_bank_id"], [])
    assert any("2.39:1" in (m.get("text") or m.get("content") or "") for m in bank_memories)
