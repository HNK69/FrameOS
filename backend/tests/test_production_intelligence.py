from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import (
    Asset,
    Client,
    Feedback,
    Membership,
    MemoryOperation,
    ProcessingRun,
    ProductionTask,
    Project,
    Transcript,
    User,
    Workspace,
)
from app.security import hash_password, issue_token


@pytest.fixture
def test_setup(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def test_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(settings, "auth_secret", "test-secret-with-sufficient-entropy-for-tests")
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    app.dependency_overrides[get_db] = test_db

    # Create workspace owner
    db = Session()
    owner = User(email="editor@frameops.test", password_hash=hash_password("editor-password-123"))
    ws = Workspace(name="Creative Agency")
    db.add_all([owner, ws])
    db.flush()
    mem = Membership(user_id=owner.id, workspace_id=ws.id, role="owner")
    db.add(mem)
    db.commit()

    token = issue_token(owner, mem)

    # Create foreign user/workspace for tenant isolation tests
    foreign_user = User(email="foreign@other.test", password_hash=hash_password("foreign-pass-123"))
    foreign_ws = Workspace(name="Foreign Agency")
    db.add_all([foreign_user, foreign_ws])
    db.flush()
    foreign_mem = Membership(user_id=foreign_user.id, workspace_id=foreign_ws.id, role="owner")
    db.add(foreign_mem)
    db.commit()

    foreign_token = issue_token(foreign_user, foreign_mem)
    db.close()

    yield {
        "engine": engine,
        "Session": Session,
        "token": token,
        "foreign_token": foreign_token,
        "workspace_id": ws.id,
        "foreign_workspace_id": foreign_ws.id,
        "owner_id": owner.id,
        "tmp_path": tmp_path,
    }

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_production_task_status_and_priority_management(test_setup):
    Session = test_setup["Session"]
    token = test_setup["token"]
    wid = test_setup["workspace_id"]
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token}"

    db = Session()
    cl = Client(workspace_id=wid, name="Acme Studios", memory_bank_id="bank-1")
    db.add(cl); db.flush()
    proj = Project(workspace_id=wid, client_id=cl.id, name="Commercial Cut")
    db.add(proj); db.flush()
    tr = Transcript(project_id=proj.id, content="Change pace and color grade", created_by=test_setup["owner_id"])
    db.add(tr); db.flush()
    run = ProcessingRun(workspace_id=wid, client_id=cl.id, project_id=proj.id, transcript_id=tr.id, idempotency_key="run-1", status="completed")
    db.add(run); db.flush()

    task1 = ProductionTask(
        workspace_id=wid, client_id=cl.id, project_id=proj.id, run_id=run.id,
        title="Grade warm highlights", category="grading", instruction="Apply warm offset to skin tones",
        resolve_workflow="Color page -> Primaries wheel -> Offset warmth +5", priority="medium",
        source="transcript", evidence="Client noted cold look", confidence=0.88, requires_confirmation=False, status="pending"
    )
    task2 = ProductionTask(
        workspace_id=wid, client_id=cl.id, project_id=proj.id, run_id=run.id,
        title="Sync music drop", category="audio", instruction="Align cut to bass hit at 00:14",
        resolve_workflow="Fairlight -> align audio marker", priority="high",
        source="transcript", evidence="Client feedback on beat", confidence=0.92, requires_confirmation=False, status="pending"
    )
    db.add_all([task1, task2])
    db.commit()
    t1_id, t2_id = task1.id, task2.id
    db.close()

    # 1. List tasks and filter by status
    res = client.get("/api/tasks?status=pending")
    assert res.status_code == 200
    tasks = res.json()
    assert len(tasks) == 2
    assert tasks[0]["client_name"] == "Acme Studios"
    assert tasks[0]["project_name"] == "Commercial Cut"

    # 2. Update task1 status to in_progress and priority to urgent
    res = client.patch(f"/api/tasks/{t1_id}", json={"status": "in_progress", "priority": "urgent"})
    assert res.status_code == 200
    updated = res.json()
    assert updated["status"] == "in_progress"
    assert updated["priority"] == "urgent"

    # 3. Update task2 status to blocked with note
    res = client.patch(f"/api/tasks/{t2_id}", json={"status": "blocked", "correction_note": "Waiting on master audio stem from client"})
    assert res.status_code == 200
    assert res.json()["status"] == "blocked"

    # 4. Filter tasks by in_progress and blocked
    in_prog = client.get("/api/tasks?status=in_progress").json()
    assert len(in_prog) == 1
    assert in_prog[0]["id"] == t1_id

    blocked = client.get("/api/tasks?status=blocked").json()
    assert len(blocked) == 1
    assert blocked[0]["id"] == t2_id


