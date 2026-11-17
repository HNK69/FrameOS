# FRAMEOPS

**Remember Every Client. Perfect Every Project.**

FRAMEOPS is a two-sided video production operations platform connecting clients and video-editing agencies. It provides two distinct, fully functional experiences:

1. **Client Platform**: Where clients register, discover agencies in a public catalog, submit structured project briefs, upload media assets, communicate with agencies, review proposals, track production, and approve deliverables.
2. **Agency Platform**: Where agencies register, manage public profiles and portfolios, receive project requests, submit proposals, track clients, process feedback with AI, and manage production workflows.

---

## Architecture & Product Capabilities

### 1. Two-Sided Authentication & Role-Aware RBAC
- **Independent Registration**: Dedicated registration flows for clients (`POST /api/auth/register/client`) and agencies (`POST /api/auth/register/agency`).
- **Role-Aware Sessions**: Single login endpoint (`POST /api/auth/login`) dynamically issues persona tokens (`role="client"` or `role="agency_owner"` / `role="agency_member"`).
- **Argon2id Password Security**: Password hashing via Argon2id (`pwdlib`) with secure HTTP-only cookies (`frameops_client_session` and `frameops_session`).

### 2. Agency Discovery & Profile Catalog
- **Public Catalog**: `GET /api/discovery/agencies` allows clients to search, filter by specialization and services, and browse agency portfolios.
- **Publishing Safeguards**: Agencies must complete minimum requirements (description, contact email, at least one specialization and service) before publishing (`POST /api/agency/profile/publish`).
- **Unpublished Isolation**: Unpublished agencies are strictly hidden from public discovery and return 404 to non-members.

### 3. Project Briefs, Requests & Proposals
- **Structured Project Briefs**: Clients submit detailed briefs (`POST /api/client/requests`) with target platform, aspect ratio, duration, budget, deadlines, and editing instructions.
- **Agency Inbox & Review**: Agencies receive briefs in their inbox (`GET /api/agency/requests`), with client drafts automatically hidden.
- **Proposals & Turnaround**: Agencies submit custom proposals (`POST /api/agency/requests/{id}/proposals`) with scope, turnaround days, and deliverables summary.
- **Proposal Acceptance & Project Activation**: When a client accepts a proposal (`POST /api/client/requests/{id}/proposals/{id}/accept`), other proposals are declined and an active production project is automatically created in the agency workspace.
- **Direct Messaging**: Chronological clarification thread (`/api/requests/{id}/messages`) between client and agency.

### 4. Video Production Operations & Adaptive Memory
- **Dedicated Memory Banks**: Isolated Hindsight memory bank for each client.
- **AI Feedback Extraction**: Groq Whisper and LLM extraction turning feedback into structured requests.
- **DaVinci Resolve Task Synthesis**: OpenClaw gateway generating actionable editing instructions.
- **Review Portal**: Video playback with timestamped comments, versioning, and client decisions.

---

## Current Implementation & Completed Milestones

### Milestone 1: Database & Concurrency Hardening
- **SQLite WAL Mode & Busy Timeout**: Configured SQLite Write-Ahead Logging (`PRAGMA journal_mode=WAL`) and a 5,000ms busy timeout (`PRAGMA busy_timeout=5000`) in `backend/app/db.py` to prevent database locking during concurrent API requests.
- **Linear Alembic Schema**: Migrated active database to `a1b2c3d4e5f6` (`client_portal_schema`), descending from `a891c354b0f2` (`client_feedback_pipeline`) and `05cc8ac7f846` (`initial_schema`).
- **Data Preservation**: All 144 pre-existing operational records preserved intact across all core tables (`users`, `workspaces`, `clients`, `projects`, `transcripts`, `processing_runs`, `extracted_items`, `memory_operations`).
- **Safe Backup Protocol**: Timestamped snapshot verified and preserved at `backend/frameops.db.backup_20261115_003535` and `backend/frameops.db.safe_backup`.

