from datetime import UTC, datetime
import json
import logging
import mimetypes
import os
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, File, Header, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import (
    Asset,
    Client,
    ClientFeedbackSubmission,
    ClientPortalAccess,
    MemoryOperation,
    Project,
    ReviewVersion,
    VideoComment,
    now_utc,
)
from ..schemas import (
    PortalCommentInput,
    PortalDecisionInput,
    PortalDraftInput,
    PortalFeedbackSubmitInput,
    PortalLoginInput,
)
from ..security import (
    current_client_identity,
    current_identity,
    hash_password,
    issue_client_token,
    verify_password,
)
from ..services import groq

log = logging.getLogger('frameops')
router = APIRouter(tags=['Client Portal'])

# CLIENT PORTAL HELPERS & ENDPOINTS
# ==============================================================================

def _get_client(db: Session, client_id: int, workspace_id: int) -> Client:
    item = db.scalar(select(Client).where(Client.id == client_id, Client.workspace_id == workspace_id))
    if not item:
        raise HTTPException(404, "Client not found")
    return item


def _get_project(db: Session, project_id: int, workspace_id: int) -> Project:
    item = db.scalar(select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id))
    if not item:
        raise HTTPException(404, "Project not found")
    return item


def _remember_op(db: Session, *, workspace_id: int, client_id: int, project_id: int | None,
                 run_id: int | None, operation: str, status: str, key: str, details: str = "",
                 provenance: str = "") -> MemoryOperation:
    row = MemoryOperation(workspace_id=workspace_id, client_id=client_id, project_id=project_id,
                          run_id=run_id, operation=operation, status=status, idempotency_key=key,
                          details=details[:8000], provenance=provenance)
    db.add(row)
    return row


def _ensure_portal_access(db: Session, client: Client) -> ClientPortalAccess:
    access = db.scalar(select(ClientPortalAccess).where(ClientPortalAccess.client_id == client.id))
    if not access:
        token = f"portal-{client.id}-{uuid4().hex}"
        passcode = f"{client.name[:4].strip().upper() or 'CLNT'}-{uuid4().hex[:6].upper()}"
        access = ClientPortalAccess(
            workspace_id=client.workspace_id,
            client_id=client.id,
            access_token=token,
            passcode=passcode,
            client_email="",
        )
        db.add(access)
        db.commit()
        db.refresh(access)
    return access


def _ensure_review_version(db: Session, project: Project) -> ReviewVersion:
    version = db.scalar(
        select(ReviewVersion).where(ReviewVersion.project_id == project.id).order_by(ReviewVersion.created_at.desc())
    )
    if not version:
        # Check if project already has a video asset
        video_asset = db.scalar(
            select(Asset).where(
                Asset.project_id == project.id,
                (Asset.content_type.like("video/%")) | (Asset.category.in_(["footage", "review_video", "deliverable"]))
            ).order_by(Asset.created_at.desc())
        )
        version = ReviewVersion(
            workspace_id=project.workspace_id,
            client_id=project.client_id,
            project_id=project.id,
            version_label="v1 - Initial Review Cut",
            video_asset_id=video_asset.id if video_asset else None,
            video_url=f"/api/portal/assets/{video_asset.id}/stream" if video_asset else "",
            status="in_review",
            change_summary="Initial delivery for client creative review and feedback.",
        )
        db.add(version)
        db.commit()
        db.refresh(version)
    return version


def _get_portal_project(db: Session, project_id: int, client_id: int, workspace_id: int) -> Project:
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.client_id == client_id,
            Project.workspace_id == workspace_id,
        )
    )
    if not project:
        raise HTTPException(404, "Project not found or not assigned to your client account")
    return project


def _review_version_dict(v: ReviewVersion) -> dict:
    return {
        "id": v.id,
        "project_id": v.project_id,
        "version_label": v.version_label,
        "video_asset_id": v.video_asset_id,
        "video_url": v.video_url,
        "status": v.status,
        "change_summary": v.change_summary,
        "created_at": v.created_at.isoformat(),
    }


