from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import Membership, User, Workspace
from app.routers.feedback import _audio_signature_valid
from app.schemas import ExtractionResult
from app.security import hash_password, issue_token
from app.services.groq import ServiceUnavailable


def test_audio_signatures_reject_mismatched_content():
    assert _audio_signature_valid(".wav", b"RIFF\x00\x00\x00\x00WAVEdata")
    assert not _audio_signature_valid(".wav", b"not an audio file")
    assert _audio_signature_valid(".flac", b"fLaC\x00")


def test_feedback_confirmation_delivery_and_tenant_isolation(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with Session() as db:
            yield db

    extraction_calls = 0

    async def extract(text):
        nonlocal extraction_calls
        extraction_calls += 1
        if extraction_calls == 1:
            raise ServiceUnavailable("Temporary extraction failure")
        return ExtractionResult(summary="Use the approved blue brand color.", requests=[])

    monkeypatch.setattr(settings, "auth_secret", "feedback-test-secret-sufficient-entropy")
    monkeypatch.setattr("app.routers.feedback.groq.extract_feedback", extract)
    monkeypatch.setattr("app.routers.feedback.SessionLocal", Session)
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as owner:
            owner.post(
                "/api/auth/setup",
                json={
                    "email": "feedback@example.com",
                    "password": "a-long-test-password",
                    "workspace_name": "Feedback workspace",
                },
            ).raise_for_status()
            client = owner.post("/api/clients", json={"name": "Client"}).json()
            project = owner.post(
                "/api/projects", json={"client_id": client["id"], "name": "Film"}
            ).json()
            unsupported_audio = owner.post(
                f"/api/feedback/audio?project_id={project['id']}",
                files={"file": ("voice.wav", b"not audio", "audio/wav")},
            )
            assert unsupported_audio.status_code == 415
            monkeypatch.setattr(settings, "max_upload_bytes", 4)
            oversized_audio = owner.post(
                f"/api/feedback/audio?project_id={project['id']}",
                files={"file": ("voice.wav", b"RIFF1234WAVE", "audio/wav")},
            )
            assert oversized_audio.status_code == 413
            monkeypatch.setattr(settings, "max_upload_bytes", 25 * 1024 * 1024)
            invalid = owner.post(
                "/api/feedback", json={"project_id": project["id"], "text": "          "}
            )
            assert invalid.status_code == 422
            response = owner.post(
                "/api/feedback",
                headers={"Idempotency-Key": "submission-1"},
                json={
                    "project_id": project["id"],
                    "text": "Please use the approved blue brand color.",
                },
            )
            assert response.status_code == 202
            feedback = response.json()
            duplicate = owner.post(
                "/api/feedback",
                headers={"Idempotency-Key": "submission-1"},
                json={
                    "project_id": project["id"],
                    "text": "Please use the approved blue brand color.",
                },
            )
            assert duplicate.json()["id"] == feedback["id"]
            feedback = owner.get(f"/api/feedback/{feedback['id']}").json()
            assert feedback["status"] == "failed"
            assert feedback["attempt_count"] == 1
            retried = owner.post(f"/api/feedback/{feedback['id']}/retry")
            assert retried.status_code == 202
            feedback = owner.get(f"/api/feedback/{feedback['id']}").json()
            assert feedback["status"] == "awaiting_confirmation"
            assert feedback["attempt_count"] == 2
            assert feedback["transcript"] == "Please use the approved blue brand color."
            assert feedback["transcript_provenance"]["source"] == "text"
            invalid_review = owner.patch(
                f"/api/feedback/{feedback['id']}/confirmation", json={"summary": "     "}
            )
            assert invalid_review.status_code == 422
            approved = owner.patch(
                f"/api/feedback/{feedback['id']}/confirmation",
                json={"summary": "Use the approved blue brand color."},
            )
            assert approved.json()["status"] == "confirmed"
            assert len(owner.get("/api/agency/feedback").json()) == 1
            delivered = owner.post(f"/api/agency/feedback/{feedback['id']}/deliver")
            assert delivered.json()["status"] == "delivered"

            db = Session()
            user, workspace = (
                User(
                    email="other-feedback@example.com",
                    password_hash=hash_password("another-long-password"),
                ),
                Workspace(name="Other"),
            )
            db.add_all([user, workspace])
            db.flush()
            member = Membership(user_id=user.id, workspace_id=workspace.id, role="owner")
            db.add(member)
            db.commit()
            token = issue_token(user, member)
            db.close()
            outsider = TestClient(app)
            outsider.headers["Authorization"] = f"Bearer {token}"
            assert outsider.get(f"/api/feedback/{feedback['id']}").status_code == 404
            assert (
                outsider.post(f"/api/agency/feedback/{feedback['id']}/deliver").status_code == 404
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        engine.dispose()
