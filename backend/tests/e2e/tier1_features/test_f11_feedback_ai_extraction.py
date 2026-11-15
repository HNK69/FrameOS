"""Tier 1 Feature 11 Tests: Agency Feedback AI Extraction.

Coverage:
- test_tier1_f11_groq_extracts_structured_feedback_categories:
  Groq extract_feedback categorizes multi-domain notes across grading, pacing, audio, and graphics.
- test_tier1_f11_extraction_identifies_explicit_vs_inferred_requests:
  Differentiates explicit instructions from ambiguous inferred requests requiring confirmation.
- test_tier1_f11_extraction_flags_actionable_ambiguities:
  Flags subjective or vague notes as actionable ambiguities with clarification prompts.
- test_tier1_f11_portal_feedback_draft_endpoint:
  Client portal drafts structured AI feedback from raw client review notes (POST /api/portal/projects/{id}/feedback/draft).
- test_tier1_f11_process_transcript_persists_extracted_items:
  Agency process-transcript pipeline persists ExtractedItem records to database (POST /api/process-transcript).
- test_tier1_f11_voice_audio_transcription_and_extraction:
  Transcribes voice notes using Whisper and produces structured editing feedback.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest
from sqlalchemy import select

from app.models import ExtractedItem, ProcessingRun, Project
from app.schemas import ExtractionResult


@pytest.mark.asyncio
async def test_tier1_f11_groq_extracts_structured_feedback_categories(mock_groq):
    """F11-1: Groq extracts structured items categorized across grading, pacing, audio, and graphics."""
    transcript = (
        "1. Warm up the color grade and adjust saturation.\n"
        "2. Trim the scene pacing and cut 2s from the intro.\n"
        "3. Raise the music volume track and balance dialogue.\n"
        "4. Fix the lower third font and brand logo graphic."
    )

    result = await mock_groq.extract_feedback(transcript)
    assert isinstance(result, ExtractionResult)
    assert len(result.requests) >= 4

    categories = {r.category for r in result.requests}
    assert "grading" in categories
    assert "pacing" in categories
    assert "audio" in categories
    assert "graphics" in categories


@pytest.mark.asyncio
async def test_tier1_f11_extraction_identifies_explicit_vs_inferred_requests(mock_groq):
    """F11-2: AI extraction separates explicit concrete notes from ambiguous inferred requests."""
    transcript = (
        "1. Cut the opening scene at exactly 5 seconds.\n"
        "2. Maybe the background music feels a bit too slow."
    )

    result = await mock_groq.extract_feedback(transcript)
    assert len(result.requests) == 2

    explicit_item = result.requests[0]
    inferred_item = result.requests[1]

    assert explicit_item.classification == "explicit"
    assert explicit_item.confidence >= 0.90
    assert explicit_item.requires_confirmation is False

    assert inferred_item.classification == "inferred"
    assert inferred_item.confidence < 0.85
    assert inferred_item.requires_confirmation is True


@pytest.mark.asyncio
async def test_tier1_f11_extraction_flags_actionable_ambiguities(mock_groq):
    """F11-3: Vague aesthetic notes are flagged in ambiguities to guide follow-up clarification."""
    transcript = "The color should pop more and the overall vibe feels a bit off."

    result = await mock_groq.extract_feedback(transcript)
    assert len(result.ambiguities) >= 1
    assert any("Ambiguity in note" in amb for amb in result.ambiguities)


def test_tier1_f11_portal_feedback_draft_endpoint(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F11-4: Client portal drafts structured AI feedback from text notes (POST /api/portal/projects/{id}/feedback/draft)."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Portal AI Feedback Draft Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    payload = {
        "content": "Please enhance color saturation and trim 2s from the hook sequence",
        "feedback_type": "text",
    }

    resp = client_user_client.post(f"/api/portal/projects/{proj_id}/feedback/draft", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "requests" in data
    assert "ambiguities" in data
    assert len(data["requests"]) >= 1


def test_tier1_f11_process_transcript_persists_extracted_items(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F11-5: Agency process-transcript pipeline persists ExtractedItem rows in DB."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Transcript Processing Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    payload = {
        "project_id": proj_id,
        "transcript": (
            "1. Apply warm organic color grade across all scenes.\n"
            "2. Balance dialogue track volume against background score."
        ),
    }

    resp = agency_client.post("/api/process-transcript", json=payload)
    assert resp.status_code == 201
    run_data = resp.json()
    run_id = run_data["id"]
    assert run_data["status"] == "completed"

    with isolated_db() as db:
        items = db.scalars(select(ExtractedItem).where(ExtractedItem.run_id == run_id)).all()
        assert len(items) >= 2
        categories = {item.category for item in items}
        assert "grading" in categories
        assert "audio" in categories
        for item in items:
            assert item.confidence > 0.5


@pytest.mark.asyncio
async def test_tier1_f11_voice_audio_transcription_and_extraction(mock_groq):
    """F11-6: Audio transcription via Whisper produces transcript text and identifies model."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(b"RIFF" + b"\x00" * 36 + b"WAVEfmt " + b"\x00" * 40)
        temp_path = Path(f.name)

    try:
        text, model = await mock_groq.transcribe_audio(
            str(temp_path),
            "client_color_notes.wav",
            "audio/wav",
        )
        assert "color" in text.lower() or "contrast" in text.lower()
        assert model == "whisper-large-v3-turbo"
    finally:
        if temp_path.exists():
            temp_path.unlink()
