import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    Client,
    ExtractedItem,
    Feedback,
    MemoryOperation,
    ProcessingRun,
    ProductionTask,
    Project,
    Transcript,
    User,
)
from ..schemas import (
    AdaptiveKnowledgeInput,
    TaskUpdateInput,
)
from ..security import current_identity
from ..services import hindsight
from ..services.asset_intelligence import get_project_asset_intelligence
from ..services.production_analytics import get_production_analytics

router = APIRouter(tags=["production-intelligence"])
log = logging.getLogger("frameops.production")


def _get_client_in_workspace(db: Session, client_id: int, workspace_id: int) -> Client:
    client = db.scalar(select(Client).where(Client.id == client_id, Client.workspace_id == workspace_id))
    if not client:
        raise HTTPException(404, "Client not found in workspace")
    return client


def _get_project_in_workspace(db: Session, project_id: int, workspace_id: int) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id))
    if not project:
        raise HTTPException(404, "Project not found in workspace")
    return project


def _get_task_in_workspace(db: Session, task_id: int, workspace_id: int) -> ProductionTask:
    task = db.scalar(select(ProductionTask).where(ProductionTask.id == task_id, ProductionTask.workspace_id == workspace_id))
    if not task:
        raise HTTPException(404, "Task not found in workspace")
    return task


