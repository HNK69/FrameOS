from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import Membership, User, Workspace
from app.schemas import ExtractionResult
from app.security import hash_password, issue_token


def test_feedback_confirmation_delivery_and_tenant_isolation(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with Session() as db:
            yield db

    async def extract(text):
        return ExtractionResult(summary="Use the approved blue brand color.", requests=[])

    monkeypatch.setattr(settings, "auth_secret", "feedback-test-secret-sufficient-entropy")
    monkeypatch.setattr("app.routers.feedback.groq.extract_feedback", extract)
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as owner:
            owner.post("/api/auth/setup", json={"email": "feedback@example.com",
                "password": "a-long-test-password", "workspace_name": "Feedback workspace"}).raise_for_status()
            client = owner.post("/api/clients", json={"name": "Client"}).json()
            project = owner.post("/api/projects", json={"client_id": client["id"], "name": "Film"}).json()
            response = owner.post("/api/feedback", headers={"Idempotency-Key": "submission-1"},
                json={"project_id": project["id"], "text": "Please use the approved blue brand color."})
            assert response.status_code == 202
            feedback = response.json()
            feedback = owner.get(f"/api/feedback/{feedback['id']}").json()
            assert feedback["status"] == "awaiting_confirmation"
            assert feedback["transcript"] == "Please use the approved blue brand color."
            assert feedback["transcript_provenance"]["source"] == "text"
            approved = owner.patch(f"/api/feedback/{feedback['id']}/confirmation",
                json={"summary": "Use the approved blue brand color."})
            assert approved.json()["status"] == "confirmed"
            assert len(owner.get("/api/agency/feedback").json()) == 1
            delivered = owner.post(f"/api/agency/feedback/{feedback['id']}/deliver")
            assert delivered.json()["status"] == "delivered"

            db = Session()
            user, workspace = User(email="other-feedback@example.com",
                password_hash=hash_password("another-long-password")), Workspace(name="Other")
            db.add_all([user, workspace]); db.flush()
            member = Membership(user_id=user.id, workspace_id=workspace.id, role="owner")
            db.add(member); db.commit()
            token = issue_token(user, member)
            db.close()
            outsider = TestClient(app)
            outsider.headers["Authorization"] = f"Bearer {token}"
            assert outsider.get(f"/api/feedback/{feedback['id']}").status_code == 404
            assert outsider.post(f"/api/agency/feedback/{feedback['id']}/deliver").status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        engine.dispose()
