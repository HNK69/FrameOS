from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    Asset,
    Client,
    Feedback,
    MemoryOperation,
    ProcessingRun,
    ProductionTask,
    Project,
)


def get_production_analytics(db: Session, workspace_id: int) -> dict[str, Any]:
    """
    Computes real production analytics strictly based on persisted records.
    Returns clear empty states when data is absent.
    Never fabricates charts, numbers, or activity.
    """
    # 1. Projects metrics
    total_projects = db.scalar(select(func.count(Project.id)).where(Project.workspace_id == workspace_id)) or 0
    active_projects = db.scalar(select(func.count(Project.id)).where(Project.workspace_id == workspace_id, Project.status == "active")) or 0
    completed_projects = db.scalar(select(func.count(Project.id)).where(Project.workspace_id == workspace_id, Project.status == "completed")) or 0
    archived_projects = db.scalar(select(func.count(Project.id)).where(Project.workspace_id == workspace_id, Project.status == "archived")) or 0

    clients_count = db.scalar(select(func.count(Client.id)).where(Client.workspace_id == workspace_id)) or 0

    # 2. Tasks metrics
    all_tasks = db.scalars(select(ProductionTask).where(ProductionTask.workspace_id == workspace_id)).all()
    total_tasks = len(all_tasks)

    pending_tasks = sum(1 for t in all_tasks if t.status == "pending")
    in_progress_tasks = sum(1 for t in all_tasks if t.status == "in_progress")
    # Completed tasks include both status "completed" and status "accepted"
    completed_tasks = sum(1 for t in all_tasks if t.status in ("completed", "accepted"))
    blocked_tasks = sum(1 for t in all_tasks if t.status == "blocked")
    rejected_tasks = sum(1 for t in all_tasks if t.status == "rejected")

    # Priority distribution
    priority_counts = {
        "urgent": sum(1 for t in all_tasks if t.priority == "urgent"),
        "high": sum(1 for t in all_tasks if t.priority == "high"),
        "medium": sum(1 for t in all_tasks if t.priority == "medium"),
        "low": sum(1 for t in all_tasks if t.priority == "low"),
    }

    # Category distribution
    category_counts: dict[str, int] = {}
    for t in all_tasks:
        cat = t.category or "general"
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # 3. Feedback and Client Revisions
    all_feedback = db.scalars(select(Feedback).where(Feedback.workspace_id == workspace_id)).all()
    total_feedback = len(all_feedback)
    corrections_count = sum(1 for f in all_feedback if f.action == "correct")
    acceptances_count = sum(1 for f in all_feedback if f.action == "accept")
    rejections_count = sum(1 for f in all_feedback if f.action == "reject")
    client_confirmed_feedback = sum(1 for f in all_feedback if f.client_confirmed)

    acceptance_rate = round((acceptances_count / total_feedback * 100), 1) if total_feedback > 0 else None

    # 4. Turnaround indicators (computed strictly from real records)
    # Task turnaround: time between task creation and feedback timestamp
    task_turnaround_hours: list[float] = []
    task_map = {t.id: t for t in all_tasks}
    for f in all_feedback:
        t = task_map.get(f.task_id)
        if t and f.created_at and t.created_at:
            delta = (f.created_at - t.created_at).total_seconds() / 3600.0
            if delta >= 0:
                task_turnaround_hours.append(delta)

    avg_task_turnaround_hours = round(sum(task_turnaround_hours) / len(task_turnaround_hours), 1) if task_turnaround_hours else None
    min_task_turnaround_hours = round(min(task_turnaround_hours), 1) if task_turnaround_hours else None
    max_task_turnaround_hours = round(max(task_turnaround_hours), 1) if task_turnaround_hours else None

    # Run processing turnaround: time between run creation and completion
    completed_runs = db.scalars(
        select(ProcessingRun).where(
            ProcessingRun.workspace_id == workspace_id,
            ProcessingRun.completed_at.is_not(None)
        )
    ).all()

    run_seconds: list[float] = []
    for r in completed_runs:
        if r.completed_at and r.created_at:
            delta = (r.completed_at - r.created_at).total_seconds()
            if delta >= 0:
                run_seconds.append(delta)

    avg_run_processing_seconds = round(sum(run_seconds) / len(run_seconds), 1) if run_seconds else None

    # 5. Feedback Processing Activity (real daily run counts)
    history_rows = db.execute(
        select(func.date(ProcessingRun.created_at), func.count(ProcessingRun.id))
        .where(ProcessingRun.workspace_id == workspace_id)
        .group_by(func.date(ProcessingRun.created_at))
        .order_by(func.date(ProcessingRun.created_at))
    ).all()

    daily_activity = [{"date": str(day), "runs": int(count)} for day, count in history_rows]

    total_runs = db.scalar(select(func.count(ProcessingRun.id)).where(ProcessingRun.workspace_id == workspace_id)) or 0
    successful_runs = db.scalar(select(func.count(ProcessingRun.id)).where(ProcessingRun.workspace_id == workspace_id, ProcessingRun.status == "completed")) or 0
    failed_runs = db.scalar(select(func.count(ProcessingRun.id)).where(ProcessingRun.workspace_id == workspace_id, ProcessingRun.status == "failed")) or 0

    # 6. Confirmed Client Memories & Knowledge
    memories_retained = db.scalar(
        select(func.count(MemoryOperation.id)).where(
            MemoryOperation.workspace_id == workspace_id,
            MemoryOperation.operation == "retain",
            MemoryOperation.status == "completed"
        )
    ) or 0

    memories_recalled = db.scalar(
        select(func.count(MemoryOperation.id)).where(
            MemoryOperation.workspace_id == workspace_id,
            MemoryOperation.operation == "recall",
            MemoryOperation.status == "completed"
        )
    ) or 0

    # Per-client breakdown
    client_rows = db.scalars(select(Client).where(Client.workspace_id == workspace_id)).all()
    client_memory_breakdown = []
    for c in client_rows:
        retained_count = db.scalar(
            select(func.count(MemoryOperation.id)).where(
                MemoryOperation.client_id == c.id,
                MemoryOperation.operation == "retain",
                MemoryOperation.status == "completed"
            )
        ) or 0
        confirmed_count = db.scalar(
            select(func.count(Feedback.id)).where(
                Feedback.client_id == c.id,
                Feedback.client_confirmed.is_(True)
            )
        ) or 0
        client_memory_breakdown.append({
            "client_id": c.id,
            "client_name": c.name,
            "brand": c.brand,
            "memory_status": c.memory_status,
            "memories_retained": retained_count,
            "confirmed_preferences": confirmed_count,
        })

    # 7. Asset Coverage
    total_assets = db.scalar(select(func.count(Asset.id)).where(Asset.workspace_id == workspace_id)) or 0

    return {
        # Primary KPI counts (matches and extends existing /api/analytics contract)
        "clients": clients_count,
        "active_projects": active_projects,
        "completed_projects": completed_projects,
        "archived_projects": archived_projects,
        "total_projects": total_projects,
        "pending_tasks": pending_tasks,
        "in_progress_tasks": in_progress_tasks,
        "completed_tasks": completed_tasks,
        "blocked_tasks": blocked_tasks,
        "rejected_tasks": rejected_tasks,
        "total_tasks": total_tasks,
        "tasks_completed": completed_tasks,
        "pending_confirmations": pending_tasks,
        "total_assets": total_assets,

        # Task breakdowns
        "task_priority_distribution": priority_counts,
        "task_status_distribution": {
            "pending": pending_tasks,
            "in_progress": in_progress_tasks,
            "completed": completed_tasks,
            "blocked": blocked_tasks,
            "rejected": rejected_tasks,
        },
        "task_category_distribution": category_counts,

        # Feedback & revisions
        "revisions": {
            "total_feedback": total_feedback,
            "editor_corrections": corrections_count,
            "acceptances": acceptances_count,
            "rejections": rejections_count,
            "client_confirmed": client_confirmed_feedback,
            "acceptance_rate_percentage": acceptance_rate,
        },

        # Turnaround indicators
        "turnaround": {
            "avg_task_turnaround_hours": avg_task_turnaround_hours,
            "min_task_turnaround_hours": min_task_turnaround_hours,
            "max_task_turnaround_hours": max_task_turnaround_hours,
            "avg_run_processing_seconds": avg_run_processing_seconds,
            "completed_samples_count": len(task_turnaround_hours),
            "has_turnaround_data": bool(task_turnaround_hours or run_seconds),
        },

        # Activity and processing
        "processing_activity": {
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "failed_runs": failed_runs,
        },
        "activity": daily_activity,

        # Memory & adaptive intelligence
        "memories_retained": memories_retained,
        "memory_retrievals": memories_recalled,
        "client_memories": client_memory_breakdown,
    }
