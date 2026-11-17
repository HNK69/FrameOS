# FRAMEOPS Architecture

## System Architecture

```text
Next.js 15 UI (Agency Dashboard & Client Portal)
                │ Dynamic API Proxy: Next.js rewrites() -> process.env.BACKEND_URL (default: 8001)
                │ REST + JSON / multipart (HttpOnly Session Cookie / Client Portal Bearer Token)
                ▼
FastAPI Backend (Security Headers: nosniff, SAMEORIGIN, strict-origin-when-cross-origin)
                │
                ├── Modular Routers:
                │   ├── backend/app/main.py (Core API, auth, clients, projects, runs, tasks, memory)
                │   ├── backend/app/routers/feedback.py (Feedback intake, audio Whisper, deliver, convert-task)
                │   ├── backend/app/routers/production_intelligence.py (Analytics, asset intelligence, adaptive knowledge)
                │   └── backend/app/routers/portal.py (Client portal auth, review versions, video comments, review submission)
                │
                ├── Persistence: SQLAlchemy 2.0 ORM + SQLite WAL Mode (PRAGMA journal_mode=WAL, busy_timeout=5000)
                │   └── Linear Alembic Chain: 05cc8ac7f846 -> a891c354b0f2 -> a1b2c3d4e5f6
                │
                ├── AI Resiliency Layer:
                │   ├── Groq Cloud: Whisper audio & token chunker (<=4,000 tokens) with 429 exponential backoff
                │   ├── Hindsight Cloud: Tenant memory banks with graceful degradation fallback to empty memories ([])
                │   └── OpenClaw Gateway CLI: Local agentic DaVinci Resolve task synthesis via Windows off-loop execution
                │
                └── Storage Adapter: Local disk storage with workspace scoping & Content-Disposition attachment downloads
```

---

## Modular Routers & Endpoint Separation

The API endpoints are organized into modular, independently tested FastAPI routers:

1. **Core Application Router (`backend/app/main.py`)**:
   - Workspace initialization, owner setup, HttpOnly session cookie authentication, and user profile management (`/api/auth/*`, `/api/me`).
   - Project and client CRUD with workspace scoping (`/api/clients`, `/api/projects`).
   - Production processing pipeline (`POST /api/process-transcript`) coordinating Groq extraction, Hindsight preference recall, and OpenClaw synthesis.
   - Global HTTP security middleware and CORS policy allowing `X-Portal-Token`.
   - Asset download handler with `Content-Disposition: attachment` sanitization to prevent SVG stored XSS.

2. **Feedback Intelligence Pipeline (`backend/app/routers/feedback.py`)**:
   - Structured client feedback intake (`POST /api/feedback`) and audio upload with Groq Whisper transcription (`POST /api/feedback/audio`).
   - Client confirmation flow (`PATCH /api/feedback/{id}/confirmation`).
   - Agency feedback management (`GET /api/agency/feedback`, `POST /api/agency/feedback/{id}/deliver`).
   - Feedback-to-production task conversion (`POST /api/agency/feedback/{id}/convert-task`) with `source="client_feedback"` and query-based idempotency.

3. **Production Intelligence & Operational Analytics (`backend/app/routers/production_intelligence.py`)**:
   - Operational production analytics (`GET /api/production-analytics`): completion velocity, priority distribution, task duration metrics.
   - Evidence-based asset intelligence (`GET /api/projects/{id}/asset-intelligence`): extracted requirement to asset correlation.
   - Adaptive client knowledge (`GET|POST /api/clients/{id}/adaptive-knowledge`): structured client styling and brand guidelines.

4. **Client Review Portal (`backend/app/routers/portal.py`)**:
   - Secure portal authentication (`POST /api/portal/auth/login`) with Argon2 passcode verification and token expiration enforcement.
   - Project review version management and metadata retrieval (`GET /api/portal/projects/{id}`).
   - Timestamped video review comments (`GET|POST /api/portal/projects/{id}/comments`).
   - Review approval/change-request submissions (`POST /api/portal/projects/{id}/submit-review`), automatically triggering Hindsight retention for confirmed preferences.
   - Partial content media streaming endpoint (`GET /api/portal/assets/{id}/stream`).

---

## Security Architecture & Tenant Boundaries

### 1. Authentication & Portal Security Remediation
- **Elimination of Passwordless Login Bypass**: In `backend/app/routers/portal.py`, all authentication requires either `data.code` (passcode) or `data.token` (access token). Submitting only an email address returns `HTTP 401 Unauthorized`.
- **Argon2 Passcode Hashing**: Client passcodes are stored hashed with Argon2 (`verify_password`). Expiration timestamps (`expires_at`) are strictly enforced against timezone-aware UTC.
- **Client Identity Resolution**: `backend/app/security.py:current_client_identity` rejects plaintext passcode matches, accepting only valid signed JWTs or unexpired access tokens.
- **Cross-Client Isolation**: Clients cannot access projects, reviews, or comments outside their authorized tenant scope; unauthorized attempts return `HTTP 404 Not Found`.

