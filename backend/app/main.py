import logging
import mimetypes
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import (
    Asset,
    Client,
    ExtractedItem,
    Feedback,
    Membership,
    MemoryOperation,
    ProcessingRun,
    ProductionTask,
    Project,
    Transcript,
    User,
    Workspace,
    now_utc,
)
from .routers.feedback import router as feedback_router
from .routers.portal import router as portal_router
from .routers.production_intelligence import router as production_router
from .schemas import (
    ClientInput,
    FeedbackInput,
    LoginInput,
    ProcessInput,
    ProjectInput,
    RetainInput,
    SetupInput,
)
from .security import current_identity, hash_password, issue_token, verify_password
from .services import groq, hindsight, openclaw
from .services.production_analytics import get_production_analytics

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(message)s")
log = logging.getLogger("frameops")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(title="FRAMEOPS API", version="0.1.0", lifespan=lifespan)
app.include_router(feedback_router)
app.include_router(production_router)
app.include_router(portal_router)
origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "PATCH", "DELETE"],
                   allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Portal-Token"])


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


def _client_dict(c: Client, db: Session) -> dict:
    return {"id": c.id, "name": c.name, "brand": c.brand, "industry": c.industry,
            "description": c.description, "memory_status": c.memory_status,
            "projects_count": db.query(Project).filter_by(client_id=c.id).count(),
            "memories_retained": db.query(MemoryOperation).filter_by(client_id=c.id, operation="retain", status="completed").count(),
            "created_at": c.created_at.isoformat()}


def _project_dict(p: Project) -> dict:
    return {"id": p.id, "client_id": p.client_id, "client_name": p.client.name if p.client else "",
            "name": p.name, "description": p.description, "status": p.status,
            "due_date": p.due_date.isoformat() if p.due_date else None,
            "created_at": p.created_at.isoformat()}


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


def _remove_project_assets(db: Session, project_ids: list[int]):
    if not project_ids:
        return
    root = Path(settings.upload_dir).resolve()
    assets = db.scalars(select(Asset).where(Asset.project_id.in_(project_ids))).all()
    for asset in assets:
        path = Path(asset.storage_key).resolve()
        if path.is_relative_to(root) and path.is_file():
            path.unlink()


def _remember_op(db: Session, *, workspace_id: int, client_id: int, project_id: int | None,
                 run_id: int | None, operation: str, status: str, key: str, details: str = "",
                 provenance: str = "") -> MemoryOperation:
    row = MemoryOperation(workspace_id=workspace_id, client_id=client_id, project_id=project_id,
                          run_id=run_id, operation=operation, status=status, idempotency_key=key,
                          details=details[:8000], provenance=provenance)
    db.add(row)
    return row


def _memory_text(result: dict | list) -> list[dict]:
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        found = result.get("results", result.get("memories", []))
        return found if isinstance(found, list) else []
    return []


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "frameops-api"}


@app.get("/api/ready")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        database = "ready"
    except Exception:
        database = "unavailable"
    openclaw_cli = bool(settings.openclaw_bin or os.getenv("OPENCLAW_BIN") or shutil.which("openclaw"))
    integrations = {
        "groq": "configured" if settings.groq_api_key and settings.groq_model else "unavailable",
        "hindsight": "configured" if hindsight.configured() else "unavailable",
        "openclaw": "configured" if (openclaw_cli and settings.openclaw_gateway_url and (settings.openclaw_auth_token or os.getenv("OPENCLAW_GATEWAY_TOKEN"))) else "unavailable",
    }
    status = "ready" if database == "ready" and all(v == "configured" for v in integrations.values()) else "degraded"
    return {"status": status, "database": database, "integrations": integrations}


@app.get("/api/auth/status")
def auth_status(db: Session = Depends(get_db)):
    return {"setup_required": db.query(User).count() == 0, "auth_ready": bool(settings.auth_secret)}


def _set_auth_cookie(response: Response, token: str):
    response.set_cookie("frameops_session", token, max_age=settings.auth_token_minutes * 60,
                        httponly=True, secure=settings.auth_cookie_secure, samesite="lax", path="/")


