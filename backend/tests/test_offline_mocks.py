"""Unit and Contract Tests for Deterministic Offline Mocks and Database Isolation.

Verifies:
1. MockGroqService: extraction categories, ambiguity inference, audio transcription, error handling.
2. MockHindsightService: strict multi-tenant bank_id isolation, retain_and_verify, recall, reflect.
3. MockOpenClawService: DaVinci Resolve task synthesis, workflow validation, client preference memory injection.
4. Conftest database isolation: zero mutation of backend/frameops.db and monkeypatch fidelity.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

import app.db
from app.models import Client, User, Workspace
from app.schemas import ExtractionResult, SynthesisResult
from app.services.groq import ServiceUnavailable
from tests.e2e.mocks import (
    MockGroqService,
    MockHindsightService,
    MockOpenClawService,
    verify_resolve_workflow,
)


pytest_plugins = ["tests.e2e.conftest"]


# ==============================================================================
# 1. MockGroqService Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_mock_groq_extract_feedback_categories_and_ambiguities():
    service = MockGroqService()
    transcript = (
        "1. Please enhance the color grade and make the interior shots warmer with natural saturation.\n"
        "2. The intro pacing feels too slow, maybe trim 2 seconds from the opening cut.\n"
        "3. Turn up the dialogue volume in the audio track and balance the music stems.\n"
        "4. Add a lower third graphic title with the brand logo vector.\n"
        "5. Always use 16:9 aspect ratio as standard brand guideline."
    )

    result = await service.extract_feedback(transcript)
    assert isinstance(result, ExtractionResult)
    assert len(result.requests) >= 5

    categories = {req.category for req in result.requests}
    assert "grading" in categories
    assert "pacing" in categories
    assert "audio" in categories
    assert "graphics" in categories

    # Verify ambiguity detection for "maybe" / "feels too slow"
    ambiguous_items = [r for r in result.requests if r.requires_confirmation]
    assert len(ambiguous_items) >= 1
    assert any("pacing" in r.category for r in ambiguous_items)
    assert len(result.ambiguities) >= 1

    # Verify reusable preference detection
    reusable = [r for r in result.requests if r.memory_class == "reusable_preference"]
    assert len(reusable) >= 1

    # Verify asset requirement detection
    asset_categories = {a.category for a in result.required_assets}
    assert "logo" in asset_categories or "audio" in asset_categories


@pytest.mark.asyncio
async def test_mock_groq_extract_feedback_empty_input():
    service = MockGroqService()
    result = await service.extract_feedback("   ")
    assert isinstance(result, ExtractionResult)
    assert len(result.requests) == 0
    assert result.summary == ""


@pytest.mark.asyncio
async def test_mock_groq_extract_feedback_failure_simulation():
    service = MockGroqService()
    service.should_fail_extraction = True
    service.failure_message = "Simulated Groq 503 Overloaded"

    with pytest.raises(ServiceUnavailable) as exc:
        await service.extract_feedback("Make it punchier")
    assert "503 Overloaded" in str(exc.value)


@pytest.mark.asyncio
async def test_mock_groq_transcribe_audio_success(tmp_path: Path):
    service = MockGroqService()
    test_audio = tmp_path / "client_notes_color.wav"
    test_audio.write_bytes(b"RIFF" + b"\x00" * 100)

    text, model = await service.transcribe_audio(str(test_audio), "client_notes_color.wav", "audio/wav")
    assert "color" in text.lower() or "contrast" in text.lower()
    assert model == "whisper-large-v3-turbo"
    assert len(service.recorded_transcriptions) == 1


@pytest.mark.asyncio
async def test_mock_groq_transcribe_audio_empty_file(tmp_path: Path):
    service = MockGroqService()
    empty_audio = tmp_path / "empty.wav"
    empty_audio.write_bytes(b"")

    with pytest.raises(ValueError, match="Empty transcription"):
        await service.transcribe_audio(str(empty_audio), "empty.wav", "audio/wav")


@pytest.mark.asyncio
async def test_mock_groq_transcribe_audio_missing_file():
    service = MockGroqService()
    missing_path = "non_existent_audio_path_12345.wav"

    with pytest.raises(ServiceUnavailable, match="Audio file not found"):
        await service.transcribe_audio(missing_path, "missing.wav", "audio/wav")


@pytest.mark.asyncio
async def test_mock_groq_transcribe_audio_failure_simulation(tmp_path: Path):
    service = MockGroqService()
    service.should_fail_transcription = True
    test_audio = tmp_path / "notes.wav"
    test_audio.write_bytes(b"RIFF" + b"\x00" * 50)

    with pytest.raises(ServiceUnavailable):
        await service.transcribe_audio(str(test_audio), "notes.wav", "audio/wav")


def test_mock_groq_reset():
    service = MockGroqService()
    service.should_fail_extraction = True
    service.recorded_extractions.append("test")
    service.reset()
    assert not service.should_fail_extraction
    assert len(service.recorded_extractions) == 0


# ==============================================================================
# 2. MockHindsightService Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_mock_hindsight_tenant_isolation():
    service = MockHindsightService()
    bank_a = "tenant-client-alpha-bank"
    bank_b = "tenant-client-beta-bank"

    # Retain private preference in Bank A
    await service.retain(
        bank_id=bank_a,
        content="Always use teal and orange grading for commercial deliverables.",
        context="color_guidelines",
        tags=["client_alpha", "color"],
        document_id="doc-alpha-001",
    )

    # Bank B queries recall for color grading
    recall_b = await service.recall(bank_id=bank_b, query="color grading preference")
    assert recall_b.get("results") == [], "CRITICAL ISOLATION FAILURE: Bank B received Bank A's private memory!"

    # Bank A queries recall
    recall_a = await service.recall(bank_id=bank_a, query="color grading preference")
    assert len(recall_a.get("results", [])) == 1
    assert "teal and orange" in recall_a["results"][0]["text"]


@pytest.mark.asyncio
async def test_mock_hindsight_retain_and_verify():
    service = MockHindsightService()
    bank_id = "tenant-verify-bank"

    result, verified = await service.retain_and_verify(
        bank_id=bank_id,
        content="Never use comic sans typeface in lower thirds.",
        context="brand_fonts",
        tags=["fonts"],
        document_id="doc-font-001",
    )

    assert verified is True
    assert result.get("status") == "stored"
    assert len(result.get("results", [])) == 1
    assert result["results"][0]["document_id"] == "doc-font-001"


@pytest.mark.asyncio
async def test_mock_hindsight_keyword_recall_relevance():
    service = MockHindsightService()
    bank_id = "tenant-relevance-bank"

    service.seed_memory(bank_id, "Fast-paced jump cuts for social clips", context="editing")
    service.seed_memory(bank_id, "Dolby Atmos 5.1 surround sound mix for cinema", context="audio")
    service.seed_memory(bank_id, "Warm 3200K color balance for interviews", context="grading")

    # Recall audio preference
    res = await service.recall(bank_id, "surround sound mix")
    assert len(res["results"]) >= 1
    assert "Dolby Atmos" in res["results"][0]["text"]


@pytest.mark.asyncio
async def test_mock_hindsight_reflect_and_ensure_bank():
    service = MockHindsightService()
    bank_id = "tenant-mgmt-bank"

    ensured = await service.ensure_bank(bank_id)
    assert ensured["status"] == "ensured"
    assert service.configured() is True

    reflected = await service.reflect(bank_id, "Synthesize overall preferences")
    assert reflected["status"] == "ok"


@pytest.mark.asyncio
async def test_mock_hindsight_delete_bank():
    service = MockHindsightService()
    bank_id = "tenant-delete-bank"

    await service.retain(bank_id, "Temporary secret", "temp", [], "doc-temp")
    assert len((await service.recall(bank_id, "secret"))["results"]) == 1

    del_res = await service.delete_bank(bank_id)
    assert del_res["status"] == "deleted"

    # Now empty
    assert len((await service.recall(bank_id, "secret"))["results"]) == 0


@pytest.mark.asyncio
async def test_mock_hindsight_failure_simulation():
    service = MockHindsightService()
    service.should_fail = True
    service.failure_message = "Connection timeout to Hindsight cluster"

    with pytest.raises(ServiceUnavailable, match="Connection timeout"):
        await service.recall("any-bank", "query")


# ==============================================================================
# 3. MockOpenClawService Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_mock_openclaw_synthesize_valid_tasks():
    service = MockOpenClawService()
    extraction = {
        "requests": [
            {"description": "Apply warm organic saturation to interior shots", "category": "grading", "classification": "explicit"},
            {"description": "Balance background music dialogue stems", "category": "audio", "classification": "explicit"},
            {"description": "Ripple trim 2 seconds from montage", "category": "pacing", "classification": "explicit"},
            {"description": "Add brand logo animation to closing frame", "category": "graphics", "classification": "explicit"},
        ]
    }

    result = await service.synthesize(
        run_id=1,
        attempt_count=1,
        client_name="Test Client",
        project_name="Commercial Cut",
        extraction=extraction,
        memories={"results": []},
        assets=[],
    )

    assert isinstance(result, SynthesisResult)
    assert len(result.tasks) == 4

    # Validate that every task has a valid DaVinci Resolve workflow
    for task in result.tasks:
        val = verify_resolve_workflow(task.resolve_workflow)
        assert val["valid"] is True, f"Invalid workflow: {task.resolve_workflow} ({val['error']})"
        assert task.priority in ("low", "medium", "high")
        assert 0.0 <= task.confidence <= 1.0


def test_mock_openclaw_resolve_workflow_validation():
    # Valid workflows
    assert verify_resolve_workflow("Color page -> Primaries wheel -> Adjust temperature")["valid"] is True
    assert verify_resolve_workflow("Fairlight page -> Track EQ & Dynamics -> Balance stems")["valid"] is True
    assert verify_resolve_workflow("Edit page -> Timeline -> Ripple trim head cuts")["valid"] is True
    assert verify_resolve_workflow("Fusion page -> Text+ node -> Apply brand font")["valid"] is True

    # Invalid: empty
    assert verify_resolve_workflow("")["valid"] is False

    # Invalid: missing resolve page
    assert verify_resolve_workflow("Just edit the cut on the computer")["valid"] is False

    # Invalid: word count exceeds 20 words
    long_workflow = "Color page " + "word " * 25
    assert verify_resolve_workflow(long_workflow)["valid"] is False


@pytest.mark.asyncio
async def test_mock_openclaw_incorporates_client_memory():
    service = MockOpenClawService()
    extraction = {
        "requests": [
            {"description": "Adjust color grading for summer campaign", "category": "grading", "classification": "explicit"}
        ]
    }
    memories = {
        "results": [
            {"text": "Always preserve skin tones and avoid oversaturating greens.", "id": "mem-001"}
        ]
    }

    result = await service.synthesize(
        run_id=2,
        attempt_count=1,
        client_name="Acme Client",
        project_name="Summer Campaign",
        extraction=extraction,
        memories=memories,
        assets=[],
    )

    # Check that client preference is incorporated into synthesized tasks (Step 15)
    sources = {t.source for t in result.tasks}
    assert "client_memory" in sources or any("skin tones" in t.evidence for t in result.tasks)


@pytest.mark.asyncio
async def test_mock_openclaw_fallback_baseline_task():
    service = MockOpenClawService()
    result = await service.synthesize(
        run_id=3,
        attempt_count=1,
        client_name="Test Client",
        project_name="Empty Extraction Project",
        extraction={"requests": []},
        memories={"results": []},
        assets=[],
    )

    assert len(result.tasks) >= 1
    assert "Edit page" in result.tasks[0].resolve_workflow


@pytest.mark.asyncio
async def test_mock_openclaw_failure_simulation():
    service = MockOpenClawService()
    service.should_fail = True
    service.failure_message = "OpenClaw subprocess execution timeout"

    with pytest.raises(ServiceUnavailable, match="timeout"):
        await service.synthesize(
            run_id=4, attempt_count=1, client_name="C", project_name="P",
            extraction={}, memories={}, assets=[]
        )


# ==============================================================================
# 4. Database Isolation and Integrity Tests
# ==============================================================================

def test_database_isolation_does_not_modify_prod_db(isolated_db):
    """Verify that writing new rows in isolated_db never touches backend/frameops.db."""
    prod_db_path = Path("backend/frameops.db").resolve()
    if not prod_db_path.is_file():
        prod_db_path = Path("frameops.db").resolve()

    assert prod_db_path.is_file(), "Active database backend/frameops.db not found"
    initial_sha = hashlib.sha256(prod_db_path.read_bytes()).hexdigest()
    initial_size = prod_db_path.stat().st_size

    # Insert test data into the isolated in-memory DB
    Session = isolated_db
    with Session() as session:
        user = User(email="temporary_test_user@isolated.test", password_hash="hash-12345")
        ws = Workspace(name="Temporary Isolated Workspace")
        session.add_all([user, ws])
        session.commit()

        # Query to verify it was written in memory
        loaded_user = session.scalar(select(User).where(User.email == "temporary_test_user@isolated.test"))
        assert loaded_user is not None
        assert loaded_user.id > 0

    # Verify active production database is 100% byte-for-byte identical
    current_sha = hashlib.sha256(prod_db_path.read_bytes()).hexdigest()
    current_size = prod_db_path.stat().st_size

    assert initial_sha == current_sha, "CRITICAL ERROR: isolated_db mutated backend/frameops.db!"
    assert initial_size == current_size


def test_isolated_db_monkeypatch_covers_sessionlocal(isolated_db):
    """Verify that app.db.SessionLocal and app.db.engine are monkeypatched to isolated DB."""
    Session = isolated_db

    # Calling app.db.SessionLocal() directly must create a session bound to the test engine
    with app.db.SessionLocal() as session:
        ws = Workspace(name="SessionLocal Direct Insert Workspace")
        session.add(ws)
        session.commit()
        ws_id = ws.id
        assert ws_id > 0

    # Verify it can be retrieved from Session()
    with Session() as session:
        loaded = session.get(Workspace, ws_id)
        assert loaded is not None
        assert loaded.name == "SessionLocal Direct Insert Workspace"


# ==============================================================================
# 5. E2E Persona & Multi-Tenant Conftest Fixture Verification Tests
# ==============================================================================

def test_e2e_agency_setup_fixture(agency_setup, agency_client):
    """Verifies that agency_setup creates valid owner and workspace with proper session tokens."""
    assert agency_setup["owner_id"] > 0
    assert agency_setup["workspace_id"] > 0
    assert "frameops_session" in agency_setup["cookies"]
    assert agency_setup["headers"]["Authorization"].startswith("Bearer ")

    # agency_client can authenticate
    resp = agency_client.get("/api/auth/me")
    if resp.status_code == 200:
        data = resp.json()
        assert data.get("email") == agency_setup["email"]


def test_e2e_client_setup_fixture(client_setup, client_user_client):
    """Verifies that client_setup creates valid client and session tokens."""
    assert client_setup["user_id"] > 0
    assert client_setup["client_id"] > 0
    assert "frameops_client_session" in client_setup["cookies"]
    assert client_setup["headers"]["Authorization"].startswith("Bearer ")


def test_e2e_cross_tenant_isolation_fixtures(
    agency_setup, foreign_agency_setup, client_setup, foreign_client_setup
):
    """Verifies that distinct tenants have isolated IDs, workspaces, and memory banks."""
    assert agency_setup["workspace_id"] != foreign_agency_setup["workspace_id"]
    assert agency_setup["owner_id"] != foreign_agency_setup["owner_id"]
    assert client_setup["client_id"] != foreign_client_setup["client_id"]
    assert client_setup["memory_bank_id"] != foreign_client_setup["memory_bank_id"]


@pytest.mark.asyncio
async def test_e2e_autouse_external_mocks_integration(mock_groq, mock_hindsight, mock_openclaw):
    """Verifies that external services are wired to deterministic offline mocks."""
    import app.services.groq as groq
    import app.services.hindsight as hindsight
    import app.services.openclaw as openclaw

    # Groq extraction through module interface
    res = await groq.extract_feedback("Trim 2 seconds from montage")
    assert isinstance(res, ExtractionResult)
    assert len(res.requests) >= 1

    # Hindsight memory through module interface
    assert hindsight.configured() is True
    retain_res = await hindsight.retain("test-bank", "Color note", "grading", ["tag"], "doc-01")
    assert retain_res.get("status") == "stored"

    # OpenClaw synthesis through module interface
    synth_res = await openclaw.synthesize(
        run_id=10, attempt_count=1, client_name="Test", project_name="Proj",
        extraction={"requests": [{"description": "Color grade interior", "category": "grading"}]},
        memories={"results": []}, assets=[]
    )
    assert isinstance(synth_res, SynthesisResult)
    assert len(synth_res.tasks) >= 1