### 2. HTTP Security Headers & Safe Downloads
- Global middleware injects:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: SAMEORIGIN`
  - `Referrer-Policy: strict-origin-when-cross-origin`
- CORS configuration includes `"X-Portal-Token"` in `allow_headers`.
- File downloads (`/api/assets/{id}/download`) enforce `Content-Disposition: attachment; filename="{safe_filename}"` and `nosniff`, preventing browser script execution on uploaded SVG and HTML files.

---

## AI Pipeline Resiliency & Memory Sync

### 1. Token-Aware Chunking & Rate Limit Handling
- **Sliding-Window Chunker**: Rather than enforcing a rigid character cutoff, `chunk_transcript_tokens(text, max_tokens=4000, overlap_tokens=200)` splits long transcripts into overlapping segments along paragraph and sentence boundaries.
- **Rate Limit Exponential Backoff**: Both `groq.transcribe_audio` and `extract_feedback` handle HTTP 429 rate limits with exponential backoff (2s, 4s, 6s retries) to stay within Groq's on-demand 8,000 TPM limit.

### 2. Hindsight Graceful Degradation Fallback
- When Hindsight Cloud is unreachable, `process_transcript` intercepts exceptions, logs a `MemoryOperation(status="degraded")`, and falls back to empty memories (`[]`). This allows downstream OpenClaw synthesis to complete rather than terminating the user's workflow.

### 3. Client Preference Synchronization
- When clients confirm preferences during portal review submissions, `submit_portal_feedback` calls `hindsight.retain_and_verify` to asynchronously persist preferences into the tenant's dedicated memory bank (`frameops-w{wid}-c{uuid}`).

---

## Database Architecture & Linear Migrations

### Linear Alembic Migration Chain
1. `05cc8ac7f846_initial_schema.py`: Base tables (`workspaces`, `users`, `memberships`, `clients`, `projects`, `transcripts`, `processing_runs`, `extracted_items`, `production_tasks`, `assets`, `memory_operations`).
2. `a891c354b0f2_client_feedback_pipeline.py`: Added `client_feedback` table.
3. `a1b2c3d4e5f6_client_portal_schema.py`: Added `client_portal_access`, `review_versions`, `video_comments`, and `client_feedback_submissions`.

### SQLite Concurrency & Invariants
- Enabled SQLite WAL mode (`PRAGMA journal_mode=WAL`) and 5,000ms busy timeout (`PRAGMA busy_timeout=5000`) in `backend/app/db.py` to ensure high-concurrency read/write safety.
- Certified active database at revision `a1b2c3d4e5f6` preserving all 144 pre-existing operational records.
- Pre-migration timestamped backup verified at `backend/frameops.db.backup_20261115_003535` and `backend/frameops.db.safe_backup`.

---

## Frontend Architecture & Full-Stack Integration

- **Framework**: Next.js 15 (App Router), React 19, TailwindCSS 4, TanStack React Query 5.
- **Dynamic Port Architecture**: Frontend connects to the backend dynamically using `process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"`. Next.js API `rewrites()` in `frontend/next.config.ts` forward `/api/:path*` requests seamlessly.
- **Portal UI Styling**: 284 lines of CSS isolated under `.portal-*` selectors in `frontend/app/globals.css`.
- **Hydration Resiliency**: `ProductionWorkspace` invokes `restoreProductionProject(projectData)` upon page revisit to hydrate active run state, tasks, and asset intelligence.

---

## Multi-Tier Verification Matrix

| Tier | Scope | Execution | Result |
|---|---|---|---|
| **Layer A** | Backend Unit & Security Tests (Mocked) | `pytest backend/tests -v` | **35 passed, 0 failed** (100% pass) |
| **Layer A** | Frontend Workspace Hydration Tests | `npm test` | **2 passed, 0 failed** (100% pass) |
| **Layer A** | Frontend Next.js Production Build | `npm run build` | **0 errors** across all 8 routes |
| **Layer B** | Live Groq Cloud Models API | HTTP GET `/models` | **HTTP 200 OK** |
| **Layer B** | Live Hindsight Cloud Memory Layer | HTTP GET `/v1/default/banks` | **HTTP 200 OK** |
| **Layer B** | Live OpenClaw Gateway Daemon | Loopback socket check (`127.0.0.1:18789`) | **Socket Open & Connected** |
| **Layer B** | Live End-to-End Workflow Script | `backend/scripts/live_workflow.py` | Isolated workflow runner available |
