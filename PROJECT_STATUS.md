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

## Current integration blocker

The final live end-to-end attempt used a fresh isolated database and real services. Groq extraction, Hindsight recall, and verified Hindsight retention succeeded. OpenClaw then returned HTTP 503 with this underlying Groq error:

`413 Request too large for model openai/gpt-oss-120b in organization service tier on_demand: Limit 8000 TPM, Requested 11700.`

The synthesis prompt contains only extracted requirements, the top four compact Hindsight evidence records, and actual asset data; OpenClaw is configured with a 512 output-token cap. Even with this scope, OpenClaw's real runtime request exceeds the 8K TPM account limit. No OpenClaw synthesis completed, and the isolated verification database contained zero production task rows. The application correctly leaves the run failed instead of claiming success.

The authenticated Groq model catalog contains `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, and `qwen/qwen3.8-27b`; their current on-demand organization TPM limit is 8K. The 20B model and Qwen have the same limit. Prompt Guard models have a 512-token context and are not synthesis models. Groq Compound and Compound Mini were decommissioned on 2026-09-21. No currently available model on this account has a sufficient limit for the present OpenClaw request. A higher Groq tier or further reduction of OpenClaw runtime context is required; no paid plan was purchased.

Earlier `ConnectError` reports came from the restricted test execution environment. Under the authorized backend runtime, the provider calls above reached Groq and Hindsight; the present failure is the explicit Groq TPM rejection, not a connection error.

## Not production-ready

PostgreSQL operations and restore drills, durable object storage, background jobs/retry reconciliation, role administration, database-backed rate limiting, CSRF review, upload scanning, monitoring, privacy/retention policy, security review, and production deployment validation remain open. The requested visual screenshot comparison and full Playwright workflow also remain unverified.