def _build_feedback_dict(f: Feedback, author_email: str = "") -> dict:
    return {
        "id": f.id,
        "task_id": f.task_id,
        "author_id": f.author_id,
        "author_email": author_email,
        "action": f.action,
        "original_recommendation": f.original_recommendation,
        "correction": f.correction,
        "client_confirmed": f.client_confirmed,
        "retention_status": f.retention_status,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


def _rich_task_dict(t: ProductionTask, db: Session) -> dict:
    # 1. Fetch feedbacks for this task
    feedbacks = db.scalars(
        select(Feedback).where(Feedback.task_id == t.id).order_by(Feedback.created_at.desc())
    ).all()

    # Cache author emails
    author_ids = list({f.author_id for f in feedbacks})
    authors = {}
    if author_ids:
        users = db.scalars(select(User).where(User.id.in_(author_ids))).all()
        authors = {u.id: u.email for u in users}

    feedback_list = [_build_feedback_dict(f, authors.get(f.author_id, "editor")) for f in feedbacks]

    # Resolve project and client names
    project = db.get(Project, t.project_id)
    client = db.get(Client, t.client_id)

    # Determine original recommendation:
    # If corrections exist, the earliest feedback has the original AI recommendation
    # Otherwise, task.instruction is the original recommendation.
    if feedbacks:
        earliest = feedbacks[-1]
        original_rec = earliest.original_recommendation or t.instruction
    else:
        original_rec = t.instruction

    is_corrected = any(f.action == "correct" or (f.correction and f.correction != t.instruction) for f in feedbacks)
    latest_correction = next((f.correction for f in feedbacks if f.correction), None)

    return {
        "id": t.id,
        "workspace_id": t.workspace_id,
        "client_id": t.client_id,
        "client_name": client.name if client else "",
        "project_id": t.project_id,
        "project_name": project.name if project else "",
        "run_id": t.run_id,
        "title": t.title,
        "category": t.category,
        "instruction": t.instruction,
        "original_recommendation": original_rec,
        "is_corrected": is_corrected,
        "latest_correction": latest_correction,
        "resolve_workflow": t.resolve_workflow,
        "priority": t.priority,
        "source": t.source,
        "evidence": t.evidence,
        "confidence": t.confidence,
        "requires_confirmation": t.requires_confirmation,
        "status": t.status,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "feedback_count": len(feedback_list),
        "latest_feedback": feedback_list[0] if feedback_list else None,
        "feedback_history": feedback_list,
    }


# =========================================================================
# 1. Production Tasks Management Endpoints
# =========================================================================

@router.get("/api/tasks")
def list_production_tasks(
    project_id: int | None = None,
    client_id: int | None = None,
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    identity=Depends(current_identity),
):
    """
    List production tasks with multi-field filtering, search, and rich provenance.
    """
    _, wid, _ = identity
    stmt = select(ProductionTask).where(ProductionTask.workspace_id == wid)

    if project_id is not None:
        stmt = stmt.where(ProductionTask.project_id == project_id)
    if client_id is not None:
        stmt = stmt.where(ProductionTask.client_id == client_id)
    if status and status != "all":
        stmt = stmt.where(ProductionTask.status == status)
    if priority and priority != "all":
        stmt = stmt.where(ProductionTask.priority == priority)
    if category and category != "all":
        stmt = stmt.where(ProductionTask.category == category)

    tasks = db.scalars(stmt.order_by(ProductionTask.created_at.desc())).all()

    # Search filter in Python for flexibility with instruction and title
    if search and search.strip():
        q = search.strip().lower()
        tasks = [t for t in tasks if q in t.title.lower() or q in t.instruction.lower() or q in t.category.lower()]

    return [_rich_task_dict(t, db) for t in tasks]


@router.get("/api/tasks/{task_id}")
def get_task_details(
    task_id: int,
    db: Session = Depends(get_db),
    identity=Depends(current_identity),
):
    """
    Get detailed task intelligence including source transcript run, linked quotes, and audit history.
    """
    _, wid, _ = identity
    task = _get_task_in_workspace(db, task_id, wid)
    rich = _rich_task_dict(task, db)

    # Source run details
    run = db.get(ProcessingRun, task.run_id)
    source_run = None
    if run:
        transcript = db.get(Transcript, run.transcript_id) if run.transcript_id else None
        source_run = {
            "id": run.id,
            "status": run.status,
            "stage": run.stage,
            "created_at": run.created_at.isoformat(),
            "transcript_preview": transcript.content[:300] if transcript else "",
        }

    # Linked extractions from the same run
    linked_items = []
    if task.run_id:
        items = db.scalars(
            select(ExtractedItem).where(ExtractedItem.run_id == task.run_id)
        ).all()
        # Find items that match category or keywords
        for it in items:
            if it.category == task.category or any(w in it.description.lower() for w in task.title.lower().split() if len(w) > 4):
                linked_items.append({
                    "id": it.id,
                    "description": it.description,
                    "category": it.category,
                    "source_quote": it.source_quote,
                    "classification": it.classification,
                    "confidence": it.confidence,
                    "requires_confirmation": it.requires_confirmation,
                })

    rich["source_run"] = source_run
    rich["linked_extractions"] = linked_items
    return rich


@router.patch("/api/tasks/{task_id}")
async def update_production_task(
    task_id: int,
    data: TaskUpdateInput,
    db: Session = Depends(get_db),
    identity=Depends(current_identity),
):
    """
    Update a production task:
    - Status: pending, in_progress, completed, blocked, accepted, rejected
    - Priority: low, medium, high, urgent
    - Instruction / text: preserves original AI recommendation and stores editor correction with provenance.
    """
    user, wid, _ = identity
    task = _get_task_in_workspace(db, task_id, wid)

    old_instruction = task.instruction
    status_changed = data.status is not None and data.status != task.status
    priority_changed = data.priority is not None and data.priority != task.priority
    instruction_changed = data.instruction is not None and data.instruction.strip() != old_instruction.strip()

    # Apply direct field updates
    if data.status:
        task.status = data.status
    if data.priority:
        task.priority = data.priority
    if data.title:
        task.title = data.title.strip()
    if data.resolve_workflow:
        task.resolve_workflow = data.resolve_workflow.strip()

    # If instruction was changed, update task.instruction and record feedback provenance
    correction_text = data.correction_note.strip() if data.correction_note else ""
    if instruction_changed:
        task.instruction = data.instruction.strip()
        if not correction_text:
            correction_text = data.instruction.strip()

    # Determine if we should record feedback
    record_feedback = instruction_changed or bool(correction_text) or status_changed or priority_changed or data.client_confirmed

    if record_feedback:
        action = "correct" if instruction_changed else ("accept" if data.status in ("accepted", "completed") else (data.status or "status_change"))
        feedback_row = Feedback(
            workspace_id=wid,
            client_id=task.client_id,
            project_id=task.project_id,
            task_id=task.id,
            author_id=user.id,
            action=action,
            original_recommendation=old_instruction,
            correction=correction_text or (f"Status changed to {task.status}"),
            client_confirmed=data.client_confirmed,
            retention_status="not_requested",
        )
        db.add(feedback_row)
        db.flush()

        # Handle adaptive memory retention for reusable knowledge or client-confirmed preferences
        should_retain = data.knowledge_type == "reusable_client_knowledge" or data.client_confirmed
        if should_retain:
            client = db.get(Client, task.client_id)
            if client:
                content = (
                    f"Client-confirmed preference: {correction_text or task.instruction}"
                    if data.client_confirmed
                    else f"Reusable client knowledge from editor: {correction_text or task.instruction}"
                )
                context = (
                    f"FRAMEOPS production task decision; workspace={wid}; client={client.id}; "
                    f"project={task.project_id}; task={task.id}; provenance={data.knowledge_type}; confirmed={data.client_confirmed}"
                )
                key = f"task-update:{task.id}:{uuid4().hex[:12]}"
                op = MemoryOperation(
                    workspace_id=wid,
                    client_id=client.id,
                    project_id=task.project_id,
                    run_id=task.run_id,
                    operation="retain",
                    status="pending",
                    idempotency_key=key,
                    provenance=data.knowledge_type,
                    details=f"Task {task.id} updated by {user.email}",
                )
                db.add(op)
                db.flush()

                if hindsight.configured():
                    try:
                        _, verified = await hindsight.retain_and_verify(
                            client.memory_bank_id,
                            content,
                            context,
                            ["frameops", data.knowledge_type, "confirmed" if data.client_confirmed else "unconfirmed"],
                            f"frameops-task-{task.id}-{uuid4().hex[:8]}",
                        )
                        op.status = "completed" if verified else "failed"
                        op.details = "Hindsight retention verified." if verified else "Verification recall did not confirm content."
                        feedback_row.retention_status = "verified" if verified else "verification_failed"
                    except Exception as exc:
                        op.status = "failed"
                        op.details = str(exc)
                        feedback_row.retention_status = "failed"
                else:
                    op.status = "completed"
                    op.details = "Retained in local production memory (Hindsight service not configured)."
                    feedback_row.retention_status = "local_only"

    db.commit()
    return _rich_task_dict(task, db)


# =========================================================================
# 2. Production Analytics Endpoint
# =========================================================================

@router.get("/api/production-analytics")
def get_comprehensive_production_analytics(
    db: Session = Depends(get_db),
    identity=Depends(current_identity),
):
    """
    Returns real dashboard metrics based strictly on persisted database records.
    Never generates fabricated charts or activity.
    """
    _, wid, _ = identity
    return get_production_analytics(db, wid)


# =========================================================================
# 3. Asset Intelligence Endpoints
# =========================================================================

@router.get("/api/projects/{project_id}/asset-intelligence")
def get_project_asset_intelligence_endpoint(
    project_id: int,
    db: Session = Depends(get_db),
    identity=Depends(current_identity),
):
    """
    Evidence-based asset tracking for a project across:
    - Reference assets
    - Brand logos
    - Fonts & typography
    - Music & audio
    - Video footage
    - Other production resources
    Statuses: Present, Missing, Unknown, Unverified.
    """
    _, wid, _ = identity
    project = _get_project_in_workspace(db, project_id, wid)
    return get_project_asset_intelligence(db, project, wid)


# =========================================================================
# 4. Adaptive Intelligence & Knowledge Distillation Endpoints
# =========================================================================

@router.get("/api/clients/{client_id}/adaptive-knowledge")
async def get_client_adaptive_knowledge(
    client_id: int,
    db: Session = Depends(get_db),
    identity=Depends(current_identity),
):
    """
    Distinguishes and returns client intelligence across:
    - AI-generated recommendations
    - Editor corrections
    - Client-confirmed preferences
    - Project-specific decisions
    - Reusable client knowledge
    """
    _, wid, _ = identity
    client = _get_client_in_workspace(db, client_id, wid)

    # 1. AI-generated recommendations (from production tasks)
    tasks = db.scalars(
        select(ProductionTask).where(ProductionTask.client_id == client.id, ProductionTask.workspace_id == wid).order_by(ProductionTask.created_at.desc())
    ).all()

    ai_recommendations = [
        {
            "id": t.id,
            "title": t.title,
            "category": t.category,
            "instruction": t.instruction,
            "resolve_workflow": t.resolve_workflow,
            "confidence": t.confidence,
            "source": t.source,
            "evidence": t.evidence,
            "requires_confirmation": t.requires_confirmation,
            "status": t.status,
            "project_id": t.project_id,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tasks
    ]

    # 2. Feedbacks (Editor corrections, Client-confirmed preferences)
    feedbacks = db.scalars(
        select(Feedback).where(Feedback.client_id == client.id, Feedback.workspace_id == wid).order_by(Feedback.created_at.desc())
    ).all()

    # Preload user emails
    author_ids = list({f.author_id for f in feedbacks})
    authors = {}
    if author_ids:
        users = db.scalars(select(User).where(User.id.in_(author_ids))).all()
        authors = {u.id: u.email for u in users}

    editor_corrections = []
    client_confirmed_preferences = []

    for f in feedbacks:
        entry = {
            "id": f.id,
            "task_id": f.task_id,
            "project_id": f.project_id,
            "author": authors.get(f.author_id, "Editor"),
            "action": f.action,
            "original_recommendation": f.original_recommendation,
            "correction": f.correction,
            "client_confirmed": f.client_confirmed,
            "retention_status": f.retention_status,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        if f.action == "correct" or (f.correction and f.correction != f.original_recommendation):
            editor_corrections.append(entry)
        if f.client_confirmed:
            client_confirmed_preferences.append(entry)

    # 3. Memory Operations (reusable knowledge vs project-specific)
    memory_ops = db.scalars(
        select(MemoryOperation).where(MemoryOperation.client_id == client.id, MemoryOperation.workspace_id == wid).order_by(MemoryOperation.created_at.desc())
    ).all()

    reusable_knowledge = []
    project_specific_decisions = []

    for m in memory_ops:
        m_entry = {
            "id": m.id,
            "operation": m.operation,
            "status": m.status,
            "provenance": m.provenance,
            "project_id": m.project_id,
            "details": m.details,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        if m.provenance in ("reusable_client_knowledge", "client_confirmed"):
            reusable_knowledge.append(m_entry)
        elif m.provenance == "project_specific":
            project_specific_decisions.append(m_entry)

    # 4. Hindsight live memory bank records if configured
    hindsight_memories = []
    if hindsight.configured() and client.memory_bank_id:
        try:
            mem_result = await hindsight.call_memory("GET", client.memory_bank_id, "list", {})
            hindsight_memories = mem_result.get("results", mem_result.get("memories", []))
            if not isinstance(hindsight_memories, list):
                hindsight_memories = []
        except Exception as exc:
            log.warning("Could not list remote hindsight memories: %s", exc)

    return {
        "client_id": client.id,
        "client_name": client.name,
        "brand": client.brand,
        "memory_status": client.memory_status,
        "counts": {
            "ai_recommendations": len(ai_recommendations),
            "editor_corrections": len(editor_corrections),
            "client_confirmed_preferences": len(client_confirmed_preferences),
            "reusable_client_knowledge": len(reusable_knowledge),
            "project_specific_decisions": len(project_specific_decisions),
            "hindsight_memories": len(hindsight_memories),
        },
        "ai_recommendations": ai_recommendations,
        "editor_corrections": editor_corrections,
        "client_confirmed_preferences": client_confirmed_preferences,
        "reusable_client_knowledge": reusable_knowledge,
        "project_specific_decisions": project_specific_decisions,
        "hindsight_memories": hindsight_memories,
    }


@router.post("/api/clients/{client_id}/adaptive-knowledge", status_code=201)
async def create_client_adaptive_knowledge(
    client_id: int,
    data: AdaptiveKnowledgeInput,
    db: Session = Depends(get_db),
    identity=Depends(current_identity),
):
    """
    Directly register a confirmed client preference or reusable client knowledge.
    Preserves author identity, provenance, and retains to Hindsight if configured.
    """
    user, wid, _ = identity
    client = _get_client_in_workspace(db, client_id, wid)

    if data.project_id:
        _get_project_in_workspace(db, data.project_id, wid)

    provenance = data.knowledge_type
    if data.client_confirmed and provenance != "client_confirmed":
        provenance = "client_confirmed"

    key = f"knowledge:{client.id}:{uuid4().hex[:12]}"
    op = MemoryOperation(
        workspace_id=wid,
        client_id=client.id,
        project_id=data.project_id,
        run_id=None,
        operation="retain",
        status="pending",
        idempotency_key=key,
        provenance=provenance,
        details=f"Direct knowledge entry by {user.email}: {data.content[:200]}",
    )
    db.add(op)
    db.commit()
    db.refresh(op)

    retention_status = "local_only"
    if hindsight.configured() and provenance in ("client_confirmed", "reusable_client_knowledge"):
        try:
            _, verified = await hindsight.retain_and_verify(
                client.memory_bank_id,
                data.content,
                f"FRAMEOPS client knowledge; workspace={wid}; client={client.id}; provenance={provenance}; confirmed={data.client_confirmed}",
                ["frameops", provenance, "confirmed" if data.client_confirmed else "unconfirmed"],
                f"frameops-knowledge-{op.id}",
            )
            op.status = "completed" if verified else "failed"
            op.details = "Hindsight retention verified." if verified else "Verification recall did not confirm content."
            retention_status = "verified" if verified else "verification_failed"
            db.commit()
        except Exception as exc:
            op.status = "failed"
            op.details = str(exc)
            retention_status = "failed"
            db.commit()
    else:
        op.status = "completed"
        op.details = "Stored in local memory operations."
        db.commit()

    return {
        "id": op.id,
        "client_id": client.id,
        "content": data.content,
        "knowledge_type": provenance,
        "client_confirmed": data.client_confirmed,
        "retention_status": retention_status,
        "created_at": op.created_at.isoformat(),
    }