def test_editor_correction_preserves_provenance(test_setup):
    Session = test_setup["Session"]
    token = test_setup["token"]
    wid = test_setup["workspace_id"]
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token}"

    db = Session()
    cl = Client(workspace_id=wid, name="Beta Media", memory_bank_id="bank-2")
    db.add(cl); db.flush()
    proj = Project(workspace_id=wid, client_id=cl.id, name="Hero Video")
    db.add(proj); db.flush()
    tr = Transcript(project_id=proj.id, content="Notes", created_by=test_setup["owner_id"])
    db.add(tr); db.flush()
    run = ProcessingRun(workspace_id=wid, client_id=cl.id, project_id=proj.id, transcript_id=tr.id, idempotency_key="run-2", status="completed")
    db.add(run); db.flush()

    original_instruction = "Use heavy vignette around product"
    task = ProductionTask(
        workspace_id=wid, client_id=cl.id, project_id=proj.id, run_id=run.id,
        title="Product spotlight vignette", category="grading", instruction=original_instruction,
        resolve_workflow="Power window -> linear vignette", priority="medium",
        source="groq-ai", evidence="Client mentioned focus", confidence=0.75, requires_confirmation=True, status="pending"
    )
    db.add(task)
    db.commit()
    t_id = task.id
    db.close()

    # Editor corrects the instruction:
    corrected_instruction = "Client requested soft circular gradient instead of heavy vignette"
    res = client.patch(
        f"/api/tasks/{t_id}",
        json={
            "instruction": corrected_instruction,
            "status": "in_progress",
            "priority": "high",
            "knowledge_type": "reusable_client_knowledge",
            "client_confirmed": True,
        }
    )
    assert res.status_code == 200
    task_res = res.json()

    # Verify task updated
    assert task_res["instruction"] == corrected_instruction
    assert task_res["original_recommendation"] == original_instruction
    assert task_res["is_corrected"] is True
    assert task_res["status"] == "in_progress"
    assert task_res["priority"] == "high"

    # Verify Feedback row stored separately with author and provenance
    db = Session()
    fb = db.scalars(select(Feedback).where(Feedback.task_id == t_id)).first()
    assert fb is not None
    assert fb.original_recommendation == original_instruction
    assert fb.correction == corrected_instruction
    assert fb.author_id == test_setup["owner_id"]
    assert fb.client_confirmed is True
    assert fb.created_at is not None

    # Verify MemoryOperation stored with reusable provenance
    mem_op = db.scalars(select(MemoryOperation).where(MemoryOperation.client_id == cl.id)).first()
    assert mem_op is not None
    assert mem_op.provenance in ("reusable_client_knowledge", "client_confirmed")
    db.close()

    # Verify task details endpoint returns audit history
    detail_res = client.get(f"/api/tasks/{t_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert len(detail["feedback_history"]) >= 1
    assert detail["feedback_history"][0]["original_recommendation"] == original_instruction
    assert detail["feedback_history"][0]["correction"] == corrected_instruction


def test_asset_intelligence_evidence_based_tracking(test_setup):
    Session = test_setup["Session"]
    token = test_setup["token"]
    wid = test_setup["workspace_id"]
    tmp_path = test_setup["tmp_path"]
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token}"

    db = Session()
    cl = Client(workspace_id=wid, name="Gamma Agency", memory_bank_id="bank-3")
    db.add(cl); db.flush()
    proj = Project(workspace_id=wid, client_id=cl.id, name="Reel")
    db.add(proj); db.flush()

    # 1. Create a physical file on disk (Evidence Present)
    storage_folder = tmp_path / "uploads" / str(wid) / str(proj.id)
    storage_folder.mkdir(parents=True, exist_ok=True)
    real_logo = storage_folder / "logo_white.svg"
    real_logo.write_text("<svg>Logo</svg>")

    asset_present = Asset(
        workspace_id=wid, client_id=cl.id, project_id=proj.id,
        filename="logo_white.svg", category="logo", content_type="image/svg+xml",
        size_bytes=real_logo.stat().st_size, storage_key=str(real_logo), created_by=test_setup["owner_id"]
    )

    # 2. Create an asset record whose file is NOT on disk (Evidence Missing/Unverified)
    phantom_file = storage_folder / "missing_footage.mov"
    asset_missing = Asset(
        workspace_id=wid, client_id=cl.id, project_id=proj.id,
        filename="missing_footage.mov", category="footage", content_type="video/quicktime",
        size_bytes=1048576, storage_key=str(phantom_file), created_by=test_setup["owner_id"]
    )

    db.add_all([asset_present, asset_missing])
    db.commit()
    proj_id = proj.id
    db.close()

    # Query asset intelligence
    res = client.get(f"/api/projects/{proj_id}/asset-intelligence")
    assert res.status_code == 200
    intel = res.json()

    assert intel["project_id"] == proj_id
    summary = intel["summary"]
    assert summary["total_uploaded"] == 2
    assert summary["present_count"] == 1
    assert summary["missing_count"] == 1

    # Check verified present asset
    present_item = next(a for a in intel["uploaded_assets"] if a["filename"] == "logo_white.svg")
    assert present_item["status"] == "Present"
    assert present_item["exists_on_disk"] is True
    assert present_item["category"] == "logo"
    assert "Verified in secure storage" in present_item["evidence"]

    # Check missing asset (physical file was not on disk)
    missing_item = next(a for a in intel["uploaded_assets"] if a["filename"] == "missing_footage.mov")
    assert missing_item["status"] == "Missing"
    assert missing_item["exists_on_disk"] is False
    assert "not found in storage" in missing_item["evidence"]


