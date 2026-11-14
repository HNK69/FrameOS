"""Exercise the live FRAMEOPS workflow against configured external services.

Uses the application's HTTP API and an isolated SQLite database. The configured
Groq, Hindsight and OpenClaw services are real; this is not a mocked test.
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PORT = 8000
BASE = f"http://127.0.0.1:{PORT}"
DB = ROOT / ".live-workflow-check.db"
LOG = ROOT / ".live-workflow-check.log"


def ensure_port_free() -> None:
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", PORT))
        except OSError as exc:
            raise RuntimeError(f"Port {PORT} is occupied; no process was stopped.") from exc


def main() -> int:
    ensure_port_free()
    for path in (DB, Path(str(DB) + "-wal"), Path(str(DB) + "-shm")):
        path.unlink(missing_ok=True)

    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite:///" + DB.as_posix()
    with LOG.open("w", encoding="utf-8") as log_file:
        migration = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT, env=env, stdout=log_file, stderr=subprocess.STDOUT, timeout=90,
        )
        if migration.returncode:
            raise RuntimeError(f"Isolated database migration failed (exit {migration.returncode}); see local verification log.")
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
            cwd=ROOT, env=env, stdout=log_file, stderr=subprocess.STDOUT,
        )
        result: dict[str, object] = {"port": PORT, "database": "isolated SQLite", "workflow": "incomplete"}
        client_id: int | None = None
        try:
            with httpx.Client(base_url=BASE, timeout=115) as client:
                for _ in range(60):
                    if server.poll() is not None:
                        raise RuntimeError(f"Uvicorn exited with code {server.returncode}; see local verification log.")
                    try:
                        health = client.get(f"{BASE}/api/health")
                        if health.status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.5)
                else:
                    raise RuntimeError("Uvicorn did not become reachable on loopback port 8000.")

                auth = "frameops-live-" + secrets.token_hex(8) + "@example.com"
                password = secrets.token_urlsafe(24)
                response = client.post("/api/auth/setup", json={
                    "email": auth, "password": password, "workspace_name": "Live workflow verification",
                })
                if response.status_code != 200:
                    raise RuntimeError(f"Workspace setup HTTP {response.status_code}: {response.text[:500]}")
                result["workspace_created"] = True

                response = client.post("/api/clients", json={
                    "name": "Live Integration Verification", "brand": "FRAMEOPS test",
                    "industry": "Post-production", "description": "Temporary real-service workflow verification.",
                })
                response.raise_for_status()
                created = response.json()
                client_id = created["id"]
                result["hindsight_bank_initialized"] = created["memory_status"] == "ready"
                if not result["hindsight_bank_initialized"]:
                    raise RuntimeError("Client was created, but its Hindsight bank was not initialized.")

                content = "For this verification, the client prefers understated music and a warm, natural opening."
                response = client.post("/api/memory/retain", headers={"Idempotency-Key": "live-verification-retain"}, json={
                    "client_id": client_id, "content": content, "provenance": "editor_interpretation",
                    "client_confirmed": False,
                })
                if response.status_code != 200:
                    result["hindsight_retain_http_status"] = response.status_code
                    result["hindsight_retain_detail"] = response.text[:600]
                    recall_debug = client.post("/api/memory/recall", params={
                        "client_id": client_id, "query": "understated music and warm natural opening",
                    })
                    result["hindsight_recall_http_status"] = recall_debug.status_code
                    if recall_debug.status_code == 200:
                        result["hindsight_recall_evidence"] = recall_debug.json()
                    raise RuntimeError(json.dumps(result, ensure_ascii=False)[:2000])
                result["hindsight_retain_status"] = response.json()["status"]
                if response.json()["status"] != "completed":
                    raise RuntimeError("Hindsight retain was not verified by recall.")

                response = client.post("/api/projects", json={
                    "client_id": client_id, "name": "Live workflow verification project",
                    "description": "Temporary integration check", "status": "active",
                })
                response.raise_for_status()
                project_id = response.json()["id"]
                transcript = (
                    "Please make the opening feel warmer and more human. Use the close-up product shot first. "
                    "Keep the music understated. Put the transparent logo on the end card. "
                    "Do not change the color treatment; we will confirm that after review."
                )
                response = client.post("/api/process-transcript", headers={"Idempotency-Key": "live-verification-run"}, json={
                    "project_id": project_id, "transcript": transcript,
                })
                if response.status_code != 201:
                    result["transcript_http_status"] = response.status_code
                    result["transcript_error"] = response.text[:1200]
                    raise RuntimeError("Real transcript processing did not complete: " + json.dumps(result, ensure_ascii=False)[:1800])
                run = response.json()
                result["run_status"] = run["status"]
                result["run_stage"] = run["stage"]
                result["extraction_count"] = len(run["extractions"])
                result["recall_recorded"] = any(op["operation"] == "recall" and op["status"] == "completed" for op in run["memory_operations"])
                result["production_tasks_returned"] = len(run["tasks"])
                if run["status"] != "completed" or run["stage"] != "completed" or not run["tasks"] or not result["recall_recorded"]:
                    raise RuntimeError("Workflow response lacks completed real synthesis, recall, or production tasks.")

                response = client.post("/api/memory/recall", params={
                    "client_id": client_id, "query": "understated music warm natural opening",
                })
                response.raise_for_status()
                recalled = json.dumps(response.json(), ensure_ascii=False).lower()
                result["hindsight_recall_contains_retained_preference"] = "understated music" in recalled
                if not result["hindsight_recall_contains_retained_preference"]:
                    raise RuntimeError("Explicit Hindsight recall did not return the retained verification preference.")

                from sqlalchemy import func, select

                from app.db import SessionLocal
                from app.models import ProcessingRun, ProductionTask

                with SessionLocal() as db:
                    persisted_run = db.scalar(select(ProcessingRun).where(ProcessingRun.id == run["id"]))
                    persisted_tasks = db.scalar(select(func.count(ProductionTask.id)).where(ProductionTask.run_id == run["id"]))
                    result["persisted_run_status"] = persisted_run.status if persisted_run else None
                    result["persisted_production_task_count"] = persisted_tasks
                if result["persisted_run_status"] != "completed" or not result["persisted_production_task_count"]:
                    raise RuntimeError("Production tasks were not persisted in the isolated database.")
                result["workflow"] = "completed"
                result["openclaw_synthesis"] = "completed; API persisted tasks after the real CLI agent response"
        finally:
            if client_id is not None and server.poll() is None:
                try:
                    with httpx.Client(timeout=60) as cleanup:
                        cleanup.cookies.update(client.cookies)
                        deleted = cleanup.delete(f"{BASE}/api/clients/{client_id}")
                        result["hindsight_bank_cleanup"] = "verified" if deleted.status_code == 204 else f"failed HTTP {deleted.status_code}"
                except Exception as exc:  # cleanup evidence should not hide the workflow result
                    result["hindsight_bank_cleanup"] = f"failed {type(exc).__name__}"
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
    print(json.dumps(result, indent=2))
    if result.get("workflow") == "completed":
        for path in (DB, Path(str(DB) + "-wal"), Path(str(DB) + "-shm")):
            path.unlink(missing_ok=True)
        return 0
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"workflow": "incomplete", "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        raise SystemExit(1) from exc
