"""Tier 2 Boundary, Error, and Security Tests: Features 9 to 12.

Coverage:
- Feature 9: Project Transition Boundaries (Tests 81 to 86)
  81. test_tier2_b09_duplicate_proposal_acceptance_rejected: Double proposal acceptance rejected (400/409).
  82. test_tier2_b09_foreign_agency_cannot_access_project: Foreign agency cannot view Project A (404).
  83. test_tier2_b09_foreign_client_cannot_access_project_in_portal: Foreign client cannot view Project A in portal (404).
  84. test_tier2_b09_cannot_accept_declined_proposal: Acceptance of declined proposal rejected (400).
  85. test_tier2_b09_project_patch_invalid_status_enum: Invalid status enum on project patch rejected (422).
  86. test_tier2_b09_accept_nonexistent_proposal_returns_404: Accepting nonexistent proposal returns 404.
- Feature 10: Client Asset Upload & Ownership Boundaries (Tests 87 to 92)
  87. test_tier2_b10_upload_empty_asset_rejected: 0-byte file upload rejected with 413.
  88. test_tier2_b10_upload_oversized_asset_rejected: File exceeding max_upload_bytes rejected with 413.
  89. test_tier2_b10_upload_disallowed_mime_type_rejected: Disallowed MIME type rejected with 415.
  90. test_tier2_b10_path_traversal_filename_sanitized: Path traversal in uploaded filename sanitized safely.
  91. test_tier2_b10_cross_tenant_asset_download_forbidden: Cross-tenant download and streaming return 404.
  92. test_tier2_b10_upload_asset_to_nonexistent_project_returns_404: Upload to nonexistent project returns 404.
- Feature 11: Feedback AI Extraction Boundaries (Tests 93 to 98)
  93. test_tier2_b11_extract_empty_or_whitespace_transcript: Empty transcript returns empty ExtractionResult.
  94. test_tier2_b11_groq_service_unavailable_handling: Groq outage marks run failed and returns 503.
  95. test_tier2_b11_extreme_length_transcript_handling: Transcripts exceeding 100k chars rejected with 422.
  96. test_tier2_b11_audio_transcription_empty_file_rejected: Empty audio file raises ValueError.
  97. test_tier2_b11_portal_draft_empty_content_rejected: Blank feedback draft rejected with 422.
  98. test_tier2_b11_idempotency_key_mismatch_on_process_transcript: Replaying idempotency key with different text returns 409.
- Feature 12: Video Review Studio Boundaries (Tests 99 to 104)
  99. test_tier2_b12_comment_negative_timestamp_rejected: Negative timestamp_seconds rejected with 422.
  100. test_tier2_b12_comment_empty_content_or_timecode_rejected: Empty content or timecode rejected with 422.
  101. test_tier2_b12_decision_invalid_enum_rejected: Invalid decision string rejected with 422.
  102. test_tier2_b12_comment_on_nonexistent_project_returns_404: Comment on nonexistent project returns 404.
  103. test_tier2_b12_foreign_client_cannot_comment_or_decide: Foreign client commenting on Client A project returns 404.
  104. test_tier2_b12_comment_patch_invalid_status_rejected: Comment patch with invalid status rejected with 422.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import settings
from app.main import app
from app.models import (
    Asset,
    ProcessingRun,
    Project,
    ProjectRequest,
    Proposal,
    VideoComment,
)

from . import progressive_check

# ==============================================================================
# Feature 9: Project Transition Boundaries (Tests 81-86)
# ==============================================================================

def test_tier2_b09_duplicate_proposal_acceptance_rejected(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B09-1: Double acceptance of already accepted proposal returns 400 Bad Request or 409 Conflict."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Brief for Double Accept",
            status="accepted",
        )
        db.add(req)
        db.flush()

        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="Scope A",
            estimated_days=7,
            status="accepted",
        )
        db.add(prop)
        db.commit()
        prop_id = prop.id

    def _fallback():
        with isolated_db() as db:
            p = db.get(Proposal, prop_id)
            assert p.status == "accepted"

    resp = client_user_client.post(f"/api/client/proposals/{prop_id}/accept")
    progressive_check(app, resp, f"/api/client/proposals/{prop_id}/accept", _fallback)
    assert resp.status_code in (400, 409)


def test_tier2_b09_foreign_agency_cannot_access_project(
    foreign_agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B09-2: Foreign agency cannot view Project A (returns 404 Not Found)."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Confidential Project Alpha",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    resp = foreign_agency_client.get(f"/api/projects/{proj_id}")
    assert resp.status_code == 404


def test_tier2_b09_foreign_client_cannot_access_project_in_portal(
    foreign_client_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B09-3: Foreign client cannot view Client A's project in portal (returns 404 Not Found)."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Client A Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    resp = foreign_client_client.get(f"/api/portal/projects/{proj_id}")
    assert resp.status_code == 404


def test_tier2_b09_cannot_accept_declined_proposal(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B09-4: Proposal in 'declined' status cannot be accepted (returns 400 Bad Request)."""
    with isolated_db() as db:
        req = ProjectRequest(
            client_user_id=client_setup["user_id"],
            agency_workspace_id=agency_setup["workspace_id"],
            title="Brief with Declined Proposal",
            status="under_review",
        )
        db.add(req)
        db.flush()

        prop = Proposal(
            request_id=req.id,
            agency_workspace_id=agency_setup["workspace_id"],
            scope_description="Rejected Scope",
            estimated_days=10,
            status="declined",
        )
        db.add(prop)
        db.commit()
        prop_id = prop.id

    def _fallback():
        with isolated_db() as db:
            p = db.get(Proposal, prop_id)
            assert p.status == "declined"

    resp = client_user_client.post(f"/api/client/proposals/{prop_id}/accept")
    progressive_check(app, resp, f"/api/client/proposals/{prop_id}/accept", _fallback)
    assert resp.status_code in (400, 422)