@app.post("/api/auth/setup")
def setup(data: SetupInput, response: Response, db: Session = Depends(get_db)):
    if not settings.auth_secret:
        raise HTTPException(503, "Set AUTH_SECRET before creating the workspace owner")
    if db.query(User).count():
        raise HTTPException(409, "Initial owner is already configured")
    user = User(email=data.email.lower(), password_hash=hash_password(data.password))
    workspace = Workspace(name=data.workspace_name.strip())
    db.add_all([user, workspace])
    db.flush()
    member = Membership(workspace_id=workspace.id, user_id=user.id, role="owner")
    db.add(member)
    db.commit()
    _set_auth_cookie(response, issue_token(user, member))
    return {"workspace": {"id": workspace.id, "name": workspace.name}}


@app.post("/api/auth/login")
def login(data: LoginInput, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    member = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.id))
    if not member:
        raise HTTPException(403, "No workspace membership")
    _set_auth_cookie(response, issue_token(user, member))
    return {"workspace": {"id": member.workspace_id, "name": member.workspace.name}}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("frameops_session", path="/", httponly=True, secure=settings.auth_cookie_secure, samesite="lax")
    return {"logged_out": True}


@app.get("/api/me")
def me(identity=Depends(current_identity)):
    user, workspace_id, role = identity
    return {"id": user.id, "email": user.email, "workspace_id": workspace_id, "role": role}