def test_production_analytics_empty_and_populated_states(test_setup):
    Session = test_setup["Session"]
    token = test_setup["token"]
    wid = test_setup["workspace_id"]
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token}"

    # 1. Empty state verification: no data fabricated!
    res = client.get("/api/production-analytics")
    assert res.status_code == 200
    empty_analytics = res.json()

    assert empty_analytics["clients"] == 0
    assert empty_analytics["active_projects"] == 0
    assert empty_analytics["pending_tasks"] == 0
    assert empty_analytics["completed_tasks"] == 0
    assert empty_analytics["turnaround"]["avg_task_turnaround_hours"] is None
    assert empty_analytics["turnaround"]["has_turnaround_data"] is False
    assert empty_analytics["activity"] == []

    # 2. Populate real records and verify calculations
    db = Session()
    cl = Client(workspace_id=wid, name="Delta Brand", memory_bank_id="bank-4")
    db.add(cl); db.flush()
    p1 = Project(workspace_id=wid, client_id=cl.id, name="Project 1", status="active")
    p2 = Project(workspace_id=wid, client_id=cl.id, name="Project 2", status="completed")
    db.add_all([p1, p2]); db.flush()

    tr = Transcript(project_id=p1.id, content="Content", created_by=test_setup["owner_id"])
    db.add(tr); db.flush()
    run = ProcessingRun(
        workspace_id=wid, client_id=cl.id, project_id=p1.id, transcript_id=tr.id,
        idempotency_key="run-3", status="completed",
        created_at=datetime.now(UTC) - timedelta(seconds=120),
        completed_at=datetime.now(UTC)
    )
    db.add(run); db.flush()

    t_created = datetime.now(UTC) - timedelta(hours=4)
    t1 = ProductionTask(
        workspace_id=wid, client_id=cl.id, project_id=p1.id, run_id=run.id,
        title="Cut audio", category="audio", instruction="Trim pause", resolve_workflow="Cut",
        priority="high", source="ai", evidence="test", confidence=0.9, requires_confirmation=False,
        status="completed", created_at=t_created
    )
    t2 = ProductionTask(
        workspace_id=wid, client_id=cl.id, project_id=p1.id, run_id=run.id,
        title="Grade scene", category="grading", instruction="Add contrast", resolve_workflow="Curve",
        priority="urgent", source="ai", evidence="test", confidence=0.85, requires_confirmation=False,
        status="pending", created_at=t_created
    )
    db.add_all([t1, t2]); db.flush()

    # Feedback completed 2 hours later
    f_time = t_created + timedelta(hours=2)
    fb = Feedback(
        workspace_id=wid, client_id=cl.id, project_id=p1.id, task_id=t1.id, author_id=test_setup["owner_id"],
        action="accept", original_recommendation=t1.instruction, correction="", client_confirmed=True,
        created_at=f_time
    )
    db.add(fb); db.commit()
    db.close()

    # Query analytics again
    res = client.get("/api/production-analytics")
    assert res.status_code == 200
    populated = res.json()

    assert populated["clients"] == 1
    assert populated["active_projects"] == 1
    assert populated["completed_projects"] == 1
    assert populated["total_projects"] == 2
    assert populated["pending_tasks"] == 1
    assert populated["completed_tasks"] == 1
    assert populated["task_priority_distribution"]["urgent"] == 1
    assert populated["task_priority_distribution"]["high"] == 1
    assert populated["revisions"]["total_feedback"] == 1
    assert populated["revisions"]["client_confirmed"] == 1

    # Turnaround should accurately report ~2.0 hours
    turnaround = populated["turnaround"]
    assert turnaround["has_turnaround_data"] is True
    assert turnaround["avg_task_turnaround_hours"] == 2.0
    assert turnaround["completed_samples_count"] == 1


