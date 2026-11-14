# FRAMEOPS Architecture

## Runtime shape

```text
Next.js UI (same-site HttpOnly session cookie)
               │ REST + JSON / multipart
               ▼
FastAPI ── SQLAlchemy ── SQLite local / PostgreSQL deployment
   │
   ├── Groq Chat Completions: validated transcript extraction
   ├── Hindsight API: client-bank initialization, recall, retain, reflect, delete
   ├── OpenClaw CLI → authenticated Gateway: production synthesis
   └── Storage adapter (current local disk; object storage required for production)
```

## Tenant and memory boundaries

The first owner setup creates a user, workspace, and owner membership. Session claims identify a user and workspace; API routes derive the workspace from that identity and validate requested client/project ownership. The current product supports one owner account per initialized workspace. The membership table carries a role column for later role administration.

Each client record has a persisted, application-generated `memory_bank_id`. The transcript is never used to construct a bank ID. All Hindsight calls use the bank id resolved from the authenticated project/client relationship. Hindsight remains the source of truth for long-term preference records; PostgreSQL stores mappings, operation state, local activity, and provenance.

## Transcript workflow

1. Persist the transcript and a processing run with an idempotency key.
2. Call Groq with transcript text JSON-encoded as untrusted data; validate JSON against Pydantic models.
3. Recall the correct client bank using the extracted feedback as the query; persist successful and failed retrieval operations with status and error details.
4. Compare extracted required assets with actual project uploads. Absence alone yields `Unknown`; no unverified asset is presented as present.
5. Call the configured `frameops-synth` OpenClaw Gateway agent with compact extracted requirements, up to four ranked Hindsight facts (source/provenance/confirmation/confidence), and actual asset availability. The agent uses a 512-token output cap and a minimal tool profile.
6. Validate synthesized tasks, force confirmation where confidence is below the application threshold, and persist the result. Extracted requirements are committed before recall/synthesis, so provider errors leave the run and its available extractions intact without fabricated tasks. Production history hydrates persisted runs on revisit/refresh.

## Feedback and provenance

Recommendations are immutable in their original fields. Feedback records capture accept/correct/reject, author, timestamp, correction text, client-confirmation status, and retention status. Corrected or explicitly confirmed knowledge is retained in Hindsight with provenance tags and a stable document id; recall verification waits for Hindsight indexing and requires matching source-document identity plus overlap with the distilled content before returning verified status.

## Authentication and security boundaries

- Passwords use the maintained `pwdlib` password hash and JWTs are signed with `AUTH_SECRET`.
- Browser sessions are HttpOnly, SameSite=Lax cookies. `AUTH_COOKIE_SECURE` must be enabled for HTTPS deployment. Local API bearer auth exists for development tooling.
- CORS is an explicit allowlist. Health/readiness and initial setup/login endpoints are public; business data routes require authenticated workspace membership.
- Uploaded files are size-limited, content-type checked, stored under random keys, and served only after workspace authorization.
- Transcript-derived strings are treated as untrusted data and are not executable instructions.

## Persistence and migrations

SQLAlchemy 2.x models are the application schema. Alembic is the migration interface. SQLite is intended for isolated local runs; PostgreSQL should be used for shared deployments. The API startup does not silently create production tables; initialize via `alembic upgrade head`.

## Known limitations

Current local disk upload storage is not durable deployment storage. The app has a single-owner auth flow, no invitations/role admin, no rate limit middleware, no queue/retry worker for slow provider calls, and only foundational activity reporting. Recovery after process interruption during external calls needs a durable job/outbox design. These are production hardening items, not claimed features.

The configured Groq on-demand account currently permits 8K TPM for its available synthesis models. OpenClaw's real runtime request still exceeds that limit after compacting the application prompt and limiting output to 512 tokens; the live workflow therefore fails before production task persistence. No higher-limit model is available in the authenticated account catalog.
