import pytest
from app.services.groq import chunk_transcript_tokens
from app.models import Client, ClientFeedback, ProductionTask, User, Workspace
from app.security import hash_password, issue_token
from app.db import Base, get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.config import settings


def test_chunk_transcript_tokens_short_text():
    short_text = "This is a brief creative feedback note under 4000 tokens."
    chunks = chunk_transcript_tokens(short_text, max_tokens=4000, overlap_tokens=200)
    assert len(chunks) == 1
    assert chunks[0] == short_text


def test_chunk_transcript_tokens_long_text_sliding_window():
    # Generate long transcript exceeding 4,000 tokens (~16,000 characters)
    paragraphs = [f"Paragraph {i}: This is detailed feedback on scene {i} with specific pacing notes." for i in range(400)]
    long_text = "\n\n".join(paragraphs)
    assert len(long_text) > 16000

    chunks = chunk_transcript_tokens(long_text, max_tokens=1000, overlap_tokens=100)
    assert len(chunks) > 1
    # Verify each chunk is <= max_tokens * 4 chars approximately
    for chunk in chunks:
        assert len(chunk) <= 1000 * 4 + 200


def test_feedback_conversion_to_production_task_idempotency(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def test_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(settings, "auth_secret", "test-secret-with-high-entropy-123456789")
    app.dependency_overrides[get_db] = test_db

    db = Session()
    user = User(email="editor@agency.com", password_hash=hash_password("pw-1234"))
    ws = Workspace(name="Test Agency")
    db.add_all([user, ws])
    db.flush()

    from app.models import Membership, Project
    member = Membership(workspace_id=ws.id, user_id=user.id, role="owner")
    db.add(member)

    client = Client(workspace_id=ws.id, name="Test Brand", brand="Brand", industry="Media", memory_bank_id="bank-test-123")
    db.add(client)
    db.flush()

    project = Project(workspace_id=ws.id, client_id=client.id, name="Commercial Cut", status="active")
    db.add(project)
    db.flush()

    # Create delivered client feedback
    feedback = ClientFeedback(
        workspace_id=ws.id,
        client_id=client.id,
        project_id=project.id,
        submitted_by=user.id,
        idempotency_key="fb-idemp-12345",
        source_type="text",
        original_text="Please warm up the color balance in the interior night scene.",
        status="delivered",
        stage="delivered",
    )
    db.add(feedback)
    db.commit()
    fb_id = feedback.id
    token = issue_token(user, member)
    db.close()

    api_client = TestClient(app)
    api_client.headers["Authorization"] = f"Bearer {token}"

    # 1. First conversion
    res1 = api_client.post(f"/api/agency/feedback/{fb_id}/convert-task")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["already_converted"] is False
    task_id = data1["task_id"]

    # Verify task in DB
    with Session() as s:
        task = s.get(ProductionTask, task_id)
        assert task is not None
        assert task.source == "client_feedback"
        assert f"feedback_id:{fb_id}" in task.evidence
        assert task.priority == "high"

    # 2. Second conversion (repeated click) -> must be idempotent
    res2 = api_client.post(f"/api/agency/feedback/{fb_id}/convert-task")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["already_converted"] is True
    assert data2["task_id"] == task_id

    # Verify no duplicate task created
    with Session() as s:
        tasks = s.scalars(select(ProductionTask).where(ProductionTask.project_id == project.id)).all()
        assert len(tasks) == 1

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(engine)
    engine.dispose()
