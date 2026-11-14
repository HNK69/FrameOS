# FRAMEOPS Project Status

Updated: 2026-11-14

## Implemented in this build

- Next.js frontend and FastAPI backend with workspace-scoped client/project CRUD, secure sessions, audit/analytics records, assets, and production task persistence.
- Per-client Hindsight bank mapping; real bank initialization, recall, retain, reflect, and deletion API calls.
- Groq structured extraction with Pydantic validation and transcript-as-untrusted-input handling.
- OpenClaw Gateway synthesis, task validation, editor feedback, provenance, and persisted processing runs.
- Windows-safe OpenClaw CLI execution using `asyncio.to_thread(subprocess.run)` under Uvicorn selector loops, with Gateway URL/token forwarding, timeout, stdout/stderr capture, and error parsing.
- Bounded Hindsight recall verification that accounts for asynchronous indexing and distilled facts by verifying source-document identity and content overlap.
- Isolated live workflow runner: `backend/scripts/live_workflow.py`. It starts Uvicorn on loopback port 8000 with a separate temporary SQLite database and creates/removes its test Hindsight bank through the API.
- Local portable Node.js 24.22.1 and OpenClaw CLI 2026.11.3 installed under ignored `.tools/`; SHA-256 of the Node archive was checked against the official release manifest. Backend `.env` points directly to these files without changing system Node or PATH.
- Dedicated Gateway agent `frameops-synth` configured with minimal tools, no inherited skills/bootstrap context, and a 512-token output cap. Shared `main` remains the system/auth owner and default for system operations.

## Verified

- Backend settings loaded required auth, Groq, Hindsight, and Gateway variables; checks printed only presence booleans, never secret values.
- Port 8000 was free before the live run. After the isolated test stopped, the backend was started on `127.0.0.1:8000` and remains running as the identified Uvicorn process started for this task (PID 32460). Health returns HTTP 200; `/api/ready` says `ready` because the database and integrations are configured. Readiness does not verify synthesis. No unidentified process was terminated.
- Groq configured API endpoint connectivity: HTTP 200. In the live backend workflow, Groq transcript extraction also returned HTTP 200.
- Hindsight configured service is reachable. Client bank initialization returned HTTP 200; actual retain and recall requests returned HTTP 200, and the retained preference was returned under its Hindsight source document. The test bank was subsequently deleted successfully.
- OpenClaw Gateway CLI version: `OpenClaw 2026.11.3`; the Windows-safe runner successfully launches it and passes existing Gateway authentication/environment.
- Pytest: 12 passed. Import/undefined-name Ruff checks passed. The Windows selector-loop test covers asynchronous execution, stdout/stderr, Gateway environment, timeout, and direct npm-shim resolution.

## Persistence audit (2026-11-14)

- The existing local SQLite database contains 4 processing runs, 24 extracted items, 0 production tasks, 0 feedback rows, and 4 memory-operation rows. Runs 3 and 4 have 9 and 8 extracted items respectively and remain failed with the OpenClaw output-token-limit error; their extracted items remain attached to their run IDs. The project history response and `/api/runs/4` each return run 4 with 8 extractions and no tasks.
- The production page previously fetched project assets but did not restore `runs[0]` into React state. That caused extracted data to disappear from the view on navigation/refresh even though it remained in SQLite. It now hydrates the latest run and assets from persisted project history and reloads on application data refresh.
- The current database has 1 completed initialization row, 3 completed recall rows (each records 0 retrieved historical entries), and 0 retain rows. There are no feedback records. Thus there is no local evidence of a successfully retained, reusable preference for the current dataset.
- Real Hindsight list and recall calls from the backend runtime currently fail with `ConnectError`. The updated API returns HTTP 503 with the provider error instead of a generic 500. Actual Hindsight contents and retention cannot be verified while this connectivity failure persists. A previous isolated integration run did verify retain/recall; that earlier result does not establish current bank contents or current connectivity.
- Regression coverage now verifies failed OpenClaw synthesis preserves extracted SQLite rows and exposes them through both history APIs; failed Hindsight recall is recorded as a failed memory operation; Hindsight API connectivity failures return 503; and production history hydration restores persisted data. Current tests: backend 16 passed; frontend 2 passed; TypeScript typecheck passed.
- Port 8000 was held by PID 32460 (`python.exe`, Anaconda installation), which matched the backend process recorded from the prior task. It was restarted with the workspace virtualenv (Uvicorn launcher PID 54716; server worker/listener PID 47796). Its real SQLite project/run APIs return HTTP 200 and Hindsight list returns HTTP 503 with `ConnectError`.
- The frontend API fallback is port 8001, where a separate Python listener also serves the same SQLite run history (HTTP 200). Its Hindsight list response is HTTP 503 with upstream HTTP 400. Both configured API paths therefore currently lack usable Hindsight evidence; the port 8001 listener was left untouched.

## Current integration blocker

The final live end-to-end attempt used a fresh isolated database and real services. Groq extraction, Hindsight recall, and verified Hindsight retention succeeded. OpenClaw then returned HTTP 503 with this underlying Groq error:

`413 Request too large for model openai/gpt-oss-120b in organization service tier on_demand: Limit 8000 TPM, Requested 11700.`

The synthesis prompt contains only extracted requirements, the top four compact Hindsight evidence records, and actual asset data; OpenClaw is configured with a 512 output-token cap. Even with this scope, OpenClaw's real runtime request exceeds the 8K TPM account limit. No OpenClaw synthesis completed, and the isolated verification database contained zero production task rows. The application correctly leaves the run failed instead of claiming success.

The authenticated Groq model catalog contains `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, and `qwen/qwen3.8-27b`; their current on-demand organization TPM limit is 8K. The 20B model and Qwen have the same limit. Prompt Guard models have a 512-token context and are not synthesis models. Groq Compound and Compound Mini were decommissioned on 2026-09-21. No currently available model on this account has a sufficient limit for the present OpenClaw request. A higher Groq tier or further reduction of OpenClaw runtime context is required; no paid plan was purchased.

The earlier isolated integration run did reach Groq and Hindsight. In this persistence audit, however, direct calls from the current backend runtime to Hindsight list and recall failed with `ConnectError`; current Hindsight availability and stored bank contents are unverified. The existing database's completed recall rows reflect prior requests that returned zero results and are not proof of current provider reachability or retained memories.

## Not production-ready

PostgreSQL operations and restore drills, durable object storage, background jobs/retry reconciliation, role administration, database-backed rate limiting, CSRF review, upload scanning, monitoring, privacy/retention policy, security review, and production deployment validation remain open. The requested visual screenshot comparison and full Playwright workflow also remain unverified.