def test_adaptive_intelligence_distinguishes_decision_types(test_setup):
    Session = test_setup["Session"]
    token = test_setup["token"]
    wid = test_setup["workspace_id"]
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token}"

    db = Session()
    cl = Client(workspace_id=wid, name="Epsilon Agency", memory_bank_id="bank-5")
    db.add(cl); db.flush()
    proj = Project(workspace_id=wid, client_id=cl.id, name="Brand Launch", status="active")
    db.add(proj); db.flush()
    tr = Transcript(project_id=proj.id, content="Content", created_by=test_setup["owner_id"])
    db.add(tr); db.flush()
    run = ProcessingRun(workspace_id=wid, client_id=cl.id, project_id=proj.id, transcript_id=tr.id, idempotency_key="run-5", status="completed")
    db.add(run); db.flush()

    # AI recommendation
    t_ai = ProductionTask(
        workspace_id=wid, client_id=cl.id, project_id=proj.id, run_id=run.id,
        title="Subtle grade", category="grading", instruction="Apply Rec709 LUT", resolve_workflow="LUT",
        priority="low", source="groq-ai", evidence="standard lut", confidence=0.9, requires_confirmation=False, status="pending"
    )
    db.add(t_ai); db.flush()

    # Editor correction
    fb_corr = Feedback(
        workspace_id=wid, client_id=cl.id, project_id=proj.id, task_id=t_ai.id, author_id=test_setup["owner_id"],
        action="correct", original_recommendation="Apply Rec709 LUT", correction="Use custom ACES color transform instead",
        client_confirmed=False
    )
    # Client-confirmed preference
    fb_conf = Feedback(
        workspace_id=wid, client_id=cl.id, project_id=proj.id, task_id=t_ai.id, author_id=test_setup["owner_id"],
        action="accept", original_recommendation="Always include 1.5s brand logo bumper at head", correction="",
        client_confirmed=True
    )
    # Reusable client knowledge
    m_reusable = MemoryOperation(
        workspace_id=wid, client_id=cl.id, project_id=proj.id, operation="retain", status="completed",
        idempotency_key="op-reusable", provenance="reusable_client_knowledge", details="Client mandates 24fps export"
    )
    # Project-specific decision
    m_proj = MemoryOperation(
        workspace_id=wid, client_id=cl.id, project_id=proj.id, operation="retain", status="completed",
        idempotency_key="op-proj", provenance="project_specific", details="Omit callout text for teaser only"
    )

    db.add_all([fb_corr, fb_conf, m_reusable, m_proj])
    db.commit()
    cl_id = cl.id
    db.close()

    res = client.get(f"/api/clients/{cl_id}/adaptive-knowledge")
    assert res.status_code == 200
    data = res.json()

    counts = data["counts"]
    assert counts["ai_recommendations"] == 1
    assert counts["editor_corrections"] == 1
    assert counts["client_confirmed_preferences"] == 1
    assert counts["reusable_client_knowledge"] == 1
    assert counts["project_specific_decisions"] == 1

    # Test direct POST to adaptive knowledge
    post_res = client.post(
        f"/api/clients/{cl_id}/adaptive-knowledge",
        json={
            "content": "Client prefers clean lower thirds with 20% opacity backing plate",
            "knowledge_type": "reusable_client_knowledge",
            "client_confirmed": True,
        }
    )
    assert post_res.status_code == 201
    assert post_res.json()["knowledge_type"] == "client_confirmed"


def test_tenant_workspace_isolation(test_setup):
    token = test_setup["token"]
    foreign_token = test_setup["foreign_token"]

    owner_client = TestClient(app)
    owner_client.headers["Authorization"] = f"Bearer {token}"

    foreign_client = TestClient(app)
    foreign_client.headers["Authorization"] = f"Bearer {foreign_token}"

    # Owner creates client, project, and task
    c_res = owner_client.post("/api/clients", json={"name": "Owner Client", "brand": "Brand"})
    c_id = c_res.json()["id"]

    p_res = owner_client.post("/api/projects", json={"client_id": c_id, "name": "Owner Project"})
    p_id = p_res.json()["id"]

    # Foreign client cannot access client, project, or asset-intelligence
    assert foreign_client.get(f"/api/clients/{c_id}").status_code == 404
    assert foreign_client.get(f"/api/projects/{p_id}").status_code == 404
    assert foreign_client.get(f"/api/projects/{p_id}/asset-intelligence").status_code == 404
    assert foreign_client.get(f"/api/clients/{c_id}/adaptive-knowledge").status_code == 404
    assert foreign_client.get("/api/tasks").json() == []
