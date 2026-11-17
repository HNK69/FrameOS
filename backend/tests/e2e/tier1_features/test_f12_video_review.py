"""Tier 1 Feature 12 Tests: Video Review Studio & Timestamped Comments.

Coverage:
- test_tier1_f12_client_creates_timecoded_comment:
  Client submits timecoded feedback comment linked to review version (POST /api/portal/projects/{id}/comments).
- test_tier1_f12_list_comments_chronological_ordering:
  Comments endpoint returns list strictly ordered by ascending timestamp_seconds (GET /api/portal/projects/{id}/comments).
- test_tier1_f12_update_comment_status_lifecycle:
  Updates comment status across submitted -> processing -> resolved lifecycle (PATCH /api/portal/projects/{id}/comments/{id}).
- test_tier1_f12_client_submits_approval_decision:
  Client submits 'approve' decision, marking project completed and version approved (POST /api/portal/projects/{id}/decision).
- test_tier1_f12_client_submits_changes_requested_decision:
  Client submits 'changes_requested' decision, setting version status to changes_requested (POST /api/portal/projects/{id}/decision).
- test_tier1_f12_portal_project_overview_aggregates_review_data:
  Portal project overview aggregates versions, comments, and unresolved comment counts (GET /api/portal/projects/{id}).
"""

from __future__ import annotations

from app.models import ClientFeedbackSubmission, Project, ReviewVersion, VideoComment


def test_tier1_f12_client_creates_timecoded_comment(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F12-1: Client creates a timecoded comment on review version."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Video Review Project",
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

    payload = {
        "timestamp_seconds": 45.5,
        "timecode": "00:00:45:12",
        "content": "Audio clip cuts off abruptly here",
        "version_id": ver_id,
        "author_name": "Client Lead",
    }

    resp = client_user_client.post(f"/api/portal/projects/{proj_id}/comments", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] > 0
    assert data["timestamp_seconds"] == 45.5
    assert data["timecode"] == "00:00:45:12"
    assert data["content"] == "Audio clip cuts off abruptly here"
    assert data["status"] == "submitted"
    assert data["author_name"] == "Client Lead"


def test_tier1_f12_list_comments_chronological_ordering(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F12-2: Comments are listed in strictly ascending chronological order by timestamp_seconds."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Timeline Sorting Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        # Add 3 comments out of order
        c1 = VideoComment(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            timestamp_seconds=72.0,
            timecode="00:01:12:00",
            content="End credits cut early",
            status="submitted",
        )
        c2 = VideoComment(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            timestamp_seconds=14.5,
            timecode="00:00:14:12",
            content="Intro title typo",
            status="submitted",
        )
        c3 = VideoComment(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            timestamp_seconds=30.2,
            timecode="00:00:30:05",
            content="Color balance shift",
            status="submitted",
        )
        db.add_all([c1, c2, c3])
        db.commit()
        proj_id = proj.id

    resp = client_user_client.get(f"/api/portal/projects/{proj_id}/comments")
    assert resp.status_code == 200
    comments = resp.json()
    assert len(comments) == 3
    timestamps = [c["timestamp_seconds"] for c in comments]
    assert timestamps == [14.5, 30.2, 72.0]


def test_tier1_f12_update_comment_status_lifecycle(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F12-3: Comment status can be updated from submitted to processing to resolved."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Comment Lifecycle Project",
            status="active",
        )
        db.add(proj)
        db.flush()

        comment = VideoComment(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            timestamp_seconds=22.0,
            timecode="00:00:22:00",
            content="Lower third misalignment",
            status="submitted",
        )
        db.add(comment)
        db.commit()
        proj_id = proj.id
        comment_id = comment.id

    # 1. Update to processing
    resp1 = client_user_client.patch(f"/api/portal/projects/{proj_id}/comments/{comment_id}?status=processing")
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "processing"

    # 2. Update to resolved
    resp2 = client_user_client.patch(f"/api/portal/projects/{proj_id}/comments/{comment_id}?status=resolved")
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "resolved"

    with isolated_db() as db:
        c = db.get(VideoComment, comment_id)
        assert c.status == "resolved"


def test_tier1_f12_client_submits_approval_decision(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F12-4: Submitting an 'approve' decision completes project and marks version approved."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Approval Workflow Project",
            status="in_review",
        )
        db.add(proj)
        db.flush()

        ver = ReviewVersion(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            version_label="v2.0",
            status="in_review",
        )
        db.add(ver)
        db.commit()
        proj_id = proj.id
        ver_id = ver.id

    payload = {
        "decision": "approve",
        "version_id": ver_id,
        "notes": "Approved for delivery! Fantastic color work.",
    }

    resp = client_user_client.post(f"/api/portal/projects/{proj_id}/decision", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_status"] == "completed"
    assert data["version_status"] == "approved"
    assert data["decision"] == "approve"
    assert data["submission_id"] > 0

    with isolated_db() as db:
        p = db.get(Project, proj_id)
        v = db.get(ReviewVersion, ver_id)
        sub = db.get(ClientFeedbackSubmission, data["submission_id"])
        assert p.status == "completed"
        assert v.status == "approved"
        assert sub.review_decision == "approve"
        assert sub.status == "resolved"


def test_tier1_f12_client_submits_changes_requested_decision(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F12-5: Submitting 'changes_requested' updates version status and keeps project in review."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Revisions Project",
            status="in_review",
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

    payload = {
        "decision": "changes_requested",
        "version_id": ver_id,
        "notes": "Fix color grade and adjust pacing on section 2.",
    }

    resp = client_user_client.post(f"/api/portal/projects/{proj_id}/decision", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["version_status"] == "changes_requested"
    assert data["project_status"] == "in_review"

    with isolated_db() as db:
        v = db.get(ReviewVersion, ver_id)
        assert v.status == "changes_requested"


def test_tier1_f12_portal_project_overview_aggregates_review_data(
    client_user_client,
    agency_setup,
    client_setup,
    isolated_db,
):
    """F12-6: Portal project overview aggregates versions, comments, and unresolved comment counts."""
    with isolated_db() as db:
        proj = Project(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            name="Aggregated Review Project",
            status="in_review",
        )
        db.add(proj)
        db.flush()

        v1 = ReviewVersion(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            version_label="v1.0",
            status="changes_requested",
        )
        v2 = ReviewVersion(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            version_label="v2.0",
            status="in_review",
        )
        db.add_all([v1, v2])

        c1 = VideoComment(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            timestamp_seconds=10.0,
            timecode="00:00:10:00",
            content="Note 1",
            status="resolved",
        )
        c2 = VideoComment(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            timestamp_seconds=20.0,
            timecode="00:00:20:00",
            content="Note 2",
            status="submitted",
        )
        c3 = VideoComment(
            workspace_id=agency_setup["workspace_id"],
            client_id=client_setup["client_id"],
            project_id=proj.id,
            timestamp_seconds=30.0,
            timecode="00:00:30:00",
            content="Note 3",
            status="processing",
        )
        db.add_all([c1, c2, c3])
        db.commit()
        proj_id = proj.id

    resp = client_user_client.get(f"/api/portal/projects/{proj_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == proj_id
    assert data["comments_count"] == 3
    assert data["unresolved_comments_count"] == 2
    assert len(data["versions"]) >= 2
    assert len(data["comments"]) == 3