def test_tier2_b09_project_patch_invalid_status_enum(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B09-5: Patching project with invalid status string is rejected with 422 Unprocessable Entity."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Enum Test Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    payload = {
        "client_id": client_setup["client_id"],
        "name": "Enum Test Project",
        "status": "destroyed_and_deleted",
    }
    resp = agency_client.patch(f"/api/projects/{proj_id}", json=payload)
    assert resp.status_code == 422


def test_tier2_b09_accept_nonexistent_proposal_returns_404(
    client_user_client,
    isolated_db,
):
    """B09-6: Accepting nonexistent proposal ID 999999 returns 404 Not Found."""
    def _fallback():
        with isolated_db() as db:
            p = db.get(Proposal, 999999)
            assert p is None

    resp = client_user_client.post("/api/client/proposals/999999/accept")
    progressive_check(app, resp, "/api/client/proposals/999999/accept", _fallback)
    assert resp.status_code == 404


# ==============================================================================
# Feature 10: Client Asset Upload & Ownership Boundaries (Tests 87-92)
# ==============================================================================

def test_tier2_b10_upload_empty_asset_rejected(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B10-1: Uploading a 0-byte asset file is rejected with 413 Payload Too Large."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Empty Upload Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    files = {"file": ("empty_cut.mp4", b"", "video/mp4")}
    resp = agency_client.post(f"/api/projects/{proj_id}/assets", files=files)
    assert resp.status_code == 413


def test_tier2_b10_upload_oversized_asset_rejected(
    agency_client,
    agency_setup,
    client_setup,
    monkeypatch,
    isolated_db,
):
    """B10-2: Uploading an asset exceeding max_upload_bytes is rejected with 413 Payload Too Large."""
    monkeypatch.setattr(settings, "max_upload_bytes", 200)

    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Oversized Upload Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    oversized_data = b"X" * 300
    files = {"file": ("oversized.mp4", oversized_data, "video/mp4")}
    resp = agency_client.post(f"/api/projects/{proj_id}/assets", files=files)
    assert resp.status_code == 413


def test_tier2_b10_upload_disallowed_mime_type_rejected(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B10-3: Uploading an asset with a disallowed executable MIME type is rejected with 415."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Disallowed MIME Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    files = {"file": ("evil_script.exe", b"MZ\x90\x00" + b"\x00" * 50, "application/x-dosexec")}
    resp = agency_client.post(f"/api/projects/{proj_id}/assets", files=files)
    assert resp.status_code == 415


def test_tier2_b10_path_traversal_filename_sanitized(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B10-4: Filenames containing path traversal elements (../../) are stripped to safe basenames."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Traversal Sanitization Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    traversal_filename = "../../../../etc/passwd"
    files = {"file": (traversal_filename, b"safe file content", "text/plain")}
    resp = agency_client.post(f"/api/projects/{proj_id}/assets", files=files)
    assert resp.status_code == 201
    asset_data = resp.json()
    assert asset_data["filename"] == "passwd"
    assert ".." not in asset_data["filename"]

    # Verify storage path is within upload_dir
    with isolated_db() as db:
        asset = db.get(Asset, asset_data["id"])
        storage_path = Path(asset.storage_key)
        upload_root = Path(settings.upload_dir).resolve()
        assert upload_root in storage_path.resolve().parents


def test_tier2_b10_cross_tenant_asset_download_forbidden(
    foreign_agency_client,
    foreign_client_client,
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B10-5: Foreign agency and foreign client cannot download or stream Asset A (returns 404)."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Protected Asset Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    files = {"file": ("secret_take.wav", b"Secret audio data", "audio/wav")}
    up_resp = agency_client.post(f"/api/projects/{proj_id}/assets", files=files)
    assert up_resp.status_code == 201
    asset_id = up_resp.json()["id"]

    # 1. Foreign agency cannot download via agency endpoint
    resp1 = foreign_agency_client.get(f"/api/assets/{asset_id}/download")
    assert resp1.status_code == 404

    # 2. Foreign client cannot stream via portal endpoint
    resp2 = foreign_client_client.get(f"/api/portal/assets/{asset_id}/stream")
    assert resp2.status_code == 404


def test_tier2_b10_upload_asset_to_nonexistent_project_returns_404(
    agency_client,
):
    """B10-6: Uploading asset to nonexistent project ID 999999 returns 404 Not Found."""
    files = {"file": ("asset.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4")}
    resp = agency_client.post("/api/projects/999999/assets", files=files)
    assert resp.status_code == 404


# ==============================================================================
# Feature 11: Feedback AI Extraction Boundaries (Tests 93-98)
# ==============================================================================

@pytest.mark.asyncio
async def test_tier2_b11_extract_empty_or_whitespace_transcript(mock_groq):
    """B11-1: Extracting empty or whitespace transcript returns clean empty ExtractionResult without crashing."""
    res = await mock_groq.extract_feedback("   \n\t  ")
    assert res.summary == ""
    assert len(res.requests) == 0
    assert len(res.required_assets) == 0


def test_tier2_b11_groq_service_unavailable_handling(
    agency_client,
    agency_setup,
    client_setup,
    mock_groq,
    isolated_db,
):
    """B11-2: Simulated Groq outage marks run failed and returns 503 Service Unavailable."""
    mock_groq.should_fail_extraction = True

    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Groq Outage Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    payload = {"project_id": proj_id, "transcript": "Apply warm organic color grade."}
    resp = agency_client.post("/api/process-transcript", json=payload)
    assert resp.status_code == 503

    with isolated_db() as db:
        run = db.scalar(select(ProcessingRun).where(ProcessingRun.project_id == proj_id))
        assert run is not None
        assert run.status == "failed"
        assert run.stage == "failed"


def test_tier2_b11_extreme_length_transcript_handling(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B11-3: Transcripts exceeding 100,000 characters are rejected with 422 Unprocessable Entity."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Length Boundary Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    oversized_text = "A" * 100_001
    payload = {"project_id": proj_id, "transcript": oversized_text}
    resp = agency_client.post("/api/process-transcript", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_tier2_b11_audio_transcription_empty_file_rejected(mock_groq):
    """B11-4: Transcribing a 0-byte audio file raises ValueError('Empty transcription')."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        temp_path = Path(f.name)

    try:
        with pytest.raises(ValueError, match="Empty transcription"):
            await mock_groq.transcribe_audio(str(temp_path), "empty.wav", "audio/wav")
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_tier2_b11_portal_draft_empty_content_rejected(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B11-5: Portal draft with whitespace or content shorter than 3 chars is rejected with 422."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Portal Draft Boundary Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    payload = {"content": "  ", "feedback_type": "text"}
    resp = client_user_client.post(f"/api/portal/projects/{proj_id}/feedback/draft", json=payload)
    assert resp.status_code == 422


def test_tier2_b11_idempotency_key_mismatch_on_process_transcript(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B11-6: Reusing an Idempotency-Key with different transcript text returns 409 Conflict."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Idempotency Conflict Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    headers = {"Idempotency-Key": "idemp-key-shared-001"}

    # First call with text A
    resp1 = agency_client.post(
        "/api/process-transcript",
        json={"project_id": proj_id, "transcript": "Initial text A for processing"},
        headers=headers,
    )
    assert resp1.status_code == 201

    # Second call with same key but text B
    resp2 = agency_client.post(
        "/api/process-transcript",
        json={"project_id": proj_id, "transcript": "Conflicting text B for processing"},
        headers=headers,
    )
    assert resp2.status_code == 409


# ==============================================================================
# Feature 12: Video Review Studio Boundaries (Tests 99-104)
# ==============================================================================

def test_tier2_b12_comment_negative_timestamp_rejected(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B12-1: Negative timestamp_seconds is rejected with 422 Unprocessable Entity."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Negative Timestamp Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    payload = {
        "timestamp_seconds": -5.0,
        "timecode": "00:00:00:00",
        "content": "Negative time test",
    }
    resp = client_user_client.post(f"/api/portal/projects/{proj_id}/comments", json=payload)
    assert resp.status_code == 422


def test_tier2_b12_comment_empty_content_or_timecode_rejected(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B12-2: Empty comment content or blank timecode string is rejected with 422 Unprocessable Entity."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Empty Comment Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    # 1. Blank content
    resp1 = client_user_client.post(
        f"/api/portal/projects/{proj_id}/comments",
        json={"timestamp_seconds": 10.0, "timecode": "00:00:10:00", "content": ""},
    )
    assert resp1.status_code == 422

    # 2. Blank timecode
    resp2 = client_user_client.post(
        f"/api/portal/projects/{proj_id}/comments",
        json={"timestamp_seconds": 10.0, "timecode": "", "content": "Valid comment"},
    )
    assert resp2.status_code == 422


def test_tier2_b12_decision_invalid_enum_rejected(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B12-3: Decision string not in (approve, changes_requested, reject) is rejected with 422."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Invalid Decision Project",
            status="in_review",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    payload = {"decision": "maybe_later_undecided"}
    resp = client_user_client.post(f"/api/portal/projects/{proj_id}/decision", json=payload)
    assert resp.status_code == 422


def test_tier2_b12_comment_on_nonexistent_project_returns_404(
    client_user_client,
):
    """B12-4: Submitting comment to nonexistent project ID 999999 returns 404 Not Found."""
    payload = {
        "timestamp_seconds": 5.0,
        "timecode": "00:00:05:00",
        "content": "Phantom project comment",
    }
    resp = client_user_client.post("/api/portal/projects/999999/comments", json=payload)
    assert resp.status_code == 404


def test_tier2_b12_foreign_client_cannot_comment_or_decide(
    foreign_client_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B12-5: Foreign client cannot comment on or submit decisions for Client A's project (returns 404)."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Client A Review Project",
            status="in_review",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    # 1. Foreign client cannot post comment
    resp_com = foreign_client_client.post(
        f"/api/portal/projects/{proj_id}/comments",
        json={"timestamp_seconds": 12.0, "timecode": "00:00:12:00", "content": "Unauthorized note"},
    )
    assert resp_com.status_code == 404

    # 2. Foreign client cannot submit decision
    resp_dec = foreign_client_client.post(
        f"/api/portal/projects/{proj_id}/decision",
        json={"decision": "approve"},
    )
    assert resp_dec.status_code == 404


def test_tier2_b12_comment_patch_invalid_status_rejected(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """B12-6: Updating comment status to value outside (submitted, processing, resolved) returns 422."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Comment Patch Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        com = VideoComment(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            timestamp_seconds=5.0,
            timecode="00:00:05:00",
            content="Test note",
            status="submitted",
        )
        db.add(com)
        db.commit()
        proj_id = proj.id
        com_id = com.id

    resp = client_user_client.patch(
        f"/api/portal/projects/{proj_id}/comments/{com_id}?status=invalid_bogus_status"
    )
    assert resp.status_code == 422
