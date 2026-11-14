import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import ExtractedItem, Membership, MemoryOperation, ProcessingRun, User, Workspace
from app.schemas import ClientInput, ExtractionItem, ExtractionResult, FeedbackInput, ProcessInput, ProjectInput, SynthesisResult
from app.security import hash_password, issue_token


def test_client_requires_real_name():
    with pytest.raises(ValidationError):
        ClientInput(name=" ")


def test_transcript_has_size_and_minimum_validation():
    with pytest.raises(ValidationError):
        ProcessInput(project_id=1, transcript="tiny")
    with pytest.raises(ValidationError):
        ProcessInput(project_id=1, transcript="x" * 100001)


def test_feedback_requires_known_action_and_confirmation_is_explicit():
    with pytest.raises(ValidationError):
        FeedbackInput(action="auto_confirm")
    item = FeedbackInput(action="correct", correction="Use a slower reveal", client_confirmed=False)
    assert item.client_confirmed is False


def test_project_status_is_bounded():
    with pytest.raises(ValidationError):
        ProjectInput(client_id=1, name="Campaign", status="imaginary")
    for valid_status in ("active", "in_review", "completed", "archived"):
        proj = ProjectInput(client_id=1, name="Campaign", status=valid_status)
        assert proj.status == valid_status


def test_synthesized_task_requires_resolve_and_confirmation_fields():
    with pytest.raises(ValidationError):
        SynthesisResult.model_validate({"tasks": [{"title": "Color", "instruction": "Make it warmer"}]})