def _comment_dict(c: VideoComment) -> dict:
    return {
        "id": c.id,
        "project_id": c.project_id,
        "review_version_id": c.review_version_id,
        "timestamp_seconds": c.timestamp_seconds,
        "timecode": c.timecode,
        "author_name": c.author_name,
        "content": c.content,
        "status": c.status,
        "created_at": c.created_at.isoformat(),
    }


def _submission_dict(s: ClientFeedbackSubmission) -> dict:
    parsed_items = []
    if s.structured_data:
        try:
            parsed_items = json.loads(s.structured_data)
        except Exception:
            parsed_items = []
    return {
        "id": s.id,
        "project_id": s.project_id,
        "review_version_id": s.review_version_id,
        "feedback_type": s.feedback_type,
        "author_name": s.author_name,
        "content": s.content,
        "items": parsed_items,
        "audio_asset_id": s.audio_asset_id,
        "status": s.status,
        "review_decision": s.review_decision,
        "created_at": s.created_at.isoformat(),
    }


def _portal_project_dict(p: Project, db: Session) -> dict:
    latest_version = _ensure_review_version(db, p)
    submissions_count = db.query(ClientFeedbackSubmission).filter_by(project_id=p.id).count()
    comments_count = db.query(VideoComment).filter_by(project_id=p.id).count()
    unresolved_comments = db.query(VideoComment).filter(
        VideoComment.project_id == p.id,
        VideoComment.status != "resolved"
    ).count()

    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "status": p.status,
        "due_date": p.due_date.isoformat() if p.due_date else None,
        "created_at": p.created_at.isoformat(),
        "client_name": p.client.name if p.client else "",
        "brand": p.client.brand if p.client else "",
        "current_version": _review_version_dict(latest_version),
        "submissions_count": submissions_count,
        "comments_count": comments_count,
        "unresolved_comments_count": unresolved_comments,
    }


