# FRAMEOPS Project Status

Updated: 2026-11-14 (Post-Integration & Handover Audit)

## Teammate Branch & Repository Audit Summary

- **Repository**: `HNK69/FrameOS`
- **PR #1**: `feat: add client feedback intelligence pipeline` by `Lakshmivenkatesha` (`feature/feedback-intelligence` → `main`)
  - Status: **Merged & Verified** (Commit `4568f50`).
  - Additions: `ClientFeedback` model, Alembic revision `a891c354b0f2`, audio transcription endpoint, feedback router `backend/app/routers/feedback.py`, client confirmation flow.
  - Fixes Applied: Resolved `ExtractedItem` model dump crash where schema-only attributes (`kind`, `memory_class`) exceeded table columns.
- **PR #2**: `feat: agency production workflow and operational intelligence layer` by `gagan-dk` (`feature/production-intelligence` → `main`)
  - Status: **Merged & Verified** (Commit `01aaa24`).
  - Additions: `production_intelligence.py` router, `asset_intelligence.py`, `production_analytics.py`, and interactive Next.js `ProductionWorkspace`.
  - Fixes Applied: Resolved merge conflicts in `README.md`, `backend/app/main.py`, and `frontend/components/app-shell.tsx`.
- **Teammate Branch `origin/Deekshith`**:
  - Status: **Audited, Modularized & Packaged as PR Branch `feature/client-portal`** (Pushed to `origin/feature/client-portal` at Commit `85df332`).
  - Audit: Branch had **no existing PR**. Contained portal models (`ClientPortalAccess`, `ReviewVersion`, `VideoComment`, `ClientFeedbackSubmission`) and frontend portal pages (`/portal`, `/portal/projects/[id]`), but branched from pre-PR #1 head (`05cc8ac7f846`), creating an Alembic multi-head conflict. It also contained 700+ lines directly appended to `backend/app/main.py`.
  - Resolution: Extracted portal endpoints into `backend/app/routers/portal.py`, re-chained migration `a1b2c3d4e5f6` to descend from `a891c354b0f2`, added `backend/tests/test_portal.py`, verified all 27 tests and 8 frontend routes, and pushed to `feature/client-portal` for formal teammate PR review (never silently merged into `main`).

---

## Live Provider Verification Status

1. **Groq Cloud API (`openai/gpt-oss-120b`, `whisper-large-v3`)**:
   - Status: **Operational with Backoff Retries**.
   - Transcript structured requirement extraction returns HTTP 200 with 100% valid schema matching `ExtractedRequirements`.
   - Free/On-Demand Tier constraint: 8,000 TPM limit. When rapid sequential calls trigger HTTP 429, the newly added exponential backoff retry in `backend/app/services/groq.py` (`attempt * 2s` sleep) smoothly resolves and prevents workflow crashes.
2. **Hindsight Cloud Memory Layer (`https://api.hindsight.vectorize.io`)**:
   - Status: **Verified Live**.
   - Verified bank creation (`ensure_bank`), preference retention (`retain`), semantic recall (`recall` returning score 1.0), and cleanup (`delete_bank`).
   - Confirmed client isolation: separate client bank IDs prevent cross-client memory leakage.
3. **OpenClaw Gateway CLI (`ws://127.0.0.1:18789`)**:
   - Status: **Operational with Compact Context**.
   - Node 24.22.1 and OpenClaw CLI 2026.11.3 run reliably in Windows subprocess execution.
   - Fixed payload extraction bug in `_extract_text` (previously grabbed top-level `runId` metadata instead of payload text).
   - Agent `frameops-synth` operates under a 512-token max output limit. Because `openai/gpt-oss-120b` generates 350-490 reasoning tokens, synthesis instructions were calibrated to be concise (1 target DaVinci Resolve task, under 15 words per field), ensuring total output fits within ~150 tokens without hitting `stopReason: length` truncation.

---

## Automated Test Counts

- **Backend `main` Pytest**: **24 passed, 0 failed** (`backend/.venv/Scripts/python -m pytest backend/tests`).
- **Backend `feature/client-portal` Pytest**: **27 passed, 0 failed** (includes `test_portal.py`).
- **Frontend Unit Tests**: **2 passed, 0 failed** (`npm test`).
- **Frontend Production Build**: **Passes cleanly with 0 TypeScript/ESLint errors** across all static/dynamic routes.
- **Alembic Migration Reversibility**: Tested linear chain `05cc8ac7f846` → `a891c354b0f2` → `a1b2c3d4e5f6` (upgrades and downgrades verified on isolated SQLite database).

---

## Operational Database & Storage State

- `backend/frameops.db`: Strictly preserved. A pristine backup exists at `backend/frameops.db.safe_backup` (git-ignored).
- `backend/.env`: Strictly preserved and excluded from version control.
- Workspace and tenant boundaries are enforced across all routers (`/api/feedback`, `/api/production-analytics`, `/api/portal`).