@app.get("/api/clients")
def list_clients(db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    return [_client_dict(c, db) for c in db.scalars(select(Client).where(Client.workspace_id == wid).order_by(Client.created_at.desc())).all()]


@app.post("/api/clients", status_code=201)
async def create_client(data: ClientInput, db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    # Bank IDs are generated by the application and persisted, never inferred from client text.
    bank_id = f"frameops-w{wid}-c{uuid4().hex}"
    client = Client(workspace_id=wid, memory_bank_id=bank_id, name=data.name.strip(), brand=data.brand.strip(),
                    industry=data.industry.strip(), description=data.description.strip(),
                    memory_status="ready" if hindsight.configured() else "unavailable")
    db.add(client)
    db.commit()
    db.refresh(client)
    if hindsight.configured():
        try:
            await hindsight.ensure_bank(bank_id)
            client.memory_status = "ready"
            _remember_op(db, workspace_id=wid, client_id=client.id, project_id=None, run_id=None,
                         operation="initialize", status="completed", key=f"bank:init:{client.id}",
                         details="Client bank mapping was initialized in Hindsight.")
        except groq.ServiceUnavailable as exc:
            client.memory_status = "unavailable"
            _remember_op(db, workspace_id=wid, client_id=client.id, project_id=None, run_id=None,
                         operation="initialize", status="failed", key=f"bank:init:{client.id}", details=str(exc))
        db.commit()
    return _client_dict(client, db)


@app.get("/api/clients/{client_id}")
def get_client(client_id: int, db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    client = _get_client(db, client_id, wid)
    result = _client_dict(client, db)
    result["projects"] = [_project_dict(p) for p in db.scalars(select(Project).where(Project.client_id == client.id).order_by(Project.created_at.desc())).all()]
    result["memory_history"] = [{"operation": m.operation, "status": m.status, "provenance": m.provenance,
                                  "details": m.details, "created_at": m.created_at.isoformat()}
                                 for m in db.scalars(select(MemoryOperation).where(MemoryOperation.client_id == client.id).order_by(MemoryOperation.created_at.desc()).limit(30)).all()]
    return result


@app.patch("/api/clients/{client_id}")
def patch_client(client_id: int, data: ClientInput, db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    client = _get_client(db, client_id, wid)
    for field, value in data.model_dump().items():
        setattr(client, field, value.strip())
    db.commit()
    return _client_dict(client, db)


@app.delete("/api/clients/{client_id}", status_code=204)
async def delete_client(client_id: int, db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    client = _get_client(db, client_id, wid)
    if client.memory_status == "ready" and not hindsight.configured():
        raise HTTPException(503, "Client deletion paused. Restore Hindsight credentials to verify memory-bank offboarding.")
    if hindsight.configured():
        try:
            await hindsight.delete_bank(client.memory_bank_id)
        except groq.ServiceUnavailable as exc:
            # Don't claim offboarding when remote memory could not be deleted.
            raise HTTPException(503, f"Client deletion paused; Hindsight bank could not be reached: {exc}") from exc
    project_ids = list(db.scalars(select(Project.id).where(Project.client_id == client.id)).all())
    _remove_project_assets(db, project_ids)
    db.delete(client)
    db.commit()


@app.get("/api/projects")
def list_projects(client_id: int | None = None, status: str | None = None,
                  db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    stmt = select(Project).where(Project.workspace_id == wid)
    if client_id is not None:
        stmt = stmt.where(Project.client_id == client_id)
    if status and status != "all":
        stmt = stmt.where(Project.status == status)
    return [_project_dict(p) for p in db.scalars(stmt.order_by(Project.created_at.desc())).all()]


@app.post("/api/projects", status_code=201)
def create_project(data: ProjectInput, db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    _get_client(db, data.client_id, wid)
    project = Project(workspace_id=wid, client_id=data.client_id, name=data.name.strip(),
                      description=data.description.strip(), status=data.status, due_date=data.due_date)
    db.add(project)
    db.commit()
    db.refresh(project)
    return _project_dict(project)


@app.get("/api/projects/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    project = _get_project(db, project_id, wid)
    runs = db.scalars(select(ProcessingRun).where(ProcessingRun.project_id == project.id)
                      .order_by(ProcessingRun.created_at.desc(), ProcessingRun.id.desc())).all()
    return {**_project_dict(project), "runs": [run_dict(db, r) for r in runs],
            "assets": [asset_dict(a) for a in db.scalars(select(Asset).where(Asset.project_id == project.id)).all()]}


@app.patch("/api/projects/{project_id}")
def patch_project(project_id: int, data: ProjectInput, db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    project = _get_project(db, project_id, wid)
    _get_client(db, data.client_id, wid)
    for field, value in data.model_dump().items():
        setattr(project, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    return _project_dict(project)


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    project = _get_project(db, project_id, wid)
    _remove_project_assets(db, [project.id])
    db.delete(project)
    db.commit()


def asset_dict(a: Asset) -> dict:
    return {"id": a.id, "filename": a.filename, "category": a.category, "content_type": a.content_type,
            "size_bytes": a.size_bytes, "created_at": a.created_at.isoformat()}


@app.post("/api/projects/{project_id}/assets", status_code=201)
async def upload_asset(project_id: int, file: UploadFile = File(...), category: str = "unknown",
                       db: Session = Depends(get_db), identity=Depends(current_identity)):
    user, wid, _ = identity
    project = _get_project(db, project_id, wid)
    client = _get_client(db, project.client_id, wid)
    safe_name = Path(file.filename or "upload.bin").name[:255]
    content = await file.read(settings.max_upload_bytes + 1)
    if not content or len(content) > settings.max_upload_bytes:
        raise HTTPException(413, "File is empty or exceeds the upload size limit")
    content_type = file.content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    allowed = {"image/png", "image/jpeg", "image/webp", "image/svg+xml", "font/woff", "font/woff2",
               "audio/mpeg", "audio/wav", "video/mp4", "video/quicktime", "application/pdf",
               "text/plain", "text/markdown", "application/json", "application/octet-stream"}
    if content_type not in allowed:
        raise HTTPException(415, "Unsupported asset content type")
    folder = Path(settings.upload_dir).resolve() / str(wid) / str(project.id)
    folder.mkdir(parents=True, exist_ok=True)
    storage_key = f"{wid}/{project.id}/{uuid4().hex}"
    destination = folder / storage_key.split("/")[-1]
    destination.write_bytes(content)
    asset = Asset(workspace_id=wid, client_id=client.id, project_id=project.id, filename=safe_name,
                  category=category[:48], content_type=content_type, size_bytes=len(content),
                  storage_key=str(destination), created_by=user.id)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset_dict(asset)


@app.get("/api/assets/{asset_id}/download")
def download_asset(asset_id: int, db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    asset = db.scalar(select(Asset).where(Asset.id == asset_id, Asset.workspace_id == wid))
    if not asset or not Path(asset.storage_key).is_file():
        raise HTTPException(404, "Asset not found")
    safe_filename = asset.filename.replace('"', '\\"')
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_filename}"',
        "X-Content-Type-Options": "nosniff",
    }
    return FileResponse(asset.storage_key, filename=asset.filename, media_type=asset.content_type, headers=headers)


@app.post("/api/process-transcript", status_code=201)
async def process_transcript(data: ProcessInput, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                             db: Session = Depends(get_db), identity=Depends(current_identity)):
    user, wid, _ = identity
    project = _get_project(db, data.project_id, wid)
    client = _get_client(db, project.client_id, wid)
    key = idempotency_key or uuid4().hex
    if len(key) > 120:
        raise HTTPException(422, "Idempotency-Key must be at most 120 characters")
    run = db.scalar(select(ProcessingRun).where(ProcessingRun.workspace_id == wid,
                                                 ProcessingRun.idempotency_key == key))
    if run:
        old_transcript = db.get(Transcript, run.transcript_id)
        if run.project_id != project.id or not old_transcript or old_transcript.content != data.transcript.strip():
            raise HTTPException(409, "Idempotency-Key was already used for different input")
        if run.status in {"completed", "processing"}:
            return run_dict(db, run)
        db.query(ExtractedItem).filter_by(run_id=run.id).delete()
        db.query(ProductionTask).filter_by(run_id=run.id).delete()
        run.attempt_count += 1
        run.status, run.stage, run.error, run.completed_at = "processing", "extracting", "", None
    else:
        transcript = Transcript(project_id=project.id, content=data.transcript.strip(), created_by=user.id)
        db.add(transcript)
        db.flush()
        run = ProcessingRun(workspace_id=wid, client_id=client.id, project_id=project.id,
                            transcript_id=transcript.id, idempotency_key=key, status="processing", stage="extracting")
        db.add(run)
    db.commit()
    try:
        extracted = await groq.extract_feedback(data.transcript.strip())
        for item in extracted.requests:
            db.add(ExtractedItem(
                run_id=run.id,
                description=item.description,
                category=item.category,
                source_quote=item.source_quote,
                classification=item.classification,
                confidence=item.confidence,
                requires_confirmation=item.requires_confirmation,
            ))
        db.commit()
        run.stage = "recalling"
        db.commit()
        query = "\n".join(i.description for i in extracted.requests) or "Client preferences, editing requirements, recurring revisions"
        recall: dict | list = {"results": []}
        try:
            recall = await hindsight.recall(client.memory_bank_id, query)
            _remember_op(db, workspace_id=wid, client_id=client.id, project_id=project.id, run_id=run.id,
                         operation="recall", status="completed", key=f"{key}:recall",
                         details=f"Retrieved {len(_memory_text(recall))} historical entries.")
            db.commit()
        except Exception as exc:
            recall = {"results": []}
            _remember_op(db, workspace_id=wid, client_id=client.id, project_id=project.id, run_id=run.id,
                         operation="recall", status="degraded", key=f"{key}:recall",
                         details=f"Hindsight recall degraded: {type(exc).__name__}: {str(exc)[:500]}")
            db.commit()
        asset_rows = db.scalars(select(Asset).where(Asset.project_id == project.id)).all()
        uploaded_assets = [{"name": a.filename, "category": a.category, "status": "Present", "content_type": a.content_type} for a in asset_rows]
        requirements = [r.model_dump() for r in extracted.required_assets]
        for requirement in requirements:
            match = next((a for a in uploaded_assets if a["category"].lower() == requirement["category"].lower()
                          or a["name"].lower() == requirement["name"].lower()), None)
            requirement["status"] = "Present" if match else "Unknown"
        run.stage = "synthesizing"
        db.commit()
        synth = await openclaw.synthesize(run_id=run.id, attempt_count=run.attempt_count,
                                          client_name=client.name, project_name=project.name,
                                          extraction=extracted.model_dump(), memories=recall,
                                          assets=[*uploaded_assets, *requirements])
        for task in synth.tasks:
            requires_confirmation = task.requires_confirmation or task.confidence < 0.72
            db.add(ProductionTask(workspace_id=wid, client_id=client.id, project_id=project.id,
                                  run_id=run.id, title=task.title, category=task.category,
                                  instruction=task.instruction, resolve_workflow=task.resolve_workflow,
                                  priority=task.priority, source=task.source, evidence=task.evidence,
                                  confidence=task.confidence, requires_confirmation=requires_confirmation))
        run.status = "completed"
        run.stage = "completed"
        run.completed_at = now_utc()
        db.commit()
        return run_dict(db, run)
    except Exception as exc:
        db.rollback()
        run = db.get(ProcessingRun, run.id)
        run.status = "failed"
        run.stage = "failed"
        run.error = str(exc).strip()[:1200] or type(exc).__name__
        run.completed_at = now_utc()
        db.commit()
        if isinstance(exc, groq.ServiceUnavailable):
            raise HTTPException(503, str(exc)) from exc
        log.exception("Transcript processing failed run_id=%s", run.id)
        raise HTTPException(502, "Transcript processing failed. Check the run record for status.") from exc


def run_dict(db: Session, run: ProcessingRun) -> dict:
    transcript = db.get(Transcript, run.transcript_id)
    extractions = db.scalars(select(ExtractedItem).where(ExtractedItem.run_id == run.id)).all()
    tasks = db.scalars(select(ProductionTask).where(ProductionTask.run_id == run.id)).all()
    memory_ops = db.scalars(select(MemoryOperation).where(MemoryOperation.run_id == run.id).order_by(MemoryOperation.created_at)).all()
    return {"id": run.id, "project_id": run.project_id, "client_id": run.client_id, "status": run.status,
            "stage": run.stage, "error": run.error, "transcript": transcript.content if transcript else "",
            "extractions": [{"id": x.id, "description": x.description, "category": x.category,
                             "source_quote": x.source_quote, "classification": x.classification,
                             "confidence": x.confidence, "requires_confirmation": x.requires_confirmation} for x in extractions],
            "tasks": [task_dict(t) for t in tasks],
            "memory_operations": [{"operation": m.operation, "status": m.status, "details": m.details,
                                   "created_at": m.created_at.isoformat()} for m in memory_ops],
            "created_at": run.created_at.isoformat(), "completed_at": run.completed_at.isoformat() if run.completed_at else None}


def task_dict(t: ProductionTask) -> dict:
    return {"id": t.id, "title": t.title, "category": t.category, "instruction": t.instruction,
            "resolve_workflow": t.resolve_workflow, "priority": t.priority, "source": t.source,
            "evidence": t.evidence, "confidence": t.confidence,
            "requires_confirmation": t.requires_confirmation, "status": t.status,
            "project_id": t.project_id, "client_id": t.client_id, "run_id": t.run_id,
            "created_at": t.created_at.isoformat() if t.created_at else None}


@app.get("/api/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    run = db.scalar(select(ProcessingRun).where(ProcessingRun.id == run_id, ProcessingRun.workspace_id == wid))
    if not run:
        raise HTTPException(404, "Processing run not found")
    return run_dict(db, run)


@app.get("/api/clients/{client_id}/memories")
async def list_memories(client_id: int, db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    client = _get_client(db, client_id, wid)
    if not hindsight.configured():
        raise HTTPException(503, "Hindsight is not configured")
    try:
        result = await hindsight.call_memory("GET", client.memory_bank_id, "list", {})
    except groq.ServiceUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"client_id": client_id, "memories": _memory_text(result)}


@app.post("/api/memory/recall")
async def memory_recall(client_id: int, query: str, db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    client = _get_client(db, client_id, wid)
    try:
        return await hindsight.recall(client.memory_bank_id, query)
    except groq.ServiceUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/memory/retain")
async def memory_retain(data: RetainInput, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                        db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    client = _get_client(db, data.client_id, wid)
    project_id = data.project_id
    if project_id is not None:
        project = _get_project(db, project_id, wid)
        if project.client_id != client.id:
            raise HTTPException(422, "Project does not belong to this client")
    if data.client_confirmed and data.provenance != "client_confirmed":
        raise HTTPException(422, "Confirmed memories must use client_confirmed provenance")
    key = idempotency_key or uuid4().hex
    if len(key) > 120:
        raise HTTPException(422, "Idempotency-Key must be at most 120 characters")
    existing = db.scalar(select(MemoryOperation).where(MemoryOperation.workspace_id == wid,
                                                         MemoryOperation.idempotency_key == key))
    if existing and existing.status == "completed":
        return {"operation_id": existing.id, "status": existing.status, "details": existing.details}
    if existing:
        if existing.client_id != client.id:
            raise HTTPException(409, "Idempotency-Key is already associated with another client")
        op = existing
        op.status, op.details = "pending", ""
    else:
        op = _remember_op(db, workspace_id=wid, client_id=client.id, project_id=project_id, run_id=None,
                          operation="retain", status="pending", key=key, provenance=data.provenance)
    db.commit()
    try:
        result, verified = await hindsight.retain_and_verify(
            client.memory_bank_id, data.content,
            f"FRAMEOPS retained knowledge; workspace={wid}; client={client.id}; "
            f"project={project_id}; provenance={data.provenance}; confirmed={data.client_confirmed}",
            ["frameops", data.provenance, "confirmed" if data.client_confirmed else "unconfirmed"],
            f"frameops-retain-{wid}-{client.id}-{key[:40]}")
        op.status = "completed" if verified else "failed"
        op.details = "Hindsight retain was recalled and verified." if verified else "Retain returned but verification recall did not confirm the submitted content."
        db.commit()
        if not verified:
            raise HTTPException(502, op.details)
        return {"operation_id": op.id, "status": op.status, "details": op.details, "provider_result": result}
    except groq.ServiceUnavailable as exc:
        op.status = "failed"
        op.details = str(exc)
        db.commit()
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/memory/reflect")
async def memory_reflect(client_id: int, query: str, db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    client = _get_client(db, client_id, wid)
    try:
        return await hindsight.reflect(client.memory_bank_id, query)
    except groq.ServiceUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/tasks/{task_id}/feedback")
async def feedback(task_id: int, data: FeedbackInput, db: Session = Depends(get_db), identity=Depends(current_identity)):
    user, wid, _ = identity
    task = db.scalar(select(ProductionTask).where(ProductionTask.id == task_id, ProductionTask.workspace_id == wid))
    if not task:
        raise HTTPException(404, "Task not found")
    if data.action == "correct" and not data.correction.strip():
        raise HTTPException(422, "A correction is required for the correct action")
    task.status = {"accept": "accepted", "correct": "corrected", "reject": "rejected"}.get(data.action, data.action)
    if data.priority:
        task.priority = data.priority
    feedback_row = Feedback(workspace_id=wid, client_id=task.client_id, project_id=task.project_id,
                            task_id=task.id, author_id=user.id, action=data.action,
                            original_recommendation=task.instruction, correction=data.correction.strip(),
                            client_confirmed=data.client_confirmed)
    db.add(feedback_row)
    db.commit()
    retention_status = "not_requested"
    if data.action == "correct" or (data.action == "accept" and data.client_confirmed):
        client = _get_client(db, task.client_id, wid)
        content = (f"Editor correction to recommendation: {data.correction.strip()}" if data.action == "correct"
                   else f"Client-confirmed preference: {task.instruction}")
        context = (f"FRAMEOPS editor feedback; workspace={wid}; client={task.client_id}; "
                   f"project={task.project_id}; original={task.instruction}; confirmation={data.client_confirmed}")
        key = f"feedback:{feedback_row.id}"
        _remember_op(db, workspace_id=wid, client_id=client.id, project_id=task.project_id, run_id=task.run_id,
                     operation="retain", status="pending", key=key,
                     provenance="client_confirmed" if data.client_confirmed else "editor_interpretation")
        db.commit()
        try:
            _, retained = await hindsight.retain_and_verify(
                client.memory_bank_id, content, context,
                ["frameops", "editor_feedback", "confirmed" if data.client_confirmed else "unconfirmed"],
                f"frameops-feedback-{feedback_row.id}")
            retention_status = "verified" if retained else "verification_failed"
            op = db.scalar(select(MemoryOperation).where(MemoryOperation.idempotency_key == key))
            op.status = "completed" if retained else "failed"
            op.details = ("Hindsight retain accepted and matching content was recalled." if retained
                          else "Retain request returned, but verification recall did not contain the submitted feedback.")
            feedback_row.retention_status = retention_status
            db.commit()
        except groq.ServiceUnavailable as exc:
            op = db.scalar(select(MemoryOperation).where(MemoryOperation.idempotency_key == key))
            op.status = "failed"
            op.details = str(exc)
            feedback_row.retention_status = "failed"
            db.commit()
            raise HTTPException(503, f"Feedback saved, but Hindsight retention was not verified: {exc}") from exc
    return {"feedback_id": feedback_row.id, "task_id": task.id, "task_status": task.status,
            "client_confirmed": feedback_row.client_confirmed, "retention_status": retention_status,
            "message": "Feedback saved" + (" and verified in Hindsight." if retention_status == "verified" else ".")}


@app.get("/api/analytics")
def analytics(db: Session = Depends(get_db), identity=Depends(current_identity)):
    _, wid, _ = identity
    return get_production_analytics(db, wid)
