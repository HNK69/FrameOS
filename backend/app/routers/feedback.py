import json
import hashlib
import mimetypes
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal, get_db
from ..models import ClientFeedback, Project, now_utc
from ..security import current_identity
from ..services import groq

router = APIRouter(prefix="/api", tags=["client feedback"])
ALLOWED_AUDIO = {
    ".mp3": {"audio/mpeg", "audio/mp3"}, ".wav": {"audio/wav", "audio/x-wav"},
    ".m4a": {"audio/mp4", "audio/x-m4a"}, ".mp4": {"audio/mp4"},
    ".webm": {"audio/webm"}, ".ogg": {"audio/ogg", "application/ogg"},
    ".flac": {"audio/flac", "audio/x-flac"},
}


class TextSubmission(BaseModel):
    project_id: int
    text: str = Field(min_length=10, max_length=100_000)


class ClientReview(BaseModel):
    summary: str = Field(min_length=1, max_length=4000)
    extracted: dict | None = None


def _project(db: Session, project_id: int, workspace_id: int) -> Project:
    project = db.scalar(select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id))
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _view(item: ClientFeedback) -> dict:
    return {
        "id": item.id, "project_id": item.project_id, "client_id": item.client_id,
        "source_type": item.source_type, "audio": ({"filename": item.audio_filename,
            "content_type": item.audio_content_type, "preserved": bool(item.audio_path)} if item.audio_path else None),
        "transcript": item.transcript, "transcript_provenance": {
            "source": item.source_type, "provider": item.transcript_provider or "client_submission",
            "model": item.transcript_model or None, "submitted_by": item.submitted_by,
            "created_at": (item.transcript_created_at or item.created_at).isoformat()},
        "extracted": json.loads(item.extracted_json or "{}"), "summary": item.summary,
        "status": item.status, "stage": item.stage, "error": item.error,
        "attempt_count": item.attempt_count,
        "client_confirmed_at": item.client_confirmed_at.isoformat() if item.client_confirmed_at else None,
        "delivered_at": item.delivered_at.isoformat() if item.delivered_at else None,
        "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
    }


def _new_submission(db: Session, *, project: Project, workspace_id: int, user_id: int,
                    key: str, source_type: str, text: str = "", audio_path: str = "",
                    filename: str = "", content_type: str = "") -> ClientFeedback:
    if not key or len(key) > 120:
        raise HTTPException(422, "Idempotency-Key is required and must be at most 120 characters")
    existing = db.scalar(select(ClientFeedback).where(ClientFeedback.workspace_id == workspace_id,
                                                       ClientFeedback.idempotency_key == key))
    if existing:
        audio_matches = (not audio_path or (existing.audio_path and Path(existing.audio_path).is_file()
            and Path(existing.audio_path).read_bytes() == Path(audio_path).read_bytes()))
        if existing.project_id != project.id or existing.source_type != source_type or (text and existing.original_text != text) or not audio_matches:
            raise HTTPException(409, "Idempotency-Key was already used for different input")
        if audio_path and Path(audio_path) != Path(existing.audio_path):
            Path(audio_path).unlink(missing_ok=True)
        return existing
    item = ClientFeedback(workspace_id=workspace_id, client_id=project.client_id, project_id=project.id,
        submitted_by=user_id, idempotency_key=key, source_type=source_type, original_text=text,
        audio_path=audio_path, audio_filename=filename, audio_content_type=content_type)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/feedback", status_code=202)
def submit_text(data: TextSubmission, background: BackgroundTasks,
                key: str | None = Header(default=None, alias="Idempotency-Key"),
                db: Session = Depends(get_db), identity=Depends(current_identity)):
    user, workspace_id, _ = identity
    project = _project(db, data.project_id, workspace_id)
    normalized = data.text.strip()
    fallback_key = hashlib.sha256(f"{project.id}:text:{normalized}".encode()).hexdigest()
    item = _new_submission(db, project=project, workspace_id=workspace_id, user_id=user.id,
                           key=key or fallback_key, source_type="text", text=normalized)
    if item.status in {"queued", "failed"}:
        background.add_task(process_feedback, item.id)
    return _view(item)


@router.post("/feedback/audio", status_code=202)
async def submit_audio(project_id: int, background: BackgroundTasks, file: UploadFile = File(...),
                       key: str | None = Header(default=None, alias="Idempotency-Key"),
                       db: Session = Depends(get_db), identity=Depends(current_identity)):
    user, workspace_id, _ = identity
    project = _project(db, project_id, workspace_id)
    filename = Path(file.filename or "recording").name
    extension = Path(filename).suffix.lower()
    content_type = (file.content_type or mimetypes.guess_type(filename)[0] or "").lower()
    if extension not in ALLOWED_AUDIO or content_type not in ALLOWED_AUDIO[extension]:
        raise HTTPException(415, "Unsupported audio format")
    content = await file.read(settings.max_upload_bytes + 1)
    if not content or len(content) > settings.max_upload_bytes:
        raise HTTPException(413, "Audio is empty or exceeds the upload size limit")
    if not _audio_signature_valid(extension, content):
        raise HTTPException(415, "Audio content does not match its declared format")
    storage_root = Path(settings.upload_dir).resolve()
    folder = storage_root / str(workspace_id) / str(project.id) / "feedback"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid4().hex}{extension}"
    if not path.resolve().is_relative_to(storage_root):
        raise HTTPException(400, "Invalid upload path")
    path.write_bytes(content)
    fallback_key = hashlib.sha256(f"{project.id}:audio:".encode() + content).hexdigest()
    try:
        item = _new_submission(db, project=project, workspace_id=workspace_id, user_id=user.id,
            key=key or fallback_key, source_type="audio", audio_path=str(path), filename=filename,
            content_type=content_type)
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    background.add_task(process_feedback, item.id)
    return _view(item)


