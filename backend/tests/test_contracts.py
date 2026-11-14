import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import Membership, User, Workspace
from app.schemas import ClientInput, FeedbackInput, ProcessInput, ProjectInput, SynthesisResult
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
