# Client feedback API

All endpoints use the existing authenticated `frameops_session` cookie or bearer token. The server derives the workspace from the authenticated membership and checks project ownership. The API does not accept workspace or Hindsight bank identifiers. Requests are asynchronous; use polling rather than SSE or WebSockets because processing is short lived and deployments currently have no shared event broker.

## Submit and poll

`POST /api/feedback` accepts JSON `{ "project_id": 12, "text": "..." }` and returns `202` with a feedback record. `POST /api/feedback/audio?project_id=12` accepts multipart `file` and returns the same record. Both accept an `Idempotency-Key` header (up to 120 characters). Audio accepts MP3, WAV, M4A, MP4 audio, WebM, OGG, and FLAC, bounded by `max_upload_bytes` (25 MiB by default). The private original file remains at a random server-generated storage path; the path is never returned.

Poll `GET /api/feedback/{id}`. Status progresses through `queued`, `processing`, `awaiting_confirmation`, `confirmed`, and `delivered`, or `failed`. `stage` reports transcription/extraction. Failed records include an error and attempt count; `POST /api/feedback/{id}/retry` queues one retry and accepts only failed records. Audio records include transcript provider/model/time provenance. Text records preserve the original submitted text as their transcript.

Structured response `extracted` contains requests with `kind` (request, revision, style_preference, constraint, duration, clarification), `classification`, source quote, confidence, confirmation requirement, and `memory_class`; top-level fields include a readable `summary`, ambiguities, questions, missing information, risks, and required assets. `memory_class` distinguishes project-specific, temporary revision, reusable preference, explicitly confirmed preference, and editor correction. Extraction does not itself confirm a reusable preference.

## Client review and agency delivery

`PATCH /api/feedback/{id}/confirmation` accepts `{ "summary": "...", "extracted": { ... } }`; `extracted` is optional. The client can edit the readable summary and structured fields. This action records explicit client confirmation and unlocks delivery. `GET /api/agency/feedback?status=confirmed` lists the workspace's confirmed feedback for the agency inbox. `POST /api/agency/feedback/{id}/deliver` records delivery exactly once and returns the feedback payload; it is idempotent after delivery.

## Memory and operations boundary

Client submissions and confirmation provenance are stored independently from existing editor task feedback. This router does not write Hindsight memories or change memory retention policy. It preserves classification for the project owner's existing Groq → Hindsight → OpenClaw integration to consume. `editor_correction` must only be assigned from editor-authored data, never inferred from client text.

## Known limitations

Processing uses FastAPI in-process background tasks and polling. A server restart during a provider request can leave a record `processing`; a durable queue/lease reconciler is not implemented. Audio storage uses the existing local upload directory and needs private object storage for a shared deployment. This service relies on the authenticated workspace identity already in the app; a separate client identity/portal authorization flow is not implemented by this backend change. Audio validation checks extension and declared MIME type, but production MIME sniffing and malware scanning remain necessary. Live Groq transcription/extraction requires configured credentials and has not been represented as successful by unit tests.