def _audio_signature_valid(extension: str, data: bytes) -> bool:
    signatures = {
        ".wav": data.startswith(b"RIFF") and data[8:12] == b"WAVE",
        ".flac": data.startswith(b"fLaC"), ".ogg": data.startswith(b"OggS"),
        ".webm": data.startswith(b"\x1aE\xdf\xa3"),
        ".m4a": len(data) > 12 and data[4:8] == b"ftyp",
        ".mp4": len(data) > 12 and data[4:8] == b"ftyp",
        ".mp3": data.startswith(b"ID3") or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0),
    }
    return signatures.get(extension, False)


async def process_feedback(feedback_id: int) -> None:
    """Durable state updates around provider calls; polling reads this row."""
    with SessionLocal() as db:
        item = db.get(ClientFeedback, feedback_id)
        if not item:
            return
        claimed = db.execute(update(ClientFeedback).where(ClientFeedback.id == feedback_id,
                ClientFeedback.status.in_(["queued", "failed"])).values(
                    status="processing", stage="transcribing" if item.source_type == "audio" else "extracting",
                    error="", attempt_count=ClientFeedback.attempt_count + 1,
                    updated_at=now_utc()))
        if claimed.rowcount != 1:
            db.rollback()
            return
        db.refresh(item)
        db.commit()
        try:
            transcript = item.original_text
            if item.source_type == "audio":
                transcript, model = await groq.transcribe_audio(item.audio_path, item.audio_filename, item.audio_content_type)
                item.transcript_provider, item.transcript_model = "groq", model
                item.transcript_created_at = now_utc()
                db.commit()
            item.transcript = transcript
            item.stage = "extracting"
            db.commit()
            result = await groq.extract_feedback(transcript)
            item.extracted_json = result.model_dump_json()
            item.summary = result.summary.strip()
            item.status, item.stage = "awaiting_confirmation", "awaiting_confirmation"
            item.updated_at = now_utc()
            db.commit()
        except Exception as exc:
            db.rollback()
            item = db.get(ClientFeedback, feedback_id)
            item.status, item.stage = "failed", "failed"
            item.error = (str(exc) or type(exc).__name__)[:1200]
            item.updated_at = now_utc()
            db.commit()


@router.get("/feedback/{feedback_id}")
def get_feedback(feedback_id: int, db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, workspace_id, _ = identity
    item = db.scalar(select(ClientFeedback).where(ClientFeedback.id == feedback_id,
                                                   ClientFeedback.workspace_id == workspace_id))
    if not item:
        raise HTTPException(404, "Feedback not found")
    return _view(item)


@router.post("/feedback/{feedback_id}/retry", status_code=202)
def retry_feedback(feedback_id: int, background: BackgroundTasks, db: Session = Depends(get_db),
                   identity=Depends(current_identity)):
    _, workspace_id, _ = identity
    item = db.scalar(select(ClientFeedback).where(ClientFeedback.id == feedback_id,
        ClientFeedback.workspace_id == workspace_id))
    if not item:
        raise HTTPException(404, "Feedback not found")
    if item.status != "failed":
        raise HTTPException(409, "Only failed feedback can be retried")
    item.status, item.stage = "queued", "queued"
    db.commit()
    background.add_task(process_feedback, item.id)
    return _view(item)


@router.patch("/feedback/{feedback_id}/confirmation")
def confirm_feedback(feedback_id: int, data: ClientReview, db: Session = Depends(get_db),
                     identity=Depends(current_identity)):
    _, workspace_id, _ = identity
    item = db.scalar(select(ClientFeedback).where(ClientFeedback.id == feedback_id,
        ClientFeedback.workspace_id == workspace_id))
    if not item:
        raise HTTPException(404, "Feedback not found")
    if item.status not in {"awaiting_confirmation", "confirmed"}:
        raise HTTPException(409, "Feedback is not ready for confirmation")
    item.summary = data.summary.strip()
    if data.extracted is not None:
        item.extracted_json = json.dumps(data.extracted, ensure_ascii=False)
    item.status, item.stage = "confirmed", "confirmed"
    item.client_confirmed_at = now_utc()
    db.commit()
    return _view(item)


@router.get("/agency/feedback")
def agency_feedback(status: str | None = None, db: Session = Depends(get_db),
                    identity=Depends(current_identity)):
    _, workspace_id, _ = identity
    query = select(ClientFeedback).where(ClientFeedback.workspace_id == workspace_id)
    query = query.where(ClientFeedback.status == status) if status else query.where(
        ClientFeedback.status.in_(["confirmed", "delivered"]))
    rows = db.scalars(query.order_by(ClientFeedback.created_at.desc())).all()
    return [_view(row) for row in rows]


@router.post("/agency/feedback/{feedback_id}/deliver")
def deliver_feedback(feedback_id: int, db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, workspace_id, _ = identity
    item = db.scalar(select(ClientFeedback).where(ClientFeedback.id == feedback_id,
        ClientFeedback.workspace_id == workspace_id))
    if not item:
        raise HTTPException(404, "Feedback not found")
    if item.status not in {"confirmed", "delivered"}:
        raise HTTPException(409, "Client confirmation is required before agency delivery")
    if item.status == "confirmed":
        item.status, item.stage, item.delivered_at = "delivered", "delivered", datetime.now(UTC)
        db.commit()
    return _view(item)
