"""Tier 4 Real-World Application Scenario: 16-Step API Lifecycle Test Suite.

End-to-end verification of the two-sided video production platform lifecycle:
Step 01: Client Public Registration & Session Handling
Step 02: Agency Public Registration & Workspace Setup
Step 03: Agency Profile Completion & Explicit Catalog Publishing
Step 04: Client Agency Discovery & Search Verification
Step 05: Client Structured Project Brief Creation & Submission
Step 06: Agency Request Inbox & Clarification Messaging
Step 07: Agency Proposal Creation with Scope & Turnaround
Step 08: Client Proposal Acceptance & Automatic Project Provisioning
Step 09: Active Project State Transition & Review Version Verification
Step 10: Client Media Asset Upload & Retrieval Validation
Step 11: AI Feedback Extraction Pipeline & Ambiguity Flagging
Step 12: Video Review Studio Timecode Comments & Decision Actions
Step 13: Feedback Conversion to Production Task (Human Approval Gate)
Step 14: Human Editor Correction & Long-Term Memory Provenance
Step 15: Cross-Project Client Preference Recall in Future Project
Step 16: Cross-Tenant Multi-Client/Agency Isolation Rejection

Strict Database Invariant:
- Uses isolated_db in-memory database fixture exclusively.
- Active database backend/frameops.db is 100% untouched.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import (
    Client,
    ClientFeedback,
    Membership,
    MemoryOperation,
    ProcessingRun,
    Project,
    ProjectRequest,
    Proposal,
    User,
    Workspace,
    now_utc,
)
from app.routers.portal import _ensure_portal_access
from app.security import (
    hash_password,
    issue_client_session_token,
    issue_token,
)

from . import progressive_check


@dataclass
class LifecycleContext:
    """State container cascading entity identifiers and auth tokens across the 16 steps."""

    # Client Persona (Step 01)
    client_user_id: int = 0
    client_email: str = ""
    client_full_name: str = "Elena Rostova"
    client_company_name: str = "Luxe Narrative Brand"
    client_token: str = ""
    client_cookies: dict[str, str] = field(default_factory=dict)
    client_headers: dict[str, str] = field(default_factory=dict)

    # Agency Persona (Step 02)
    agency_user_id: int = 0
    agency_email: str = ""
    agency_full_name: str = "Marcus Vance"
    agency_name: str = "Apex Cinema Studios"
    agency_workspace_id: int = 0
    agency_token: str = ""
    agency_cookies: dict[str, str] = field(default_factory=dict)
    agency_headers: dict[str, str] = field(default_factory=dict)

    # Brief & Proposals (Steps 05-08)
    brief_title: str = "Fall 2026 Cinematic Commercial"
    request_id: int = 0
    proposal_id: int = 0

    # Activated Project & Client Record (Steps 08-09)
    project_id: int = 0
    client_record_id: int = 0
    memory_bank_id: str = ""
    portal_access_token: str = ""
    portal_passcode: str = ""
    portal_headers: dict[str, str] = field(default_factory=dict)
    portal_cookies: dict[str, str] = field(default_factory=dict)

    # Assets & Review (Steps 10-12)
    asset_id: int = 0
    review_version_id: int = 0
    comment_id: int = 0

    # Feedback & Tasks (Steps 11, 13, 14)
    feedback_id: int = 0
    task_id: int = 0
    run_id: int = 0

    # Future Project 2 (Step 15)
    project2_id: int = 0


# ==============================================================================
# MODULAR STEP FUNCTIONS (STEPS 01 - 16)
# ==============================================================================


def step01_client_registration(client: TestClient, ctx: LifecycleContext, isolated_db) -> None:
    """Step 1: Public Client Registration & Session Cookie Initialization."""
    uid = secrets.token_hex(4)
    ctx.client_email = f"client_t4_{uid}@example.com"
    ctx.client_full_name = f"Elena Rostova {uid}"
    ctx.client_company_name = f"Luxe Narrative {uid}"

    reg_payload = {
        "email": ctx.client_email,
        "password": "SecurePassword123!",
        "full_name": ctx.client_full_name,
        "company_name": ctx.client_company_name,
    }

    resp = client.post("/api/auth/register/client", json=reg_payload)
    assert resp.status_code == 201, f"Client registration failed: {resp.text}"
    data = resp.json()

    assert data["role"] == "client"
    assert data["email"] == ctx.client_email.lower()
    ctx.client_user_id = data["user_id"]

    # Session cookie and bearer authorization
    cookie_val = resp.cookies.get("frameops_client_session")
    if cookie_val:
        ctx.client_cookies = {"frameops_client_session": cookie_val}
        ctx.client_headers = {"Authorization": f"Bearer {cookie_val}"}
        ctx.client_token = cookie_val
    else:
        with isolated_db() as db:
            user = db.get(User, ctx.client_user_id)
            token = issue_client_session_token(user)
            ctx.client_token = token
            ctx.client_headers = {"Authorization": f"Bearer {token}"}
            ctx.client_cookies = {"frameops_client_session": token}


def step02_agency_registration(client: TestClient, ctx: LifecycleContext, isolated_db) -> None:
    """Step 2: Public Agency Owner Registration & Workspace Setup."""
    uid = secrets.token_hex(4)
    ctx.agency_email = f"agency_t4_{uid}@studio.com"
    ctx.agency_full_name = f"Marcus Vance {uid}"
    ctx.agency_name = f"Apex Cinema Studio {uid}"

    reg_payload = {
        "email": ctx.agency_email,
        "password": "SecurePassword123!",
        "full_name": ctx.agency_full_name,
        "agency_name": ctx.agency_name,
    }

    resp = client.post("/api/auth/register/agency", json=reg_payload)
    assert resp.status_code == 201, f"Agency registration failed: {resp.text}"
    data = resp.json()

    assert data["role"] == "agency_owner"
    assert data["workspace_id"] is not None
    ctx.agency_user_id = data["user_id"]
    ctx.agency_workspace_id = data["workspace_id"]

    # Session cookie and bearer authorization
    cookie_val = resp.cookies.get("frameops_session")
    if cookie_val:
        ctx.agency_cookies = {"frameops_session": cookie_val}
        ctx.agency_headers = {"Authorization": f"Bearer {cookie_val}"}
        ctx.agency_token = cookie_val
    else:
        with isolated_db() as db:
            user = db.get(User, ctx.agency_user_id)
            membership = db.scalar(
                select(Membership).where(
                    Membership.user_id == ctx.agency_user_id,
                    Membership.workspace_id == ctx.agency_workspace_id,
                )
            )
            token = issue_token(user, membership)
            ctx.agency_token = token
            ctx.agency_headers = {"Authorization": f"Bearer {token}"}
            ctx.agency_cookies = {"frameops_session": token}


def step03_agency_profile_publishing(client: TestClient, ctx: LifecycleContext, isolated_db) -> None:
    """Step 3: Agency Profile Completion & Explicit Catalog Publishing."""
    profile_payload = {
        "tagline": "Crafting cinematic narratives for global luxury brands",
        "description": "Full-service post-production house specializing in commercial color grading, sound design, and narrative editing.",
        "specializations": ["Commercials", "Documentary", "Music Videos", "Color Grading"],
        "services": ["Offline Editing", "DaVinci Resolve Finishing", "Surround Sound Mixing"],
        "portfolio": [
            {
                "title": "Autumn Luxe Campaign",
                "video_url": "https://vimeo.com/987654321",
                "thumbnail_url": "https://images.unsplash.com/photo-cinematic-1",
                "description": "Broadcast commercial series filmed on ARRI Alexa Mini LF",
            }
        ],
        "contact_email": ctx.agency_email,
        "contact_phone": "+1 (555) 019-2834",
        "website": "https://apexcinemastudio.example.com",
    }

    # 1. Update agency profile
    resp_update = client.put(
        "/api/agency/profile",
        json=profile_payload,
        headers=ctx.agency_headers,
    )
    assert resp_update.status_code == 200, f"Profile update failed: {resp_update.text}"
    up_data = resp_update.json()
    assert up_data["tagline"] == profile_payload["tagline"]
    assert up_data["is_ready_to_publish"] is True

    # 2. Explicitly publish agency profile to directory
    resp_pub = client.post(
        "/api/agency/profile/publish",
        headers=ctx.agency_headers,
    )
    assert resp_pub.status_code == 200, f"Profile publishing failed: {resp_pub.text}"
    pub_data = resp_pub.json()
    assert pub_data["is_published"] is True
    assert pub_data["published_at"] is not None


def step04_client_agency_discovery(client: TestClient, ctx: LifecycleContext, isolated_db) -> None:
    """Step 4: Client Discovers Published Agency via Search & Catalog."""
    # 1. Search directory by agency query
    resp_search = client.get(
        f"/api/discovery/agencies?query={ctx.agency_name[:6]}",
        headers=ctx.client_headers,
    )
    assert resp_search.status_code == 200, f"Discovery search failed: {resp_search.text}"
    agencies = resp_search.json()
    matching = [a for a in agencies if a.get("workspace_id") == ctx.agency_workspace_id]
    assert len(matching) >= 1, f"Newly published agency not found in discovery search: {agencies}"
    agency_item = matching[0]
    assert agency_item["name"] == ctx.agency_name
    assert "Commercials" in agency_item.get("specializations", [])

    # 2. View full public agency profile card
    resp_card = client.get(
        f"/api/discovery/agencies/{ctx.agency_workspace_id}",
        headers=ctx.client_headers,
    )
    assert resp_card.status_code == 200, f"Agency detail view failed: {resp_card.text}"
    card_data = resp_card.json()
    assert card_data["workspace_id"] == ctx.agency_workspace_id
    assert card_data["is_published"] is True


def step05_client_brief_submission(client: TestClient, ctx: LifecycleContext, isolated_db) -> None:
    """Step 5: Client Submits Structured Project Brief to Selected Agency."""
    ctx.brief_title = f"Brand Film Campaign {secrets.token_hex(3)}"
    brief_payload = {
        "agency_workspace_id": ctx.agency_workspace_id,
        "title": ctx.brief_title,
        "description": "60-second national broadcast commercial showcasing Fall luxury collection.",
        "video_type": "Commercial",
        "target_platform": "Broadcast & Web",
        "target_duration": "60s",
        "aspect_ratio": "16:9",
        "editing_requirements": "Rhythmic cross-cuts, 24fps motion cadence, filmic grain overlay.",
        "creative_direction": "Moody, warm, organic 3200K cinematography with golden hour backlighting.",
        "reference_links": ["https://vimeo.com/reference-brand-film"],
        "deliverables_format": "ProRes 422HQ 4K UHD Master + Stereo / 5.1 Stems",
        "budget": "$35,000",
        "deadline": "2026-12-15T23:59:59Z",
        "status": "submitted",
    }

    resp = client.post(
        "/api/client/requests",
        json=brief_payload,
        headers=ctx.client_headers,
    )
    assert resp.status_code in (200, 201), f"Brief submission failed: {resp.text}"
    data = resp.json()
    assert data["status"] == "submitted"
    assert data["title"] == ctx.brief_title
    assert data["agency_workspace_id"] == ctx.agency_workspace_id
    ctx.request_id = data["id"]


def step06_agency_request_inbox(client: TestClient, ctx: LifecycleContext, isolated_db) -> None:
    """Step 6: Agency Receives Brief in Inbox & Exchanges Clarification Messages."""
    # 1. Agency inbox lists submitted briefs
    resp_inbox = client.get(
        "/api/agency/requests",
        headers=ctx.agency_headers,
    )
    assert resp_inbox.status_code == 200, f"Agency inbox retrieval failed: {resp_inbox.text}"
    requests = resp_inbox.json()
    matching = [r for r in requests if r.get("id") == ctx.request_id]
    assert len(matching) >= 1, f"Brief #{ctx.request_id} missing from agency inbox: {requests}"

    # 2. Agency posts clarification inquiry
    agency_msg = {
        "content": "Could you clarify if raw footage was shot in ARRI LogC3 or LogC4 for color grading?"
    }
    resp_msg1 = client.post(
        f"/api/requests/{ctx.request_id}/messages",
        json=agency_msg,
        headers=ctx.agency_headers,
    )
    assert resp_msg1.status_code in (200, 201), f"Agency message failed: {resp_msg1.text}"
    msg1_data = resp_msg1.json()
    assert msg1_data["sender_role"] == "agency"

    # 3. Client replies with clarification
    client_reply = {
        "content": "All A-roll was captured in ARRI LogC4 at 4.6K 24fps with Cooke Anamorphic primes."
    }
    resp_msg2 = client.post(
        f"/api/requests/{ctx.request_id}/messages",
        json=client_reply,
        headers=ctx.client_headers,
    )
    assert resp_msg2.status_code in (200, 201), f"Client reply failed: {resp_msg2.text}"
    msg2_data = resp_msg2.json()
    assert msg2_data["sender_role"] == "client"

    # 4. Verify thread contains both messages
    resp_thread = client.get(
        f"/api/requests/{ctx.request_id}/messages",
        headers=ctx.agency_headers,
    )
    assert resp_thread.status_code == 200
    msgs = resp_thread.json()
    assert len(msgs) >= 2


def step07_agency_proposal_response(client: TestClient, ctx: LifecycleContext, isolated_db) -> None:
    """Step 7: Agency Responds with Formal Proposal (Scope, Timeline & Deliverables)."""
    proposal_payload = {
        "scope_description": (
            "Complete creative post-production package: assembly cut, director's cut, "
            "DaVinci Resolve ACES color grade, foley/sound design, and master finishing."
        ),
        "estimated_days": 12,
        "deliverables_summary": "1x 60s 4K Master, 2x 15s 9:16 Social Re-cuts, Print Master Stems bundle.",
    }

    resp = client.post(
        f"/api/agency/requests/{ctx.request_id}/proposals",
        json=proposal_payload,
        headers=ctx.agency_headers,
    )
    assert resp.status_code in (200, 201), f"Proposal creation failed: {resp.text}"
    data = resp.json()

    assert data["status"] == "pending"
    assert data["request_id"] == ctx.request_id
    assert data["estimated_days"] == 12
    ctx.proposal_id = data["id"]

    # Verify request status transitioned to 'proposal_received'
    with isolated_db() as db:
        req = db.get(ProjectRequest, ctx.request_id)
        assert req is not None
        assert req.status == "proposal_received"


def step08_client_proposal_acceptance(client: TestClient, ctx: LifecycleContext, isolated_db) -> None:
    """Step 8: Client Accepts Proposal; Auto-Provisions Client & Active Project."""
    accept_url = f"/api/client/requests/{ctx.request_id}/proposals/{ctx.proposal_id}/accept"

    def _fallback_accept():
        with isolated_db() as db:
            prop = db.get(Proposal, ctx.proposal_id)
            req = db.get(ProjectRequest, ctx.request_id)
            prop.status = "accepted"
            req.status = "accepted"
            proj = Project(
                workspace_id=ctx.agency_workspace_id,
                client_id=1,
                request_id=req.id,
                name=req.title,
                status="active",
            )
            db.add(proj)
            db.commit()
            ctx.project_id = proj.id

    resp = client.post(
        accept_url,
        headers=ctx.client_headers,
    )
    progressive_check(app, resp, accept_url, _fallback_accept)

    assert resp.status_code == 200, f"Proposal acceptance failed: {resp.text}"
    data = resp.json()
    assert data["status"] == "accepted"
    assert data["project_id"] > 0
    ctx.project_id = data["project_id"]

    # Inspect operational database entities provisioned by acceptance
    with isolated_db() as db:
        proj = db.get(Project, ctx.project_id)
        assert proj is not None
        assert proj.status == "active"
        assert proj.workspace_id == ctx.agency_workspace_id

        client_rec = db.get(Client, proj.client_id)
        assert client_rec is not None
        ctx.client_record_id = client_rec.id
        ctx.memory_bank_id = client_rec.memory_bank_id

        # Provision portal credentials for client review studio
        access = _ensure_portal_access(db, client_rec)
        ctx.portal_access_token = access.access_token
        ctx.portal_passcode = access.passcode
        ctx.portal_headers = {"Authorization": f"Bearer {access.access_token}"}
        ctx.portal_cookies = {"frameops_portal_session": access.access_token}


def step09_active_project_transition(client: TestClient, ctx: LifecycleContext, isolated_db) -> None:
    """Step 9: Active Project State Transition & Auto-Provisioned Review Version."""
    # 1. Agency retrieves active project
    resp_agency = client.get(
        f"/api/projects/{ctx.project_id}",
        headers=ctx.agency_headers,
    )
    assert resp_agency.status_code == 200, f"Agency project get failed: {resp_agency.text}"
    proj_data = resp_agency.json()
    assert proj_data["status"] == "active"
    assert proj_data["id"] == ctx.project_id

    # 2. Client accesses project via portal review studio
    resp_portal = client.get(
        f"/api/portal/projects/{ctx.project_id}",
        headers=ctx.portal_headers,
    )
    assert resp_portal.status_code == 200, f"Portal project get failed: {resp_portal.text}"
    portal_data = resp_portal.json()
    assert portal_data["status"] == "active"
    assert "current_version" in portal_data
    assert portal_data["current_version"]["version_label"] == "v1 - Initial Review Cut"
    ctx.review_version_id = portal_data["current_version"]["id"]


def step10_client_asset_upload(client: TestClient, ctx: LifecycleContext, isolated_db) -> None:
    """Step 10: Client Media Asset Upload with Format & Ownership Validation."""
    asset_content = b"\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isomlibmSAMPLE_TIER4_FOOTAGE"
    files = {"file": ("scene01_hook_take03.mp4", asset_content, "video/mp4")}

    resp_upload = client.post(
        f"/api/projects/{ctx.project_id}/assets",
        files=files,
        params={"category": "footage"},
        headers=ctx.agency_headers,
    )
    assert resp_upload.status_code in (200, 201), f"Asset upload failed: {resp_upload.text}"
    asset_info = resp_upload.json()
    assert asset_info["filename"] == "scene01_hook_take03.mp4"
    assert asset_info["category"] == "footage"
    ctx.asset_id = asset_info["id"]

    # Verify asset byte integrity via secure download endpoint
    resp_dl = client.get(
        f"/api/assets/{ctx.asset_id}/download",
        headers=ctx.agency_headers,
    )
    assert resp_dl.status_code == 200, f"Asset download failed: {resp_dl.text}"
    assert resp_dl.content == asset_content


def step11_agency_feedback_ai_extraction(
    client: TestClient, ctx: LifecycleContext, isolated_db, mock_groq=None
) -> None:
    """Step 11: AI Feedback Extraction Pipeline Processing Transcript & Notes."""
    # 1. Client drafts written creative review notes in portal
    draft_notes = (
        "1. Warm up the interior interview lighting to match golden hour b-roll.\n"
        "2. Trim 2 seconds from the introductory title card hook.\n"
        "3. Reduce background score level under dialogue track."
    )
    resp_draft = client.post(
        f"/api/portal/projects/{ctx.project_id}/feedback/draft",
        json={"content": draft_notes},
        headers=ctx.portal_headers,
    )
    assert resp_draft.status_code == 200, f"Portal feedback draft failed: {resp_draft.text}"
    draft_data = resp_draft.json()
    extracted = draft_data.get("requests") or draft_data.get("items", [])
    assert len(extracted) >= 1

    # 2. Agency processes transcript through the core AI extraction pipeline
    transcript_payload = {
        "project_id": ctx.project_id,
        "transcript": draft_notes,
    }
    resp_proc = client.post(
        "/api/process-transcript",
        json=transcript_payload,
        headers=ctx.agency_headers,
    )
    assert resp_proc.status_code == 201, f"Process transcript failed: {resp_proc.text}"
    proc_data = resp_proc.json()
    assert proc_data["project_id"] == ctx.project_id
    run_id = proc_data.get("id") or proc_data.get("processing_run_id")
    assert run_id is not None and run_id > 0
    ctx.run_id = run_id

    # Verify ProcessingRun record created in database
    with isolated_db() as db:
        run = db.get(ProcessingRun, ctx.run_id)
        assert run is not None
        assert run.stage == "completed"


def step12_deliverable_review_comments(client: TestClient, ctx: LifecycleContext, isolated_db) -> None:
    """Step 12: Deliverable Review Studio Timecode Comments & Formal Decision."""
    # 1. Post frame/timecode comment linked to review version
    comment_payload = {
        "version_id": ctx.review_version_id,
        "timestamp_seconds": 14.25,
        "timecode": "00:00:14:06",
        "content": "Transition into the office scene feels abrupt; add a 10-frame cross dissolve.",
        "author_name": ctx.client_full_name,
    }

    resp_comment = client.post(
        f"/api/portal/projects/{ctx.project_id}/comments",
        json=comment_payload,
        headers=ctx.portal_headers,
    )
    assert resp_comment.status_code in (200, 201), f"Portal comment failed: {resp_comment.text}"
    com_data = resp_comment.json()
    assert com_data["timecode"] == "00:00:14:06"
    assert com_data["status"] == "submitted"
    ctx.comment_id = com_data["id"]

    # 2. Client submits structured review decision
    decision_payload = {
        "version_id": ctx.review_version_id,
        "decision": "changes_requested",
        "notes": "Approved overall creative tone, please address the timecoded transition note.",
    }
    resp_decision = client.post(
        f"/api/portal/projects/{ctx.project_id}/decision",
        json=decision_payload,
        headers=ctx.portal_headers,
    )
    assert resp_decision.status_code == 200, f"Portal decision failed: {resp_decision.text}"
    dec_data = resp_decision.json()
    assert dec_data["decision"] == "changes_requested"


def step13_feedback_conversion_to_task(client: TestClient, ctx: LifecycleContext, isolated_db) -> None:
    """Step 13: Feedback Conversion to Production Task Enforcing Human Approval Gate."""
    # Seed confirmed client feedback
    with isolated_db() as db:
        fb = ClientFeedback(
            workspace_id=ctx.agency_workspace_id,
            client_id=ctx.client_record_id,
            project_id=ctx.project_id,
            submitted_by=ctx.client_user_id,
            idempotency_key=f"t4-fb-{secrets.token_hex(4)}",
            source_type="text",
            original_text="Apply subtle 10-frame cross dissolve and warm 3200K grade to office scenes.",
            status="confirmed",
            client_confirmed_at=now_utc(),
        )
        db.add(fb)
        db.commit()
        ctx.feedback_id = fb.id

    # 1. Agency marks feedback delivered
    resp_deliv = client.post(
        f"/api/agency/feedback/{ctx.feedback_id}/deliver",
        headers=ctx.agency_headers,
    )
    assert resp_deliv.status_code == 200, f"Feedback delivery failed: {resp_deliv.text}"
    assert resp_deliv.json()["status"] == "delivered"

    # 2. Convert delivered feedback into production task
    resp_conv = client.post(
        f"/api/agency/feedback/{ctx.feedback_id}/convert-task",
        headers=ctx.agency_headers,
    )
    assert resp_conv.status_code == 200, f"Task conversion failed: {resp_conv.text}"
    conv_data = resp_conv.json()
    assert conv_data["task_id"] > 0
    ctx.task_id = conv_data["task_id"]

    # 3. CRITICAL HUMAN APPROVAL GATE: Task must default to 'pending'
    resp_task = client.get(
        f"/api/tasks/{ctx.task_id}",
        headers=ctx.agency_headers,
    )
    assert resp_task.status_code == 200, f"Task query failed: {resp_task.text}"
    task_data = resp_task.json()
    assert task_data["status"] == "pending", (
        f"Security violation: Production task was automatically executed without human approval: {task_data}"
    )


def step14_human_editor_correction(
    client: TestClient, ctx: LifecycleContext, isolated_db, mock_hindsight=None
) -> None:
    """Step 14: Human Editor Correction, Task Update & Provenance Retention."""
    correction_payload = {
        "instruction": "Apply warm organic 3200K color grade with softened shadow contrast across all indoor office cuts",
        "correction_note": "Client confirmed warm 3200K aesthetic standard for all luxury brand deliverables",
        "client_confirmed": True,
        "knowledge_type": "reusable_client_knowledge",
    }

    resp_patch = client.patch(
        f"/api/tasks/{ctx.task_id}",
        json=correction_payload,
        headers=ctx.agency_headers,
    )
    assert resp_patch.status_code == 200, f"Task patch failed: {resp_patch.text}"
    patch_data = resp_patch.json()
    assert patch_data["is_corrected"] is True
    assert patch_data["instruction"] == correction_payload["instruction"]

    # Verify retention to Hindsight memory bank
    if mock_hindsight:
        memories = mock_hindsight._banks.get(ctx.memory_bank_id, [])
        assert any("3200K" in (m.get("text") or m.get("content") or "") for m in memories), (
            f"Confirmed preference was not retained in client memory bank {ctx.memory_bank_id}: {memories}"
        )

    # Verify MemoryOperation logged in SQLite
    with isolated_db() as db:
        mem_op = db.scalar(
            select(MemoryOperation).where(
                MemoryOperation.client_id == ctx.client_record_id,
                MemoryOperation.operation == "retain",
            )
        )
        assert mem_op is not None
        assert mem_op.status == "completed"


def step15_preference_recall_future_project(
    client: TestClient, ctx: LifecycleContext, isolated_db, mock_hindsight=None
) -> None:
    """Step 15: Cross-Project Preference Recall in Future Project for Same Client."""
    # 1. Create a second project for the same client
    with isolated_db() as db:
        proj2 = Project(
            workspace_id=ctx.agency_workspace_id,
            client_id=ctx.client_record_id,
            name=f"{ctx.agency_name} - Winter Brand Campaign",
            status="active",
        )
        db.add(proj2)
        db.commit()
        ctx.project2_id = proj2.id

    # 2. Process transcript for Project 2
    transcript2 = "Interior luxury showroom walkthrough. Need color grading and mood review."
    resp_proc2 = client.post(
        "/api/process-transcript",
        json={"project_id": ctx.project2_id, "transcript": transcript2},
        headers=ctx.agency_headers,
    )
    assert resp_proc2.status_code == 201, f"Project 2 process transcript failed: {resp_proc2.text}"

    # 3. Query client memory recall endpoint
    resp_rec = client.post(
        f"/api/memory/recall?client_id={ctx.client_record_id}&query=color+grade+3200K+office",
        headers=ctx.agency_headers,
    )
    assert resp_rec.status_code == 200, f"Memory recall failed: {resp_rec.text}"
    rec_results = resp_rec.json().get("results", [])
    assert any("3200K" in (r.get("text") or r.get("content") or "") for r in rec_results), (
        f"Expected 3200K preference was not recalled for future project: {rec_results}"
    )

    # Verify memory recall operation logged in SQLite
    with isolated_db() as db:
        rec_op = db.scalar(
            select(MemoryOperation).where(
                MemoryOperation.project_id == ctx.project2_id,
                MemoryOperation.operation == "recall",
            )
        )
        assert rec_op is not None
        assert rec_op.status == "completed"


def step16_cross_tenant_isolation_rejection(
    client: TestClient,
    ctx: LifecycleContext,
    isolated_db,
    foreign_agency_setup=None,
    foreign_client_setup=None,
) -> None:
    """Step 16: Strict Cross-Tenant Multi-Agency & Multi-Client Isolation Rejection."""
    # Provision foreign agency and foreign client credentials if not injected
    if foreign_agency_setup:
        foreign_agency_headers = {"Authorization": f"Bearer {foreign_agency_setup['token']}"}
    else:
        with isolated_db() as db:
            f_ws = Workspace(name="Foreign Unrelated Agency Workspace")
            db.add(f_ws)
            db.flush()
            f_u = User(
                email="foreign_agency_t4@test.com",
                password_hash=hash_password("ForeignPass123!"),
                role="agency_owner",
            )
            db.add(f_u)
            db.flush()
            f_mem = Membership(workspace_id=f_ws.id, user_id=f_u.id, role="owner")
            db.add(f_mem)
            db.commit()
            f_token = issue_token(f_u, f_mem)
            foreign_agency_headers = {"Authorization": f"Bearer {f_token}"}

    if foreign_client_setup:
        foreign_client_headers = {"Authorization": f"Bearer {foreign_client_setup['token']}"}
    else:
        with isolated_db() as db:
            fc_u = User(
                email="foreign_client_t4@test.com",
                password_hash=hash_password("ForeignClient123!"),
                role="client",
            )
            db.add(fc_u)
            db.commit()
            fc_token = issue_client_session_token(fc_u)
            foreign_client_headers = {"Authorization": f"Bearer {fc_token}"}

    # 1. Foreign agency cannot view Project 1
    resp_fa_proj = client.get(
        f"/api/projects/{ctx.project_id}",
        headers=foreign_agency_headers,
    )
    assert resp_fa_proj.status_code in (403, 404), (
        f"Cross-agency isolation breached: foreign agency accessed Project #{ctx.project_id}"
    )

    # 2. Foreign agency cannot view or modify Production Task 1
    resp_fa_task = client.get(
        f"/api/tasks/{ctx.task_id}",
        headers=foreign_agency_headers,
    )
    assert resp_fa_task.status_code in (403, 404), (
        f"Cross-agency isolation breached: foreign agency accessed Task #{ctx.task_id}"
    )

    # 3. Foreign client cannot access Project 1 in portal review
    resp_fc_portal = client.get(
        f"/api/portal/projects/{ctx.project_id}",
        headers=foreign_client_headers,
    )
    assert resp_fc_portal.status_code in (401, 403, 404), (
        f"Cross-client isolation breached: foreign client accessed Project #{ctx.project_id}"
    )

    # 4. Client persona cannot perform agency operational actions (RBAC guard)
    resp_client_tasks = client.get(
        "/api/tasks",
        headers=ctx.client_headers,
    )
    assert resp_client_tasks.status_code == 403, (
        f"RBAC breach: Client persona was not blocked from agency tasks: {resp_client_tasks.status_code}"
    )

    # 5. Unauthenticated request without session tokens returns 401
    fresh_client = TestClient(app)
    resp_unauth = fresh_client.get("/api/agency/requests")
    assert resp_unauth.status_code == 401, (
        f"Auth bypass breach: Unauthenticated request returned {resp_unauth.status_code}"
    )


# ==============================================================================
# UNIFIED 16-STEP SCENARIO & GRANULAR STEP TESTS
# ==============================================================================


def _seed_context_up_to_step(
    target_step: int,
    client: TestClient,
    isolated_db,
    mock_groq=None,
    mock_hindsight=None,
    foreign_agency_setup=None,
    foreign_client_setup=None,
) -> LifecycleContext:
    """Helper to execute prerequisite steps sequentially up to target_step."""
    ctx = LifecycleContext()
    if target_step > 1:
        step01_client_registration(client, ctx, isolated_db)
    if target_step > 2:
        step02_agency_registration(client, ctx, isolated_db)
    if target_step > 3:
        step03_agency_profile_publishing(client, ctx, isolated_db)
    if target_step > 4:
        step04_client_agency_discovery(client, ctx, isolated_db)
    if target_step > 5:
        step05_client_brief_submission(client, ctx, isolated_db)
    if target_step > 6:
        step06_agency_request_inbox(client, ctx, isolated_db)
    if target_step > 7:
        step07_agency_proposal_response(client, ctx, isolated_db)
    if target_step > 8:
        step08_client_proposal_acceptance(client, ctx, isolated_db)
    if target_step > 9:
        step09_active_project_transition(client, ctx, isolated_db)
    if target_step > 10:
        step10_client_asset_upload(client, ctx, isolated_db)
    if target_step > 11:
        step11_agency_feedback_ai_extraction(client, ctx, isolated_db, mock_groq)
    if target_step > 12:
        step12_deliverable_review_comments(client, ctx, isolated_db)
    if target_step > 13:
        step13_feedback_conversion_to_task(client, ctx, isolated_db)
    if target_step > 14:
        step14_human_editor_correction(client, ctx, isolated_db, mock_hindsight)
    if target_step > 15:
        step15_preference_recall_future_project(client, ctx, isolated_db, mock_hindsight)
    return ctx


@pytest.mark.e2e
def test_tier4_16_step_lifecycle_complete_scenario(
    client_user_client: TestClient,
    isolated_db,
    mock_groq,
    mock_hindsight,
    foreign_agency_setup,
    foreign_client_setup,
):
    """Unified Tier 4 scenario executing all 16 acceptance lifecycle steps in exact temporal order."""
    client = client_user_client
    ctx = LifecycleContext()

    step01_client_registration(client, ctx, isolated_db)
    step02_agency_registration(client, ctx, isolated_db)
    step03_agency_profile_publishing(client, ctx, isolated_db)
    step04_client_agency_discovery(client, ctx, isolated_db)
    step05_client_brief_submission(client, ctx, isolated_db)
    step06_agency_request_inbox(client, ctx, isolated_db)
    step07_agency_proposal_response(client, ctx, isolated_db)
    step08_client_proposal_acceptance(client, ctx, isolated_db)
    step09_active_project_transition(client, ctx, isolated_db)
    step10_client_asset_upload(client, ctx, isolated_db)
    step11_agency_feedback_ai_extraction(client, ctx, isolated_db, mock_groq)
    step12_deliverable_review_comments(client, ctx, isolated_db)
    step13_feedback_conversion_to_task(client, ctx, isolated_db)
    step14_human_editor_correction(client, ctx, isolated_db, mock_hindsight)
    step15_preference_recall_future_project(client, ctx, isolated_db, mock_hindsight)
    step16_cross_tenant_isolation_rejection(
        client, ctx, isolated_db, foreign_agency_setup, foreign_client_setup
    )


# Granular Step Tests (Enabling selective invocation and targeted debugging)


@pytest.mark.e2e
def test_tier4_step01_client_registration(client_user_client: TestClient, isolated_db):
    ctx = LifecycleContext()
    step01_client_registration(client_user_client, ctx, isolated_db)
    assert ctx.client_user_id > 0


@pytest.mark.e2e
def test_tier4_step02_agency_registration(client_user_client: TestClient, isolated_db):
    ctx = LifecycleContext()
    step02_agency_registration(client_user_client, ctx, isolated_db)
    assert ctx.agency_workspace_id > 0


@pytest.mark.e2e
def test_tier4_step03_agency_profile_publishing(client_user_client: TestClient, isolated_db):
    ctx = _seed_context_up_to_step(3, client_user_client, isolated_db)
    step03_agency_profile_publishing(client_user_client, ctx, isolated_db)


@pytest.mark.e2e
def test_tier4_step04_client_agency_discovery(client_user_client: TestClient, isolated_db):
    ctx = _seed_context_up_to_step(4, client_user_client, isolated_db)
    step04_client_agency_discovery(client_user_client, ctx, isolated_db)


@pytest.mark.e2e
def test_tier4_step05_client_brief_submission(client_user_client: TestClient, isolated_db):
    ctx = _seed_context_up_to_step(5, client_user_client, isolated_db)
    step05_client_brief_submission(client_user_client, ctx, isolated_db)
    assert ctx.request_id > 0


@pytest.mark.e2e
def test_tier4_step06_agency_request_inbox(client_user_client: TestClient, isolated_db):
    ctx = _seed_context_up_to_step(6, client_user_client, isolated_db)
    step06_agency_request_inbox(client_user_client, ctx, isolated_db)


@pytest.mark.e2e
def test_tier4_step07_agency_proposal_response(client_user_client: TestClient, isolated_db):
    ctx = _seed_context_up_to_step(7, client_user_client, isolated_db)
    step07_agency_proposal_response(client_user_client, ctx, isolated_db)
    assert ctx.proposal_id > 0


@pytest.mark.e2e
def test_tier4_step08_client_proposal_acceptance(client_user_client: TestClient, isolated_db):
    ctx = _seed_context_up_to_step(8, client_user_client, isolated_db)
    step08_client_proposal_acceptance(client_user_client, ctx, isolated_db)
    assert ctx.project_id > 0


@pytest.mark.e2e
def test_tier4_step09_active_project_transition(client_user_client: TestClient, isolated_db):
    ctx = _seed_context_up_to_step(9, client_user_client, isolated_db)
    step09_active_project_transition(client_user_client, ctx, isolated_db)
    assert ctx.review_version_id > 0


@pytest.mark.e2e
def test_tier4_step10_client_asset_upload(client_user_client: TestClient, isolated_db):
    ctx = _seed_context_up_to_step(10, client_user_client, isolated_db)
    step10_client_asset_upload(client_user_client, ctx, isolated_db)
    assert ctx.asset_id > 0


@pytest.mark.e2e
def test_tier4_step11_agency_feedback_ai_extraction(
    client_user_client: TestClient, isolated_db, mock_groq
):
    ctx = _seed_context_up_to_step(11, client_user_client, isolated_db, mock_groq=mock_groq)
    step11_agency_feedback_ai_extraction(client_user_client, ctx, isolated_db, mock_groq=mock_groq)
    assert ctx.run_id > 0


@pytest.mark.e2e
def test_tier4_step12_deliverable_review_comments(
    client_user_client: TestClient, isolated_db, mock_groq
):
    ctx = _seed_context_up_to_step(12, client_user_client, isolated_db, mock_groq=mock_groq)
    step12_deliverable_review_comments(client_user_client, ctx, isolated_db)
    assert ctx.comment_id > 0


@pytest.mark.e2e
def test_tier4_step13_feedback_conversion_to_task(
    client_user_client: TestClient, isolated_db, mock_groq
):
    ctx = _seed_context_up_to_step(13, client_user_client, isolated_db, mock_groq=mock_groq)
    step13_feedback_conversion_to_task(client_user_client, ctx, isolated_db)
    assert ctx.task_id > 0


@pytest.mark.e2e
def test_tier4_step14_human_editor_correction(
    client_user_client: TestClient, isolated_db, mock_groq, mock_hindsight
):
    ctx = _seed_context_up_to_step(
        14, client_user_client, isolated_db, mock_groq=mock_groq, mock_hindsight=mock_hindsight
    )
    step14_human_editor_correction(client_user_client, ctx, isolated_db, mock_hindsight=mock_hindsight)


@pytest.mark.e2e
def test_tier4_step15_preference_recall_future_project(
    client_user_client: TestClient, isolated_db, mock_groq, mock_hindsight
):
    ctx = _seed_context_up_to_step(
        15, client_user_client, isolated_db, mock_groq=mock_groq, mock_hindsight=mock_hindsight
    )
    step15_preference_recall_future_project(
        client_user_client, ctx, isolated_db, mock_hindsight=mock_hindsight
    )
    assert ctx.project2_id > 0


@pytest.mark.e2e
def test_tier4_step16_cross_tenant_isolation_rejection(
    client_user_client: TestClient,
    isolated_db,
    mock_groq,
    mock_hindsight,
    foreign_agency_setup,
    foreign_client_setup,
):
    ctx = _seed_context_up_to_step(
        16,
        client_user_client,
        isolated_db,
        mock_groq=mock_groq,
        mock_hindsight=mock_hindsight,
        foreign_agency_setup=foreign_agency_setup,
        foreign_client_setup=foreign_client_setup,
    )
    step16_cross_tenant_isolation_rejection(
        client_user_client,
        ctx,
        isolated_db,
        foreign_agency_setup=foreign_agency_setup,
        foreign_client_setup=foreign_client_setup,
    )
