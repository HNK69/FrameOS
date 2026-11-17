"""E2E Test Fixtures and Harness for FRAMEOPS.

Provides:
1. Autouse external service mocks (Groq, Hindsight, OpenClaw) unless FRAMEOPS_LIVE_SERVICES=1.
2. Reusable persona fixtures (agency, client, foreign agency, foreign client) with both cookie and Bearer header auth.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

import app.models as models
from app.config import settings
from app.main import app
from app.models import Client, Membership, User, Workspace
from app.security import hash_password, issue_token
from .mocks import (
    MockGroqService,
    MockHindsightService,
    MockOpenClawService,
)


# ==============================================================================
# External Service Mocks Fixtures
# ==============================================================================

@pytest.fixture(scope="function")
def mock_groq() -> MockGroqService:
    service = MockGroqService()
    service.reset()
    return service


@pytest.fixture(scope="function")
def mock_hindsight() -> MockHindsightService:
    service = MockHindsightService()
    service.reset()
    return service


@pytest.fixture(scope="function")
def mock_openclaw() -> MockOpenClawService:
    service = MockOpenClawService()
    service.reset()
    return service


@pytest.fixture(scope="function", autouse=True)
def mock_external_services(
    monkeypatch: pytest.MonkeyPatch,
    mock_groq: MockGroqService,
    mock_hindsight: MockHindsightService,
    mock_openclaw: MockOpenClawService,
) -> Generator[dict[str, Any], None, None]:
    """Autouse fixture installing deterministic offline mocks for Groq, Hindsight, and OpenClaw."""
    live_mode = os.getenv("FRAMEOPS_LIVE_SERVICES", "0").lower() in ("1", "true")
    if live_mode:
        yield {"mode": "live"}
        return

    # Mock Groq
    monkeypatch.setattr("app.services.groq.extract_feedback", mock_groq.extract_feedback)
    monkeypatch.setattr("app.services.groq.transcribe_audio", mock_groq.transcribe_audio)
    monkeypatch.setattr(settings, "groq_api_key", "mock-groq-api-key")
    monkeypatch.setattr(settings, "groq_model", "whisper-large-v3-turbo")

    # Mock Hindsight
    monkeypatch.setattr("app.services.hindsight.configured", mock_hindsight.configured)
    monkeypatch.setattr("app.services.hindsight.call_memory", mock_hindsight.call_memory)
    monkeypatch.setattr("app.services.hindsight.retain", mock_hindsight.retain)
    monkeypatch.setattr("app.services.hindsight.recall", mock_hindsight.recall)
    monkeypatch.setattr("app.services.hindsight.retain_and_verify", mock_hindsight.retain_and_verify)
    monkeypatch.setattr("app.services.hindsight.reflect", mock_hindsight.reflect)
    monkeypatch.setattr("app.services.hindsight.ensure_bank", mock_hindsight.ensure_bank)
    monkeypatch.setattr("app.services.hindsight.delete_bank", mock_hindsight.delete_bank)
    monkeypatch.setattr(settings, "hindsight_api_url", "https://mock.hindsight.local")
    monkeypatch.setattr(settings, "hindsight_api_token", "mock-hindsight-token")

    # Mock OpenClaw
    monkeypatch.setattr("app.services.openclaw.synthesize", mock_openclaw.synthesize)
    monkeypatch.setattr(settings, "openclaw_auth_token", "mock-openclaw-token")
    monkeypatch.setattr(settings, "openclaw_agent_id", "main")

    yield {
        "mode": "offline_mock",
        "groq": mock_groq,
        "hindsight": mock_hindsight,
        "openclaw": mock_openclaw,
    }


# ==============================================================================
# Helper to Issue Multi-Tenant Compatible Client Tokens
# ==============================================================================

def _issue_test_client_token(client: Client, user: User | None = None) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id) if user else f"client:{client.id}",
        "user_id": user.id if user else None,
        "client_id": client.id,
        "workspace_id": client.workspace_id,
        "role": "client",
        "iat": now,
        "exp": now + timedelta(days=30),
    }
    return jwt.encode(payload, settings.auth_secret, algorithm="HS256")


# ==============================================================================
# Multi-Tenant Persona Fixtures
# ==============================================================================

@pytest.fixture
def agency_setup(isolated_db) -> dict[str, Any]:
    """Creates a standard Agency Owner, Workspace, and Membership."""
    Session = isolated_db
    with Session() as db:
        owner = User(
            email="agency_owner@frameops.test",
            password_hash=hash_password("owner-secret-pass-123"),
        )
        if hasattr(owner, "role"):
            setattr(owner, "role", "agency_owner")
        if hasattr(owner, "full_name"):
            setattr(owner, "full_name", "Acme Agency Owner")

        ws = Workspace(name="Acme Production Studio")
        db.add_all([owner, ws])
        db.flush()

        mem = Membership(user_id=owner.id, workspace_id=ws.id, role="owner")
        db.add(mem)

        # Conditionally create AgencyProfile if model exists
        profile = None
        if hasattr(models, "AgencyProfile"):
            AgencyProfileClass = getattr(models, "AgencyProfile")
            profile = AgencyProfileClass(
                workspace_id=ws.id,
                tagline="High-end video production",
                description="Specialized in commercial and cinematic editing",
                specializations='["cinematic", "commercial"]',
                services='["editing", "color_grading"]',
                portfolio='[]',
                contact_email="contact@acme.test",
                is_published=True,
            )
            db.add(profile)

        db.commit()

        token = issue_token(owner, mem)
        owner_id = owner.id
        workspace_id = ws.id

    return {
        "owner_id": owner_id,
        "workspace_id": workspace_id,
        "email": "agency_owner@frameops.test",
        "token": token,
        "cookies": {"frameops_session": token},
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
def agency_client(agency_setup: dict[str, Any]) -> Generator[TestClient, None, None]:
    """TestClient pre-authenticated as the primary Agency Owner."""
    with TestClient(app) as client:
        client.cookies.set("frameops_session", agency_setup["token"])
        client.headers["Authorization"] = f"Bearer {agency_setup['token']}"
        yield client


@pytest.fixture
def foreign_agency_setup(isolated_db) -> dict[str, Any]:
    """Creates an unrelated Agency Owner and Workspace for cross-tenant isolation testing."""
    Session = isolated_db
    with Session() as db:
        owner = User(
            email="foreign_agency@unrelated.test",
            password_hash=hash_password("foreign-owner-pass-123"),
        )
        if hasattr(owner, "role"):
            setattr(owner, "role", "agency_owner")
        if hasattr(owner, "full_name"):
            setattr(owner, "full_name", "Foreign Agency Owner")

        ws = Workspace(name="Foreign Production House")
        db.add_all([owner, ws])
        db.flush()

        mem = Membership(user_id=owner.id, workspace_id=ws.id, role="owner")
        db.add(mem)

        if hasattr(models, "AgencyProfile"):
            AgencyProfileClass = getattr(models, "AgencyProfile")
            profile = AgencyProfileClass(
                workspace_id=ws.id,
                tagline="Unrelated studio",
                description="Foreign studio profile",
                specializations='["animation"]',
                services='["vfx"]',
                portfolio='[]',
                contact_email="foreign@unrelated.test",
                is_published=True,
            )
            db.add(profile)

        db.commit()

        token = issue_token(owner, mem)
        owner_id = owner.id
        workspace_id = ws.id

    return {
        "owner_id": owner_id,
        "workspace_id": workspace_id,
        "email": "foreign_agency@unrelated.test",
        "token": token,
        "cookies": {"frameops_session": token},
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
def foreign_agency_client(foreign_agency_setup: dict[str, Any]) -> Generator[TestClient, None, None]:
    """TestClient pre-authenticated as the unrelated foreign Agency Owner."""
    with TestClient(app) as client:
        client.cookies.set("frameops_session", foreign_agency_setup["token"])
        client.headers["Authorization"] = f"Bearer {foreign_agency_setup['token']}"
        yield client


@pytest.fixture
def client_setup(isolated_db, agency_setup: dict[str, Any]) -> dict[str, Any]:
    """Creates a standard Client User, Client record, and ClientProfile."""
    Session = isolated_db
    with Session() as db:
        user = User(
            email="primary_client@clientcorp.test",
            password_hash=hash_password("client-secret-pass-123"),
        )
        if hasattr(user, "role"):
            setattr(user, "role", "client")
        if hasattr(user, "full_name"):
            setattr(user, "full_name", "Primary Client")
        db.add(user)
        db.flush()

        client = Client(
            workspace_id=agency_setup["workspace_id"],
            name="Primary Client Corp",
            brand="ClientCorp",
            industry="Technology",
            memory_bank_id="bank-client-primary-001",
            memory_status="ready",
        )
        db.add(client)
        db.flush()

        if hasattr(models, "ClientProfile"):
            ClientProfileClass = getattr(models, "ClientProfile")
            profile = ClientProfileClass(
                user_id=user.id,
                company_name="Primary Client Corp",
                industry="Technology",
                brand_guidelines="Clean, minimalist, bold colors",
                website="https://clientcorp.test",
            )
            db.add(profile)

        db.commit()

        token = _issue_test_client_token(client, user)
        user_id = user.id
        client_id = client.id

    return {
        "user_id": user_id,
        "client_id": client_id,
        "email": "primary_client@clientcorp.test",
        "token": token,
        "memory_bank_id": "bank-client-primary-001",
        "cookies": {
            "frameops_client_session": token,
            "frameops_portal_session": token,
        },
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
def client_user_client(client_setup: dict[str, Any]) -> Generator[TestClient, None, None]:
    """TestClient pre-authenticated as the primary Client."""
    with TestClient(app) as client:
        client.cookies.set("frameops_client_session", client_setup["token"])
        client.cookies.set("frameops_portal_session", client_setup["token"])
        client.headers["Authorization"] = f"Bearer {client_setup['token']}"
        yield client


@pytest.fixture
def foreign_client_setup(isolated_db, foreign_agency_setup: dict[str, Any]) -> dict[str, Any]:
    """Creates an unrelated foreign Client for cross-tenant isolation testing."""
    Session = isolated_db
    with Session() as db:
        user = User(
            email="foreign_client@othercorp.test",
            password_hash=hash_password("foreign-client-pass-123"),
        )
        if hasattr(user, "role"):
            setattr(user, "role", "client")
        if hasattr(user, "full_name"):
            setattr(user, "full_name", "Foreign Client")
        db.add(user)
        db.flush()

        client = Client(
            workspace_id=foreign_agency_setup["workspace_id"],
            name="Foreign Client Corp",
            brand="ForeignCorp",
            industry="Healthcare",
            memory_bank_id="bank-client-foreign-002",
            memory_status="ready",
        )
        db.add(client)
        db.flush()

        if hasattr(models, "ClientProfile"):
            ClientProfileClass = getattr(models, "ClientProfile")
            profile = ClientProfileClass(
                user_id=user.id,
                company_name="Foreign Client Corp",
                industry="Healthcare",
                brand_guidelines="Muted tones, formal",
                website="https://foreigncorp.test",
            )
            db.add(profile)

        db.commit()

        token = _issue_test_client_token(client, user)
        user_id = user.id
        client_id = client.id

    return {
        "user_id": user_id,
        "client_id": client_id,
        "email": "foreign_client@othercorp.test",
        "token": token,
        "memory_bank_id": "bank-client-foreign-002",
        "cookies": {
            "frameops_client_session": token,
            "frameops_portal_session": token,
        },
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
def foreign_client_client(foreign_client_setup: dict[str, Any]) -> Generator[TestClient, None, None]:
    """TestClient pre-authenticated as the unrelated foreign Client."""
    with TestClient(app) as client:
        client.cookies.set("frameops_client_session", foreign_client_setup["token"])
        client.cookies.set("frameops_portal_session", foreign_client_setup["token"])
        client.headers["Authorization"] = f"Bearer {foreign_client_setup['token']}"
        yield client
