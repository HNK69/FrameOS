# FRAMEOPS TODO

## Completed in this Handover & Audit

- [x] Complete GitHub repository and branch audit (`HNK69/FrameOS`, PR #1, PR #2, branch `Deekshith`).
- [x] Integrate verified PR #1 (`feature/feedback-intelligence`) into `main`.
- [x] Fix schema mismatch crash in `ExtractedItem` model dump during extraction persistence.
- [x] Integrate verified PR #2 (`feature/production-intelligence`) into `main` and resolve UI/router conflicts.
- [x] Resolve Alembic multi-head conflict between PR #1 and branch `Deekshith`; linearize migration chain.
- [x] Package unmerged branch `Deekshith` into clean, modularized PR branch `feature/client-portal` with dedicated router `backend/app/routers/portal.py` and unit tests in `test_portal.py`.
- [x] Verify live Hindsight Cloud bank creation, preference retention, semantic recall, and bank deletion.
- [x] Verify live Groq API extraction and add exponential backoff retry for HTTP 429 rate limits.
- [x] Resolve OpenClaw payload extraction bug in `_extract_text` to prevent capturing metadata `runId`.
- [x] Calibrate OpenClaw synthesis prompt to fit the 512-token max output limit alongside `openai/gpt-oss-120b` reasoning tokens.
- [x] Verify all automated test suites: 24 backend tests on `main`, 27 backend tests on `feature/client-portal`, and clean Next.js production builds.
- [x] Update `README.md`, `ARCHITECTURE.md`, `PROJECT_STATUS.md`, and `TODO.md`.

## Immediate Next Steps (Demonstration Readiness)

- [ ] Submit PR on GitHub for branch `feature/client-portal` (`HNK69/FrameOS`) for teammate review.
- [ ] Merge `feature/client-portal` into `main` once peer review is approved.
- [ ] Upgrade Groq API tier or configure a non-reasoning extraction model if higher TPM is required for multi-task bulk processing.
- [ ] Seed interactive demo data (e.g. LUXE STUDIO vs. FITCORE) for client demonstration walkthrough.

## Production Hardening

- [ ] Implement team member invitations and owner/admin/editor/viewer RBAC matrix.
- [ ] Add Redis-backed rate limiting and CSRF protection for cookie-authenticated mutation endpoints.
- [ ] Migrate local disk uploads to S3-compatible private object storage with presigned URLs.
- [ ] Add background task worker (Celery/ARQ) for asynchronous long-running synthesis and transcription jobs.
- [ ] Configure production PostgreSQL database with automated backups and disaster recovery runbooks.
- [ ] Add centralized OpenTelemetry tracing, Prometheus metrics, and error alerting (Sentry).