def _set_portal_cookie(response: Response, token: str):
    response.set_cookie(
        "frameops_portal_session",
        token,
        max_age=30 * 24 * 3600,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


# --- Agency View: Client Portal Link Generation ---

@router.get("/api/clients/{client_id}/portal-access")
def get_client_portal_access(client_id: int, db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    client = _get_client(db, client_id, wid)
    access = _ensure_portal_access(db, client)
    return {
        "client_id": client.id,
        "client_name": client.name,
        "access_token": access.access_token,
        "passcode": access.passcode,
        "portal_path": f"/portal?token={access.access_token}",
        "last_accessed_at": access.last_accessed_at.isoformat() if access.last_accessed_at else None,
    }


# --- Client Authentication ---

@router.post("/api/portal/auth/login")
def portal_login(data: PortalLoginInput, response: Response, db: Session = Depends(get_db)):
    if not data.token and not data.code:
        raise HTTPException(401, "Passcode or access token is required")

    access = None
    if data.token:
        access = db.scalar(select(ClientPortalAccess).where(ClientPortalAccess.access_token == data.token.strip()))
    elif data.code:
        input_code = data.code.strip()
        candidates = db.scalars(select(ClientPortalAccess)).all()
        for cand in candidates:
            if cand.passcode.startswith("$"):
                try:
                    if verify_password(input_code, cand.passcode):
                        access = cand
                        break
                except Exception:
                    pass
            elif cand.passcode.upper() == input_code.upper():
                access = cand
                break

    if not access:
        raise HTTPException(401, "Invalid client portal access token or code")

    if not getattr(access, "is_active", True):
        raise HTTPException(401, "Client portal access has been revoked or is inactive")

    expires_at = getattr(access, "expires_at", None)
    if expires_at:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < now_utc():
            raise HTTPException(401, "Client portal access token has expired")

    client = db.get(Client, access.client_id)
    if not client:
        raise HTTPException(404, "Client record does not exist")

    token = issue_client_token(client)
    _set_portal_cookie(response, token)
    access.last_accessed_at = now_utc()
    db.commit()

    return {
        "token": token,
        "client": {
            "id": client.id,
            "name": client.name,
            "brand": client.brand,
            "industry": client.industry,
            "description": client.description,
        },
        "workspace_id": client.workspace_id,
    }


@router.get("/api/portal/auth/me")
def portal_me(client_identity=Depends(current_client_identity), db: Session = Depends(get_db)):
    client, wid = client_identity
    access = _ensure_portal_access(db, client)
    projects_count = db.query(Project).filter_by(client_id=client.id, workspace_id=wid).count()
    return {
        "client": {
            "id": client.id,
            "name": client.name,
            "brand": client.brand,
            "industry": client.industry,
            "description": client.description,
        },
        "access_code": access.passcode,
        "projects_count": projects_count,
        "workspace_id": wid,
    }


@router.post("/api/portal/auth/logout")
def portal_logout(response: Response):
    response.delete_cookie(
        "frameops_portal_session",
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )
    return {"logged_out": True}


# --- Client Project Overview & Details ---

@router.get("/api/portal/projects")
def portal_list_projects(
    db: Session = Depends(get_db),
    client_identity=Depends(current_client_identity),
):
    client, wid = client_identity
    projects = db.scalars(
        select(Project).where(
            Project.client_id == client.id,
            Project.workspace_id == wid,
        ).order_by(Project.created_at.desc())
    ).all()
    return [_portal_project_dict(p, db) for p in projects]


@router.get("/api/portal/projects/{project_id}")
def portal_get_project(
    project_id: int,
    db: Session = Depends(get_db),
    client_identity=Depends(current_client_identity),
):
    client, wid = client_identity
    project = _get_portal_project(db, project_id, client.id, wid)
    base = _portal_project_dict(project, db)

    # All versions
    versions = db.scalars(
        select(ReviewVersion).where(
            ReviewVersion.project_id == project.id,
            ReviewVersion.workspace_id == wid,
        ).order_by(ReviewVersion.created_at.desc())
    ).all()

    # Timestamped video comments
    comments = db.scalars(
        select(VideoComment).where(
            VideoComment.project_id == project.id,
            VideoComment.workspace_id == wid,
        ).order_by(VideoComment.timestamp_seconds.asc())
    ).all()

    # Feedback submissions
    submissions = db.scalars(
        select(ClientFeedbackSubmission).where(
            ClientFeedbackSubmission.project_id == project.id,
            ClientFeedbackSubmission.workspace_id == wid,
        ).order_by(ClientFeedbackSubmission.created_at.desc())
    ).all()

    # Video/Media assets available
    assets = db.scalars(
        select(Asset).where(
            Asset.project_id == project.id,
            Asset.workspace_id == wid,
        ).order_by(Asset.created_at.desc())
    ).all()

    return {
        **base,
        "versions": [_review_version_dict(v) for v in versions],
        "comments": [_comment_dict(c) for c in comments],
        "feedback_submissions": [_submission_dict(s) for s in submissions],
        "assets": [
            {
                "id": a.id,
                "filename": a.filename,
                "category": a.category,
                "content_type": a.content_type,
                "size_bytes": a.size_bytes,
                "stream_url": f"/api/portal/assets/{a.id}/stream",
                "created_at": a.created_at.isoformat(),
            }
            for a in assets
        ],
    }


# --- AI-Structured Feedback Review Screen (Draft Extraction) ---

@router.post("/api/portal/projects/{project_id}/feedback/draft")
async def draft_portal_feedback(
    project_id: int,
    data: PortalDraftInput,
    db: Session = Depends(get_db),
    client_identity=Depends(current_client_identity),
):
    client, wid = client_identity
    _get_portal_project(db, project_id, client.id, wid)

    items = []
    ambiguities = []
    risks = []
    missing = []
    summary = ""

    # 1. Try Groq structured feedback extraction if configured
    if settings.groq_api_key and settings.groq_model:
        try:
            extraction = await groq.extract_feedback(data.content)
            for req in extraction.requests:
                items.append({
                    "id": uuid4().hex[:8],
                    "description": req.description,
                    "category": req.category,
                    "classification": req.classification,
                    "confidence": req.confidence,
                    "requires_confirmation": req.requires_confirmation,
                    "client_confirmed": False,
                    "actionable_cut_note": f"Apply to next cut: {req.description}",
                })
            ambiguities = extraction.ambiguities
            risks = extraction.production_risks
            missing = extraction.missing_information
            summary = f"Extracted {len(items)} actionable items from your creative feedback."
        except Exception as e:
            log.warning("Groq extraction fallback used for client portal draft: %s", e)
            items = []

    # 2. Intelligent fallback parser if Groq was not reachable or had no items
    if not items:
        raw_lines = [line.strip("- *0123456789. ") for line in data.content.split("\n") if len(line.strip()) > 3]
        if not raw_lines:
            raw_lines = [data.content.strip()]

        for idx, line in enumerate(raw_lines[:15]):
            lower = line.lower()
            cat = "General"
            if any(w in lower for w in ["pace", "slow", "fast", "speed", "timing", "cut", "trim", "transition"]):
                cat = "Pacing & Editing"
            elif any(w in lower for w in ["color", "grade", "dark", "bright", "lut", "saturation", "tint", "contrast"]):
                cat = "Color & Grade"
            elif any(w in lower for w in ["audio", "music", "track", "sound", "voice", "mix", "volume", "dialogue", "sfx"]):
                cat = "Audio & Sound"
            elif any(w in lower for w in ["graphic", "title", "font", "lower third", "text", "logo", "caption"]):
                cat = "Graphics & Titles"
            elif any(w in lower for w in ["story", "hook", "intro", "outro", "cta", "message", "script", "scene"]):
                cat = "Story & Structure"

            is_ambiguous = any(
                w in lower for w in ["maybe", "perhaps", "feel", "pop", "vibe", "punchy", "something like", "better", "not sure"]
            )
            items.append({
                "id": uuid4().hex[:8],
                "description": line,
                "category": cat,
                "classification": "explicit" if not is_ambiguous else "inferred",
                "confidence": 0.95 if not is_ambiguous else 0.65,
                "requires_confirmation": is_ambiguous,
                "client_confirmed": False,
                "actionable_cut_note": f"Production note: {line}",
            })
            if is_ambiguous:
                ambiguities.append(f"Ambiguity detected in note #{idx+1}: “{line}”. Consider clarifying specific timing or style.")

        summary = f"Structured {len(items)} actionable creative requirements for editor review."

    return {
        "summary": summary,
        "requests": items,
        "ambiguities": ambiguities,
        "missing_information": missing,
        "production_risks": risks,
    }


# --- Submit Confirmed / Edited Feedback ---

@router.post("/api/portal/projects/{project_id}/feedback/submit", status_code=201)
async def submit_portal_feedback(
    project_id: int,
    data: PortalFeedbackSubmitInput,
    db: Session = Depends(get_db),
    client_identity=Depends(current_client_identity),
):
    client, wid = client_identity
    project = _get_portal_project(db, project_id, client.id, wid)

    structured_json = json.dumps([item.model_dump() for item in data.items])

    submission = ClientFeedbackSubmission(
        workspace_id=wid,
        client_id=client.id,
        project_id=project.id,
        review_version_id=data.version_id,
        feedback_type=data.feedback_type,
        author_name=data.author_name or client.name,
        content=data.content,
        structured_data=structured_json,
        audio_asset_id=data.audio_asset_id,
        status="submitted",
    )
    db.add(submission)

    # Advance project status to in_review if active
    if project.status == "active":
        project.status = "in_review"

    if data.version_id:
        v = db.scalar(
            select(ReviewVersion).where(
                ReviewVersion.id == data.version_id,
                ReviewVersion.project_id == project.id,
            )
        )
        if v:
            v.status = "changes_requested"

    # Only retain explicitly client-confirmed preferences
    confirmed_items = [it for it in data.items if it.client_confirmed]
    for confirmed_item in confirmed_items:
        mem_key = f"portal-feedback:{uuid4().hex[:12]}"
        _remember_op(
            db,
            workspace_id=wid,
            client_id=client.id,
            project_id=project.id,
            run_id=None,
            operation="retain",
            status="completed",
            key=mem_key,
            details=f"Client confirmed preference: {confirmed_item.description}",
            provenance="client_confirmed",
        )

    db.commit()
    db.refresh(submission)
    return _submission_dict(submission)


# --- Voice Feedback Audio Upload ---

@router.post("/api/portal/projects/{project_id}/voice", status_code=201)
async def upload_portal_voice(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    client_identity=Depends(current_client_identity),
):
    client, wid = client_identity
    project = _get_portal_project(db, project_id, client.id, wid)

    safe_name = Path(file.filename or "voice_feedback.webm").name[:255]
    content = await file.read(settings.max_upload_bytes + 1)
    if not content or len(content) > settings.max_upload_bytes:
        raise HTTPException(413, "Voice audio file is empty or exceeds the upload size limit")

    content_type = file.content_type or mimetypes.guess_type(safe_name)[0] or "audio/webm"
    allowed_audio = {
        "audio/mpeg", "audio/wav", "audio/x-wav", "audio/webm", "audio/ogg",
        "audio/aac", "audio/mp4", "audio/x-m4a", "video/webm", "application/octet-stream"
    }
    if content_type not in allowed_audio:
        raise HTTPException(415, "Unsupported audio recording format")

    folder = Path(settings.upload_dir).resolve() / str(wid) / str(project.id)
    folder.mkdir(parents=True, exist_ok=True)
    storage_key = f"{wid}/{project.id}/{uuid4().hex}"
    destination = folder / storage_key.split("/")[-1]
    destination.write_bytes(content)

    # Use first owner user id or dummy for created_by
    first_member = db.scalar(select(Membership).where(Membership.workspace_id == wid))
    creator_id = first_member.user_id if first_member else 1

    asset = Asset(
        workspace_id=wid,
        client_id=client.id,
        project_id=project.id,
        filename=safe_name,
        category="voice_feedback",
        content_type=content_type,
        size_bytes=len(content),
        storage_key=str(destination),
        created_by=creator_id,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    return {
        "asset_id": asset.id,
        "filename": asset.filename,
        "category": asset.category,
        "size_bytes": asset.size_bytes,
        "stream_url": f"/api/portal/assets/{asset.id}/stream",
    }


# --- Video Review: Timestamped Comments ---

@router.get("/api/portal/projects/{project_id}/comments")
def list_portal_comments(
    project_id: int,
    db: Session = Depends(get_db),
    client_identity=Depends(current_client_identity),
):
    client, wid = client_identity
    project = _get_portal_project(db, project_id, client.id, wid)
    comments = db.scalars(
        select(VideoComment).where(
            VideoComment.project_id == project.id,
            VideoComment.workspace_id == wid,
        ).order_by(VideoComment.timestamp_seconds.asc())
    ).all()
    return [_comment_dict(c) for c in comments]


@router.post("/api/portal/projects/{project_id}/comments", status_code=201)
def add_portal_comment(
    project_id: int,
    data: PortalCommentInput,
    db: Session = Depends(get_db),
    client_identity=Depends(current_client_identity),
):
    client, wid = client_identity
    project = _get_portal_project(db, project_id, client.id, wid)

    comment = VideoComment(
        workspace_id=wid,
        client_id=client.id,
        project_id=project.id,
        review_version_id=data.version_id,
        timestamp_seconds=round(data.timestamp_seconds, 2),
        timecode=data.timecode.strip(),
        author_name=data.author_name or client.name,
        content=data.content.strip(),
        status="submitted",
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return _comment_dict(comment)


@router.patch("/api/portal/projects/{project_id}/comments/{comment_id}")
def update_portal_comment_status(
    project_id: int,
    comment_id: int,
    status: str,
    db: Session = Depends(get_db),
    client_identity=Depends(current_client_identity),
):
    client, wid = client_identity
    _get_portal_project(db, project_id, client.id, wid)
    comment = db.scalar(
        select(VideoComment).where(
            VideoComment.id == comment_id,
            VideoComment.project_id == project_id,
            VideoComment.workspace_id == wid,
        )
    )
    if not comment:
        raise HTTPException(404, "Comment not found")
    if status not in {"submitted", "processing", "resolved"}:
        raise HTTPException(422, "Invalid comment status")
    comment.status = status
    db.commit()
    return _comment_dict(comment)


# --- Client Review Decision (Approve, Request Changes, Reject) ---

@router.post("/api/portal/projects/{project_id}/decision")
def submit_portal_decision(
    project_id: int,
    data: PortalDecisionInput,
    db: Session = Depends(get_db),
    client_identity=Depends(current_client_identity),
):
    client, wid = client_identity
    project = _get_portal_project(db, project_id, client.id, wid)

    version = None
    if data.version_id:
        version = db.scalar(
            select(ReviewVersion).where(
                ReviewVersion.id == data.version_id,
                ReviewVersion.project_id == project.id,
            )
        )
    if not version:
        version = _ensure_review_version(db, project)

    decision_map = {
        "approve": ("approved", "delivered"),
        "changes_requested": ("changes_requested", "in_review"),
        "reject": ("rejected", "archived"),
    }
    ver_status, proj_status = decision_map[data.decision]
    version.status = ver_status
    if data.decision == "approve":
        project.status = "completed"

    # Record decision submission
    submission = ClientFeedbackSubmission(
        workspace_id=wid,
        client_id=client.id,
        project_id=project.id,
        review_version_id=version.id,
        feedback_type="review_decision",
        author_name=data.author_name or client.name,
        content=data.notes.strip() or f"Client marked version as {data.decision}.",
        structured_data=json.dumps([{"decision": data.decision, "version": version.version_label, "notes": data.notes}]),
        audio_asset_id=None,
        status="resolved" if data.decision == "approve" else "submitted",
        review_decision=data.decision,
    )
    db.add(submission)
    db.commit()

    return {
        "decision": data.decision,
        "project_id": project.id,
        "project_status": project.status,
        "version_id": version.id,
        "version_status": version.status,
        "submission_id": submission.id,
        "message": f"Version {version.version_label} successfully marked as {data.decision}.",
    }


# --- Client Feedback List & Status Tracking ---

@router.get("/api/portal/projects/{project_id}/feedback")
def list_portal_feedback(
    project_id: int,
    status: str | None = None,
    db: Session = Depends(get_db),
    client_identity=Depends(current_client_identity),
):
    client, wid = client_identity
    project = _get_portal_project(db, project_id, client.id, wid)
    stmt = select(ClientFeedbackSubmission).where(
        ClientFeedbackSubmission.project_id == project.id,
        ClientFeedbackSubmission.workspace_id == wid,
    )
    if status and status != "all":
        stmt = stmt.where(ClientFeedbackSubmission.status == status)

    submissions = db.scalars(stmt.order_by(ClientFeedbackSubmission.created_at.desc())).all()
    return [_submission_dict(s) for s in submissions]


# --- Secure Asset Stream for Client ---

@router.get("/api/portal/assets/{asset_id}/stream")
def stream_portal_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    client_identity=Depends(current_client_identity),
):
    client, wid = client_identity
    asset = db.scalar(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.client_id == client.id,
            Asset.workspace_id == wid,
        )
    )
    if not asset or not Path(asset.storage_key).is_file():
        raise HTTPException(404, "Asset not found or not accessible")
    return FileResponse(asset.storage_key, filename=asset.filename, media_type=asset.content_type)
