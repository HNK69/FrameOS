# FRAMEOPS Architecture

## System Architecture

```text
Next.js UI (Agency Dashboard & Client Portal)
                │ REST + JSON / multipart (HttpOnly Session Cookie / Bearer)
                ▼
FastAPI Backend (Modular Routers: auth, clients, projects, production, feedback, portal)
                │
                ├── SQLAlchemy 2.0 ORM (SQLite local / PostgreSQL deployment)
                ├── Groq Cloud API: Structured requirement extraction & Whisper transcription
                ├── Hindsight Cloud Memory Layer: Client-specific memory banks (retain/recall/reflect)
                ├── OpenClaw Gateway CLI: Local agentic DaVinci Resolve task synthesis
                └── Storage Adapter: Local disk storage with workspace scoping (object storage in prod)
```

## Modular Routers & Endpoint Separation

The API endpoints are organized into modular FastAPI routers:
1. `backend/app/main.py`: Core application setup, authentication, clients, projects, processing runs, tasks, and memory.
2. `backend/app/routers/feedback.py`: Client feedback intake, audio upload with Whisper transcription, client confirmation, and agency delivery tracking.
3. `backend/app/routers/production_intelligence.py`: Operational production analytics, project asset intelligence, and client adaptive knowledge synthesis.
4. `backend/app/routers/portal.py`: Public client portal tokens, video review versions, timestamped comments, and structured client feedback submissions.

## Tenant and Memory Boundaries

- **Workspace Scoping**: The initial setup creates a workspace owner. Session claims encode user ID and workspace ID. All mutations and queries enforce workspace scoping to eliminate cross-tenant leakage.
- **Hindsight Memory Isolation**: Each client has an application-managed `memory_bank_id`. Client briefs and feedback are recalled only against that client's specific bank ID, guaranteeing zero cross-client memory leakage.
- **SQLite Operational Truth vs Hindsight Adaptive Truth**: SQLite records all immutable operational events (transcripts, runs, extracted items, tasks, comments, feedback). Hindsight persists distilled, confirmed client preferences with provenance tags (author, source document, confirmation timestamp).

## Database Schema & Linear Alembic Migrations

The Alembic migration chain is strictly linear:
1. `05cc8ac7f846_initial_schema.py`: Workspaces, users, memberships, clients, projects, processing runs, extracted items, production tasks, assets, and memory operations.
2. `a891c354b0f2_client_feedback_pipeline.py` (PR #1): Added `client_feedback` table for audio/text feedback records and delivery tracking.
3. `a1b2c3d4e5f6_client_portal_schema.py` (Prepared PR Branch `feature/client-portal`): Added `client_portal_access`, `review_versions`, `video_comments`, and `client_feedback_submissions` tables.

All migrations are fully reversible and tested for clean `upgrade head` and `downgrade -1`.

## Synthesis & AI Provider Constraints

- **Groq Cloud API (`openai/gpt-oss-120b`)**: Used for structured requirement extraction. Implements exponential backoff retries (`attempt * 2s`) to handle the on-demand 8K TPM rate limit safely.
- **OpenClaw Gateway CLI (`frameops-synth`)**: Orchestrates task synthesis via WebSocket connection (`ws://127.0.0.1:18789`). Operates with a 512-token output cap. Because `openai/gpt-oss-120b` produces ~350-490 reasoning tokens, the synthesis prompt strictly limits generated DaVinci Resolve tasks to concise instructions (under 15 words per field), preventing output truncation.