### Milestone 2: Security & Authentication Remediation
- **Elimination of Passwordless Login Bypass**: Completely removed the insecure email-only authentication bypass in `backend/app/routers/portal.py`. All portal logins strictly require a valid passcode or access token; submitting an email alone returns `HTTP 401 Unauthorized`.
- **Argon2 Passcode Hashing**: Integrated cryptographic passcode verification using Argon2 (`verify_password`) and enforce timezone-aware UTC token expiration (`expires_at`).
- **Client Identity Hardening**: Removed plaintext passcode comparison in `backend/app/security.py:current_client_identity`; strictly requires valid signed JWTs or active unexpired access tokens.
- **HTTP Security Headers Middleware**: Added global middleware setting `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, and `Referrer-Policy: strict-origin-when-cross-origin`.
- **CORS Hardening**: Explicitly enabled `"X-Portal-Token"` in `CORSMiddleware.allow_headers`.
- **Safe Attachment Downloads**: Configured `Content-Disposition: attachment; filename="{safe_filename}"` and `X-Content-Type-Options: nosniff` in `download_asset` to mitigate SVG stored XSS.

### Milestone 3: AI Pipeline Resiliency & Memory Sync
- **Groq Transcription 429 Exponential Backoff**: Wrapped `groq.transcribe_audio` in a 4-attempt exponential backoff retry loop (2s, 4s, 6s) matching `extract_feedback` to gracefully handle on-demand 8K TPM rate limits.
- **Token-Aware Sliding-Window Chunker**: Implemented `chunk_transcript_tokens(text, max_tokens=4000, overlap_tokens=200)` in `backend/app/services/groq.py`. Transcripts exceeding 4,000 tokens (~16,000 characters) are chunked along natural sentence/paragraph boundaries with overlap, extracting requirements per chunk and merging/deduplicating them.
- **Hindsight Graceful Degradation Fallback**: Wrapped `hindsight.recall` in `process_transcript` with exception handling. If Hindsight Cloud is unreachable or times out, the pipeline records `MemoryOperation(status="degraded")` and proceeds with empty historical memories (`[]`), allowing OpenClaw DaVinci task synthesis to succeed without failing the user run.
- **Client Preference Memory Sync**: Wired client-confirmed feedback submissions in `submit_portal_feedback` to call `hindsight.retain_and_verify` against the client's tenant memory bank.

### Milestone 4: Client Review Portal Full-Stack Integration
- **Client Review Portal UI**: Integrated complete client review surfaces (`frontend/app/portal/page.tsx` and `frontend/app/portal/projects/[id]/page.tsx`) with 284 lines of ported styling isolated under `.portal-*` selectors in `frontend/app/globals.css`.
- **Interactive Review Features**: Video player with timestamped feedback pins, comment threads, review versions, and client approval/change-request decisions.
- **Navigation Integration**: Added Client Portal links and `"in_review"` project status badge directly into `frontend/components/app-shell.tsx`.
- **Dynamic Port Architecture**: Frontend configured to use dynamic backend ports (defaulting to port `8001`), supporting Next.js API `rewrites()` in `frontend/next.config.ts` mapping `/api/:path*` to `process.env.BACKEND_URL || "http://localhost:8001/api/:path*"`.

### Milestone 5: Feedback-to-Production Workflow & Workspace Hydration
- **Explicit Editor Task Conversion**: Added `POST /api/agency/feedback/{feedback_id}/convert-task` in `backend/app/routers/feedback.py`, allowing agency editors to explicitly convert delivered client feedback into production tasks with `source="client_feedback"` and explicit provenance.
- **Idempotency Enforcement**: Query-based idempotency checks prevent duplicate task generation on repeated clicks, safely returning `already_converted: True` with the existing task.
- **Workspace Hydration Fix**: Fixed `ProductionWorkspace` hydration bug on page revisit by invoking `restoreProductionProject(projectData)` and updating the `useEffect` dependency array (`[projectId, refresh]`). Added interactive "Delivered Client Feedback" banner with direct conversion actions.

### Milestone 6: Multi-Tier Verification & Pre-Push Synchronization
- **Layer A Automated Verification**: All 35 backend pytest tests pass; all 2 frontend unit tests pass; Next.js production build compiles with 0 errors across all 8 static and dynamic routes.
- **Layer B Live Provider Verification**: Groq Cloud API, Hindsight Cloud Memory Layer, and local OpenClaw Gateway daemon verified operational with live credentials and socket checks.
- **Git Branch Invariants & Checkpoint 2**: Local `main` is ahead of `origin/main` by clean commits with zero remote divergence (`git rev-list --count main..origin/main == 0`). All teammate branches (`origin/Deekshith`, `origin/feature/feedback-intelligence`, `origin/feature/production-intelligence`, `branch-*`) and backup branches (`backup/*`) preserved intact. Awaiting explicit user push sign-off.

---

## Local Setup

### Requirements
- Python 3.12+
- `uv` (recommended) or `pip` / `venv`
- Node.js 20+ (Node.js 24.16+ for OpenClaw Gateway)
- npm

### 1. Configuration (.env)
Copy `.env.example` to `backend/.env`. Configure your environment variables:
```ini
AUTH_SECRET=your-secure-random-secret
PORT=8001
DATABASE_URL=sqlite:///./frameops.db
FRONTEND_ORIGIN=http://localhost:3000
CORS_ORIGINS=http://localhost:3000
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=openai/gpt-oss-120b
HINDSIGHT_API_URL=https://api.hindsight.vectorize.io
HINDSIGHT_API_TOKEN=your-hindsight-token
OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18789
OPENCLAW_AUTH_TOKEN=your-openclaw-token
OPENCLAW_AGENT_ID=frameops-synth
```

### 2. Backend Startup
```powershell
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8001
```

### 3. Frontend Startup
In a separate terminal:
```powershell
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:3000` and automatically proxies `/api/*` requests to the backend at `http://localhost:8001` via Next.js `rewrites()`.

---

## API Outline

### Core & Authentication
- `GET /api/health`: Health status probe.
- `GET /api/ready`: Provider configuration readiness probe.
- `GET /api/auth/status`: Check initial setup completion.
- `POST /api/auth/setup`: Initialize workspace and owner account.
- `POST /api/auth/login`: Workspace owner sign-in (sets HttpOnly cookie).
- `POST /api/auth/logout`: End session.
- `GET /api/me`: Current authenticated user identity.

### Clients & Projects
- `GET|POST /api/clients`: List or create clients (automatically initializes Hindsight memory bank).
- `GET|PATCH|DELETE /api/clients/{id}`: Client details, updates, and deletion (pauses if Hindsight is unreachable).
- `GET|POST /api/projects`: List or create projects. Supports status `"active"`, `"in_review"`, `"archived"`.
- `GET|PATCH|DELETE /api/projects/{id}`: Project management.

### Production Pipeline
- `POST /api/process-transcript`: Extract structured requirements (Groq token chunker), recall client preferences (Hindsight with graceful fallback), and synthesize DaVinci Resolve tasks (OpenClaw CLI).
- `GET /api/runs/{id}`: Polling endpoint for processing run lifecycle and extractions.
- `GET /api/tasks`: List production tasks with filters.
- `GET|PATCH /api/tasks/{id}`: Task detail and editor status updates (`pending`, `in_progress`, `completed`).
- `POST /api/tasks/{id}/feedback`: Record editor feedback and corrections.

### Feedback Intelligence & Agency Bridge
- `POST /api/feedback`: Submit client feedback text (requires `Idempotency-Key`).
- `POST /api/feedback/audio`: Upload client audio feedback for Whisper transcription (with 429 exponential backoff).
- `GET /api/feedback/{id}`: Feedback processing status.
- `PATCH /api/feedback/{id}/confirmation`: Client confirmation of extracted requirements.
- `GET /api/agency/feedback`: Agency view of all feedback items across workspace projects.
- `POST /api/agency/feedback/{id}/deliver`: Mark feedback delivered to production.
- `POST /api/agency/feedback/{id}/convert-task`: Convert delivered client feedback into production task (`source="client_feedback"`, idempotent).

### Production Intelligence & Analytics
- `GET /api/production-analytics`: Operational metrics, completion velocity, and workload distribution.
- `GET /api/projects/{id}/asset-intelligence`: Evidence-based asset tracking.
- `GET|POST /api/clients/{id}/adaptive-knowledge`: Client-specific knowledge extraction.

### Client Review Portal
- `POST /api/portal/auth/login`: Client portal authentication via passcode or access token (Argon2 verified; email-only rejected with 401).
- `GET /api/portal/projects/{id}`: Client-scoped project view with review versions and assets.
- `GET|POST /api/portal/projects/{id}/comments`: Timestamped video comments and threaded discussions.
- `POST /api/portal/projects/{id}/submit-review`: Submit client approval or change requests (syncs confirmed preferences to Hindsight memory bank).
- `GET /api/portal/assets/{id}/stream`: Media streaming endpoint supporting HTTP 206 Partial Content.

---

## Testing & Verification

### Layer A: Automated Offline Unit & Mock Tests
Run on every commit without external API dependencies:

```powershell
# Backend automated test suite (35 tests)
backend\.venv\Scripts\pytest.exe backend\tests -v

# Frontend unit tests (2 tests)
npm --prefix frontend test

# Frontend production build
npm --prefix frontend run build
```

*Results:*
- **Backend pytest**: 35 passed, 0 failed. Covers security auth, token expiration, client tenant isolation, SVG download protection, Groq chunker, Hindsight degradation fallback, feedback idempotency, and OpenClaw process wrappers.
- **Frontend unit tests**: 2 passed, 0 failed. Covers workspace hydration and run state restoration.
- **Frontend build**: 8/8 static and dynamic routes compile cleanly with 0 TypeScript/ESLint errors.

### Layer B: Live Provider Smoke Tests
Explicitly separated from automated mock tests:
- **Live Groq API**: Verified HTTP 200 via `https://api.groq.com/openai/v1/models`.
- **Live Hindsight Cloud**: Verified HTTP 200 via `https://api.hindsight.vectorize.io/v1/default/banks`.
- **Live OpenClaw Gateway**: Verified local daemon socket connectivity at `ws://127.0.0.1:18789`.
- **Live End-to-End Workflow**: Run `python backend/scripts/live_workflow.py` to exercise the full live pipeline against an isolated temporary database on port 8000.

---

## Git & Repository Disposition

- **Active Branch**: `main`
- **Teammate Contributions Preserved**:
  - `origin/Deekshith`: Ported into `feature/client-portal` and merged into `main`. Original branch preserved intact.
  - `origin/feature/feedback-intelligence` (PR #1): Merged into `main`. Original branch preserved intact.
  - `origin/feature/production-intelligence` (PR #2): Merged into `main`. Original branch preserved intact.
  - Snapshot branches: `backup/main-pre-sync`, `backup/client-portal-pre-sync`, `backup/deekshith-pre-sync` preserved intact.
- **Pre-Push Status**: 0 remote divergence (`git rev-list --count main..origin/main == 0`). Ready for user sign-off at Checkpoint 2.
