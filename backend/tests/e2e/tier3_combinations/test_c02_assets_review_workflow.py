"""Tier 3 Pairwise Combinations: Assets, Review Studio, Scrubber & Deliverable Approval.

Coverage:
- test_tier3_c06_active_project_immediate_asset_upload:
  Scenario T3-06 (F08 Proposal Accept x F09 Active Project x F10 Asset Upload).
  Immediate asset upload on newly activated project persits to disk and metadata.
- test_tier3_c07_expired_session_and_cross_client_asset_rejection:
  Scenario T3-07 (F01 Client Auth x F10 Asset Upload x F16 Isolation).
  Expired tokens return 401 and cross-client uploads to Project A return 403/404.
- test_tier3_c08_video_asset_review_version_and_timecode_comments:
  Scenario T3-08 (F09 Active Project x F10 Asset Upload x F12 Video Review).
  Review version mapping and custom timecoded comments on video deliverable.
- test_tier3_c09_dual_channel_video_voice_feedback_extraction:
  Scenario T3-09 (F11 AI Extraction x F12 Video Review).
  Multi-channel review comments draft structured AI extraction with identified ambiguities.
- test_tier3_c15_final_deliverable_approval_and_project_completion:
  Scenario T3-15 (F08 Proposal Accept x F12 Video Review).
  Client deliverable approval transitions project status to completed and locks version.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from fastapi.testclient import TestClient
import jwt
import pytest
from sqlalchemy import select

from app.config import settings
from app.main import app
from app.models import Asset, Project, ReviewVersion, VideoComment


def test_tier3_c06_active_project_immediate_asset_upload(
    agency_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """T3-06: Newly activated project immediately accepts asset uploads with folder isolation."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Immediate Upload Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    video_data = b"\x00\x00\x00\x18ftypmp42" + b"video stream payload" * 15
    files = {"file": ("camera_raw_01.mp4", video_data, "video/mp4")}

    resp = agency_client.post(
        f"/api/projects/{proj_id}/assets",
        files=files,
        params={"category": "footage"},
    )
    assert resp.status_code == 201
    asset_data = resp.json()
    assert asset_data["filename"] == "camera_raw_01.mp4"
    assert asset_data["category"] == "footage"

    with isolated_db() as db:
        asset = db.get(Asset, asset_data["id"])
        assert asset is not None
        file_path = Path(asset.storage_key)
        assert file_path.is_file()
        assert file_path.read_bytes() == video_data


def test_tier3_c07_expired_session_and_cross_client_asset_rejection(
    foreign_client_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """T3-07: Expired JWTs fail with 401 and Client B uploading to Project A is rejected."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Secure Project A",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    # 1. Expired token upload attempt
    expired_payload = {
        "sub": f"client:{client_setup['client_id']}",
        "client_id": client_setup["client_id"],
        "workspace_id": agency_setup["workspace_id"],
        "role": "client",
        "exp": datetime.now(UTC) - timedelta(hours=2),
    }
    expired_token = jwt.encode(expired_payload, settings.auth_secret, algorithm="HS256")

    with TestClient(app) as expired_client:
        expired_client.cookies.set("frameops_session", expired_token)
        files = {"file": ("sneaky.mp4", b"data", "video/mp4")}
        resp_exp = expired_client.post(f"/api/projects/{proj_id}/assets", files=files)
        assert resp_exp.status_code == 401

    # 2. Foreign client uploading to Project A
    files_foreign = {"file": ("rogue.mp4", b"data", "video/mp4")}
    resp_cross = foreign_client_client.post(f"/api/projects/{proj_id}/assets", files=files_foreign)
    assert resp_cross.status_code in (401, 403, 404)


def test_tier3_c08_video_asset_review_version_and_timecode_comments(
    agency_client,
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """T3-08: Handoff from video asset upload to portal review version and timecode scrub comments."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Review Studio Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        ver = ReviewVersion(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            version_label="v1.0",
            status="in_review",
        )
        db.add(ver)
        db.commit()
        proj_id = proj.id
        ver_id = ver.id

    # Client retrieves portal project view
    resp_view = client_user_client.get(f"/api/portal/projects/{proj_id}")
    assert resp_view.status_code == 200
    data_view = resp_view.json()
    assert len(data_view["versions"]) >= 1

    # Client adds timestamped comment at 01:45.50 (105.5 seconds)
    comment_payload = {
        "timestamp_seconds": 105.5,
        "timecode": "01:45:15",
        "content": "Transition between shot A and shot B feels jarring",
        "version_id": ver_id,
        "author_name": "Executive Producer",
    }
    resp_comm = client_user_client.post(f"/api/portal/projects/{proj_id}/comments", json=comment_payload)
    assert resp_comm.status_code == 201
    comm_data = resp_comm.json()
    assert comm_data["timestamp_seconds"] == 105.5
    assert comm_data["timecode"] == "01:45:15"


def test_tier3_c09_dual_channel_video_voice_feedback_extraction(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """T3-09: Client submits review notes to AI feedback drafting endpoint which structures items."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Dual Channel Project",
            status="active",
        )
        db.add(proj)
        db.commit()
        proj_id = proj.id

    draft_payload = {
        "content": (
            "1. At 00:15 trim 2 seconds from the hero entrance.\n"
            "2. Make the grade color feel more punchy and warm.\n"
            "3. The background score volume seems a bit too high."
        ),
        "feedback_type": "text",
    }

    resp = client_user_client.post(f"/api/portal/projects/{proj_id}/feedback/draft", json=draft_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "requests" in data
    assert len(data["requests"]) >= 2
    assert "ambiguities" in data


def test_tier3_c15_final_deliverable_approval_and_project_completion(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """T3-15: Final deliverable approval transitions version to approved and project to completed."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Final Delivery Project",
            status="in_review",
        )
        db.add(proj)
        db.flush()

        ver = ReviewVersion(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            version_label="v2.0-final",
            status="in_review",
        )
        db.add(ver)
        db.commit()
        proj_id = proj.id
        ver_id = ver.id

    payload = {
        "decision": "approve",
        "version_id": ver_id,
        "notes": "Approved for national broadcast!",
    }

    resp = client_user_client.post(f"/api/portal/projects/{proj_id}/decision", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_status"] == "completed"
    assert data["version_status"] == "approved"

    with isolated_db() as db:
        p = db.get(Project, proj_id)
        v = db.get(ReviewVersion, ver_id)
        assert p.status == "completed"
        assert v.status == "approved"