def test_auth_crud_persistence_and_workspace_isolation(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def test_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(settings, "auth_secret", "isolated-test-secret-with-sufficient-entropy")
    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as owner:
            setup = owner.post("/api/auth/setup", json={"email": "owner@example.com", "password": "a-long-test-password", "workspace_name": "Test Workspace"})
            assert setup.status_code == 200
            created = owner.post("/api/clients", json={"name": "Actual UI Client", "brand": "Brand"})
            assert created.status_code == 201
            client_id = created.json()["id"]
            project = owner.post("/api/projects", json={"client_id": client_id, "name": "Launch film"})
            assert project.status_code == 201
            assert owner.get("/api/clients").json()[0]["projects_count"] == 1

            db = Session()
            other = User(email="other@example.com", password_hash=hash_password("another-test-password"))
            foreign_workspace = Workspace(name="Separate Workspace")
            db.add_all([other, foreign_workspace]); db.flush()
            membership = Membership(user_id=other.id, workspace_id=foreign_workspace.id, role="owner")
            db.add(membership); db.commit()
            token = issue_token(other, membership)
            db.close()

            isolated = TestClient(app)
            isolated.headers["Authorization"] = f"Bearer {token}"
            assert isolated.get("/api/clients").json() == []
            assert isolated.get(f"/api/clients/{client_id}").status_code == 404
            assert isolated.get(f"/api/projects/{project.json()['id']}").status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_failed_openclaw_synthesis_keeps_extractions_and_project_history(monkeypatch):
    """External services are isolated here; this guards DB/API persistence, not integration availability."""
    from app.services import groq, hindsight, openclaw

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def test_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    async def extracted(_transcript):
        return ExtractionResult(requests=[ExtractionItem(
            description="Keep the product name visible through the end card",
            category="creative", source_quote="Keep the product name visible through the end card",
            classification="explicit", confidence=0.96, requires_confirmation=False,
        )])

    async def recalled(_bank_id, _query):
        return {"results": []}

    async def synthesis_fails(**_kwargs):
        raise RuntimeError("")

    monkeypatch.setattr(settings, "auth_secret", "isolated-test-secret-with-sufficient-entropy")
    monkeypatch.setattr(settings, "hindsight_api_url", "")
    monkeypatch.setattr(groq, "extract_feedback", extracted)
    monkeypatch.setattr(hindsight, "recall", recalled)
    monkeypatch.setattr(openclaw, "synthesize", synthesis_fails)
    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as owner:
            assert owner.post("/api/auth/setup", json={
                "email": "persist@example.com", "password": "a-long-test-password", "workspace_name": "Persistence Test",
            }).status_code == 200
            client = owner.post("/api/clients", json={"name": "Test client"})
            project = owner.post("/api/projects", json={
                "client_id": client.json()["id"], "name": "Test edit",
            })
            project_id = project.json()["id"]
            response = owner.post("/api/process-transcript", headers={"Idempotency-Key": "failed-synthesis-regression"}, json={
                "project_id": project_id, "transcript": "Keep the product name visible through the end card.",
            })
            assert response.status_code == 502

            history = owner.get(f"/api/projects/{project_id}")
            assert history.status_code == 200
            run = history.json()["runs"][0]
            assert run["status"] == "failed"
            assert run["error"] == "RuntimeError"
            assert run["extractions"][0]["description"] == "Keep the product name visible through the end card"
            assert run["tasks"] == []
            persisted = owner.get(f"/api/runs/{run['id']}").json()
            assert persisted["extractions"] == run["extractions"]

            db = Session()
            try:
                assert db.query(ProcessingRun).filter_by(id=run["id"], project_id=project_id).count() == 1
                assert db.query(ExtractedItem).filter_by(run_id=run["id"]).count() == 1
            finally:
                db.close()
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_failed_hindsight_recall_is_recorded_without_losing_extraction(monkeypatch):
    """A provider failure must leave an auditable failed recall operation and the prior extraction commit."""
    from app.services import groq, hindsight

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def test_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    async def extracted(_transcript):
        return ExtractionResult(requests=[ExtractionItem(
            description="Use the approved brand color",
            category="brand", source_quote="Use the approved brand color",
            classification="explicit", confidence=0.9, requires_confirmation=False,
        )])

    async def recall_fails(_bank_id, _query):
        raise groq.ServiceUnavailable("Hindsight recall failed: ConnectError")

    from app.services import openclaw

    async def mock_execute_cli(*args, **kwargs):
        class MockProc:
            returncode = 1
            stdout = b""
            stderr = b"OpenClaw gateway unavailable in isolated test"
        return MockProc()

    monkeypatch.setattr(settings, "auth_secret", "isolated-test-secret-with-sufficient-entropy")
    monkeypatch.setattr(settings, "hindsight_api_url", "")
    monkeypatch.setattr(groq, "extract_feedback", extracted)
    monkeypatch.setattr(hindsight, "recall", recall_fails)
    monkeypatch.setattr(openclaw, "_execute_cli", mock_execute_cli)
    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as owner:
            assert owner.post("/api/auth/setup", json={
                "email": "recall@example.com", "password": "a-long-test-password", "workspace_name": "Recall Test",
            }).status_code == 200
            client = owner.post("/api/clients", json={"name": "Test client"}).json()
            project_id = owner.post("/api/projects", json={"client_id": client["id"], "name": "Recall failure"}).json()["id"]
            response = owner.post("/api/process-transcript", json={
                "project_id": project_id, "transcript": "Use the approved brand color in the title card.",
            })
            assert response.status_code == 503
            run = owner.get(f"/api/projects/{project_id}").json()["runs"][0]
            assert run["status"] == "failed"
            assert run["extractions"][0]["description"] == "Use the approved brand color"
            assert run["memory_operations"][0]["operation"] == "recall"
            assert run["memory_operations"][0]["status"] in ("failed", "degraded")
            assert "ConnectError" in run["memory_operations"][0]["details"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_hindsight_memory_api_reports_provider_connectivity_as_503(monkeypatch):
    from app.services import groq, hindsight

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def test_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    async def memory_call_fails(*_args, **_kwargs):
        raise groq.ServiceUnavailable("Hindsight list request failed: ConnectError")

    monkeypatch.setattr(settings, "auth_secret", "isolated-test-secret-with-sufficient-entropy")
    monkeypatch.setattr(settings, "hindsight_api_url", "https://configured-for-test.invalid")
    monkeypatch.setattr(settings, "hindsight_api_token", "unit-test-token")
    monkeypatch.setattr(hindsight, "call_memory", memory_call_fails)
    monkeypatch.setattr(hindsight, "configured", lambda: True)
    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as owner:
            assert owner.post("/api/auth/setup", json={
                "email": "memory-api@example.com", "password": "a-long-test-password", "workspace_name": "Memory API Test",
            }).status_code == 200
            client_id = owner.post("/api/clients", json={"name": "Test client"}).json()["id"]
            response = owner.get(f"/api/clients/{client_id}/memories")
            assert response.status_code == 503
            assert response.json()["detail"] == "Hindsight list request failed: ConnectError"
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_openclaw_memory_evidence_supports_both_list_and_dict():
    from app.services.openclaw import _memory_evidence

    # Degraded recall returns [] or {"results": []} or {"memories": []}
    assert _memory_evidence([]) == []
    assert _memory_evidence({}) == []
    assert _memory_evidence({"results": []}) == []
    assert _memory_evidence({"memories": []}) == []
    assert _memory_evidence(None) == []

    # Valid list of dicts
    items = [{"text": "Pacing must be under 30s", "context": "brand guidelines", "document_id": "doc-1"}]
    evidence = _memory_evidence(items)
    assert len(evidence) == 1
    assert evidence[0]["evidence"] == "Pacing must be under 30s"
    assert evidence[0]["provenance"] == "brand guidelines"
    assert evidence[0]["source"] == "doc-1"

    # Valid dict results
    dict_mem = {"results": [{"text": "Color scheme: navy blue", "tags": ["brand"]}]}
    evidence_dict = _memory_evidence(dict_mem)
    assert len(evidence_dict) == 1
    assert evidence_dict[0]["evidence"] == "Color scheme: navy blue"
