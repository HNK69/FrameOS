# FRAMEOPS TODO

## Immediate synthesis blocker

- [ ] Resolve the Groq on-demand limit: account limit is 8,000 TPM; real OpenClaw synthesis requested 11,700 tokens and returned HTTP 413. The app prompt is compacted and the FRAMEOPS Gateway agent has a 512-token output cap, no skills/bootstrap injection, and no tools. Further reduce Gateway runtime context or obtain an account tier with a sufficient limit (requires purchase approval).
- [ ] Re-run `backend/scripts/live_workflow.py` after the above fix. Require completed OpenClaw synthesis, non-empty persisted production tasks, actual Hindsight recall/retention verification, and verified test-bank deletion before marking complete.
- [ ] Do not treat `/api/ready` or successful extraction/recall as proof of complete workflow.

## Integration verification

- [x] Verify Windows asyncio subprocess handling, timeout, output capture, and existing Gateway URL/token forwarding.
- [x] Install and verify portable Node.js 24.22.1 and OpenClaw CLI 2026.11.3 for the backend.
- [x] Verify configured Groq and Hindsight connectivity from the backend runtime.
- [x] Verify real Groq extraction, Hindsight bank initialization, retain and recall through a loopback Uvicorn run with an isolated database.
- [ ] Complete a real OpenClaw synthesis and verify production task rows; latest run failed at the provider's 8K TPM limit before task insertion.
- [ ] Run the two-client same-transcript/correction/isolation scenario after synthesis is unblocked.
- [ ] Capture a 1440x900 screenshot and compare with the supplied reference; Playwright visual run remains outstanding.

## Production hardening

- [ ] Add invite flow and owner/admin/editor/viewer permission matrix.
- [ ] Add database-backed rate limiting and CSRF protections for cookie-authenticated mutations.
- [ ] Replace local upload storage with private object storage and expiring authorized downloads.
- [ ] Add MIME sniffing, malware scanning, upload retention controls, and download audit records.
- [ ] Add durable workflow jobs/outbox, provider retries, leases, and operation reconciliation after restarts.
- [ ] Implement workspace/client offboarding, Hindsight export/deletion verification, and retention policy UI.
- [ ] Validate PostgreSQL migrations, automated backups, and restore procedure.
- [ ] Add structured traces, metrics, provider health probes, error reporting, and alerting.
- [ ] Run dependency audit, security review, tenant-isolation tests, and privacy review.
- [ ] Add full multi-role auth tests and end-to-end Playwright scenarios.
- [ ] Configure production S3-compatible storage and deployment secrets.
- [ ] Verify production deployment configuration before any public release.
