# FRAMEOPS TODO

## Completed in Handover & Milestones 1–6

- [x] Complete GitHub repository and branch audit (`HNK69/FrameOS`, PR #1, PR #2, branch `Deekshith`).
- [x] Integrate verified PR #1 (`feature/feedback-intelligence`) into `main`.
- [x] Fix schema mismatch crash in `ExtractedItem` model dump during extraction persistence.
- [x] Integrate verified PR #2 (`feature/production-intelligence`) into `main` and resolve UI/router conflicts.
- [x] Resolve Alembic multi-head conflict between PR #1 and branch `Deekshith`; linearize migration chain.
- [x] Package unmerged branch `Deekshith` into clean, modularized PR branch `feature/client-portal` with dedicated router `backend/app/routers/portal.py` and unit tests in `test_portal.py`.
- [x] **Milestone 1**: Database & concurrency hardening (enable SQLite WAL mode, busy timeout 5000ms, linear migration to `a1b2c3d4e5f6`, 144 operational rows preserved, safe backups verified).
- [x] **Milestone 2**: Security & authentication remediation (eliminate passwordless email login bypass, Argon2 passcode verification, unexpired token enforcement, HTTP security headers, CORS `X-Portal-Token`, safe attachment downloads, 5 automated security tests).
- [x] **Milestone 3**: AI pipeline resiliency & memory sync (Groq Whisper 429 exponential backoff, sliding-window chunking >4,000 tokens, Hindsight graceful degradation fallback to empty memories, client-confirmed preference memory sync).
- [x] **Milestone 4**: Client review portal full-stack integration (284 lines ported `.portal-*` CSS, portal navigation links in `app-shell.tsx`, dynamic Next.js API `rewrites()` and port 8001 fallbacks, 8 routes compiled).
- [x] **Milestone 5**: Feedback-to-production workflow (`POST /api/agency/feedback/{id}/convert-task` with `source="client_feedback"` and query-based idempotency, `ProductionWorkspace` hydration bug fix on revisit).
- [x] **Milestone 6**: QA, multi-tier verification & Checkpoint 2 pre-push protocol (35 backend tests passing, 2 frontend unit tests passing, Next.js build clean across 8 routes, live provider connectivity verified, 0 remote divergence, all branches preserved intact).
- [x] Update `README.md`, `ARCHITECTURE.md`, `PROJECT_STATUS.md`, and `TODO.md`.

## Immediate Next Steps (Pending User Push Authorization - Checkpoint 2)

- [ ] Obtain explicit user approval to execute `git push origin main`.
- [ ] Push `main` to `origin/main` and verify synchronized commit hashes.
- [ ] Verify PR #1 and PR #2 merge status on GitHub.
- [ ] Seed interactive demo data (e.g. LUXE STUDIO vs. FITCORE) for client demonstration walkthrough.

## Production Hardening (Future Roadmap)

- [ ] Implement team member invitations and owner/admin/editor/viewer RBAC matrix.
- [ ] Add Redis-backed rate limiting and CSRF protection for cookie-authenticated mutation endpoints.
- [ ] Migrate local disk uploads to S3-compatible private object storage with presigned URLs.
- [ ] Add background task worker (Celery/ARQ) for asynchronous long-running synthesis and transcription jobs.
- [ ] Configure production PostgreSQL database with automated backups and disaster recovery runbooks.
- [ ] Add centralized OpenTelemetry tracing, Prometheus metrics, and error alerting (Sentry).
