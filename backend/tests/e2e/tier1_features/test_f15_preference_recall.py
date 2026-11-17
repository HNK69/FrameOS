"""Tier 1 Feature 15 Tests: Long-term Client Preference Recall.

Coverage:
- test_tier1_f15_direct_retain_confirmed_client_preference:
  Directly retains confirmed preference into client Hindsight memory bank (POST /api/memory/retain).
- test_tier1_f15_recall_client_preference_from_memory_bank:
  Queries client memory bank to recall retained creative preferences (POST /api/memory/recall).
- test_tier1_f15_unconfirmed_feedback_not_retained_in_hindsight:
  Unconfirmed editor modifications do not retain into Hindsight, preventing memory contamination.
- test_tier1_f15_future_project_recalls_past_client_preference:
  Subsequent project transcript processing automatically recalls past preferences from client's memory bank.
- test_tier1_f15_client_adaptive_knowledge_dashboard_breakdown:
  Client adaptive knowledge endpoint returns categorized breakdown of recommendations, corrections, and memories (GET /api/clients/{id}/adaptive-knowledge).
"""

from __future__ import annotations

from sqlalchemy import select

from app.models import (
    MemoryOperation,
    ProcessingRun,
    ProductionTask,
    Project,
    Transcript,
)


def test_tier1_f15_direct_retain_confirmed_client_preference(
    agency_client,
    client_setup,
    mock_hindsight,
    isolated_db,
):
    """F15-1: Retains confirmed preference into client memory bank via POST /api/memory/retain."""
    payload = {
        "client_id": client_setup["client_id"],
        "content": "Client prefers clean lower thirds with Neue Haas Grotesk",
        "provenance": "client_confirmed",
        "client_confirmed": True,
    }

    resp = agency_client.post("/api/memory/retain", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["operation_id"] > 0
    assert data["status"] == "completed"

    bank_id = client_setup["memory_bank_id"]
    memories = mock_hindsight._banks.get(bank_id, [])
    assert any("Neue Haas Grotesk" in (m.get("text") or m.get("content") or "") for m in memories)


def test_tier1_f15_recall_client_preference_from_memory_bank(
    agency_client,
    client_setup,
    mock_hindsight,
):
    """F15-2: Queries client memory bank via POST /api/memory/recall to retrieve brand preferences."""
    # Seed preference into client memory bank using mock helper
    bank_id = client_setup["memory_bank_id"]
    mock_hindsight.seed_memory(
        bank_id=bank_id,
        content="Client prefers clean lower thirds with Neue Haas Grotesk font",
        context="Brand typography guidelines",
        tags=["confirmed", "typography"],
    )

    cid = client_setup["client_id"]
    resp = agency_client.post(f"/api/memory/recall?client_id={cid}&query=lower+thirds+font")
    assert resp.status_code == 200
    data = resp.json()
    results = data.get("results", [])
    assert len(results) >= 1
    assert any("Neue Haas Grotesk" in (r.get("text") or r.get("content") or "") for r in results)


def test_tier1_f15_unconfirmed_feedback_not_retained_in_hindsight(
    agency_client,
    agency_setup,
    client_setup,
    mock_hindsight,
    isolated_db,
):
    """F15-3: Unconfirmed editor correction does not retain into Hindsight bank, preventing contamination."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Temporary Fix Project",
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
            idempotency_key="run-temp-03",
            status="completed",
        )
        db.add(run)
        db.flush()

        task = ProductionTask(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            run_id=run.id,
            title="Temp Audio Adjust",
            category="Audio",
            instruction="Mute audio at 05.0s",
            resolve_workflow="Mute audio clip in timeline",
            source="ai_extraction",
            confidence=0.75,
            status="pending",
        )
        db.add(task)
        db.commit()
        task_id = task.id

    bank_id = client_setup["memory_bank_id"]
    initial_count = len(mock_hindsight._banks.get(bank_id, []))

    payload = {
        "instruction": "Temporary ducking fix for scene 3",
        "client_confirmed": False,
        "knowledge_type": "editor_correction",
    }
    resp = agency_client.patch(f"/api/tasks/{task_id}", json=payload)
    assert resp.status_code == 200

    # Ensure no confirmed memory was added to Hindsight
    current_memories = mock_hindsight._banks.get(bank_id, [])
    assert len(current_memories) == initial_count


def test_tier1_f15_future_project_recalls_past_client_preference(
    agency_client,
    agency_setup,
    client_setup,
    mock_hindsight,
    isolated_db,
):
    """F15-4: Future project transcript processing automatically recalls retained preferences."""
    # 1. Seed past preference into client's memory bank using seed_memory helper
    bank_id = client_setup["memory_bank_id"]
    mock_hindsight.seed_memory(
        bank_id=bank_id,
        content="Client prefers dark moody lighting for indoor scenes",
        context="Project 1 delivery review",
        tags=["confirmed", "lighting"],
    )

    # 2. Create Project 2 for the same client
    with isolated_db() as db:
        proj2 = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Brand Film Project 2",
            status="active",
        )
        db.add(proj2)
        db.commit()
        proj2_id = proj2.id

    # 3. Process transcript for Project 2
    transcript_payload = {
        "project_id": proj2_id,
        "transcript": "Interior dialogue scene needs dark moody lighting and color grading.",
    }
    resp = agency_client.post("/api/process-transcript", json=transcript_payload)
    assert resp.status_code == 201

    # Verify recall operation was logged for Project 2
    with isolated_db() as db:
        mem_op = db.scalar(
            select(MemoryOperation).where(
                MemoryOperation.project_id == proj2_id,
                MemoryOperation.operation == "recall",
            )
        )
        assert mem_op is not None
        assert mem_op.status == "completed"


def test_tier1_f15_client_adaptive_knowledge_dashboard_breakdown(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F15-5: Adaptive knowledge endpoint returns structured breakdown of recommendations, corrections, and memories."""
    cid = client_setup["client_id"]

    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=cid,
            name="Dashboard Knowledge Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        # Add a memory operation
        op = MemoryOperation(
            workspace_id=agency_setup["workspace_id"],
            client_id=cid,
            project_id=proj.id,
            run_id=None,
            operation="retain",
            status="completed",
            idempotency_key="adapt-dash-op-01",
            provenance="client_confirmed",
            details="Confirmed preference for minimalist title cards",
        )
        db.add(op)
        db.commit()

    resp = agency_client.get(f"/api/clients/{cid}/adaptive-knowledge")
    assert resp.status_code == 200
    data = resp.json()
    assert data["client_id"] == cid
    assert "counts" in data
    assert "ai_recommendations" in data
    assert "editor_corrections" in data
    assert "client_confirmed_preferences" in data
    assert "reusable_client_knowledge" in data
    assert "hindsight_memories" in data
    assert data["counts"]["reusable_client_knowledge"] >= 1
