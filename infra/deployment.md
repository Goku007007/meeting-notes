# Deployment Notes

## Environment Profiles

Backend env templates:
- `apps/api/.env.example` (development)
- `apps/api/.env.staging.example`
- `apps/api/.env.production.example`

Frontend env template:
- `apps/web/.env.example`

## Required Runtime Checks

API:
- `GET /health` (liveness)
- `GET /health/ready` (readiness: DB + Redis queue)
- `GET /health/worker` (worker visibility count)

Worker:
- run `rq worker default --with-scheduler`
- monitor queue depth + failed jobs
- run worker with least-privilege runtime user (non-root)

## Storage Backends

Configure `STORAGE_BACKEND`:
- `local` for dev
- `s3` for staging/prod

S3 mode requires:
- `S3_BUCKET`
- optional `S3_PREFIX`

## Security Controls

- Guest token ownership scoping (`Authorization: Bearer <token>`)
- Per-IP and per-session rate limits
- Daily quotas for uploads/chats/verifies
- Upload MIME/extension allowlist
- Reindex cooldown (`REINDEX_COOLDOWN_SECONDS`)
- Session queue fairness cap (`MAX_ACTIVE_INDEX_JOBS_PER_SESSION`)
- API security headers enabled (CSP, nosniff, referrer policy, frame deny)
- Cookie-auth CSRF protection (`x-csrf-token` + CSRF cookie)
- Admin token required for ops/analytics endpoints (`ADMIN_API_TOKEN`)

CORS:
- dev: localhost origins only
- staging/prod: set explicit frontend domains only; wildcard origins/regex are blocked at startup

Logging/privacy:
- API access logs include request id, hashed session token, route, status, and latency.
- Do not log raw uploaded file content or extracted document text.

Trusted proxy / client IP:
- Only trust `X-Forwarded-For` when deployed behind a known, configured trusted proxy chain.
- Configure trusted proxy CIDRs via `TRUSTED_PROXY_CIDRS` (comma-separated CIDR list).
- If trusted proxy settings are not configured, use `request.client.host` for abuse controls and rate limiting.
- Never blindly trust arbitrary `X-Forwarded-For` headers from direct internet traffic.

Transport security:
- Set `SECURITY_HSTS` in staging/production (recommended: `max-age=31536000; includeSubDomains`) behind HTTPS.

## Timeouts and Concurrency

API server:
- Configure reverse proxy request timeout (recommended: `60s` for API requests).
- Configure upstream connect/read timeouts (recommended: connect `5s`, read `60s`).

Worker jobs:
- `INDEX_JOB_TIMEOUT_SECONDS` controls max indexing job runtime.
- `EXTRACTION_TIMEOUT_SECONDS` controls max file extraction runtime per document.
- `OCR_TIMEOUT_SECONDS` controls OCR call timeout.
- `PDF_MAX_PAGES` caps PDF pages processed by parser/OCR.

Queue/worker concurrency:
- Run bounded worker count, e.g. `rq worker default --with-scheduler` with a fixed process count in your supervisor.
- Start with 2-4 workers in staging and tune based on queue depth and OpenAI spend.
- Keep `MAX_ACTIVE_INDEX_JOBS_PER_SESSION` set to prevent one session from monopolizing workers.

Container/resource hardening:
- apply memory and CPU limits on API/worker containers (prevents parser resource exhaustion)
- keep worker filesystem permissions minimal (read upload storage + write temp only)
- avoid mounting secret files into worker unless required
- prefer no outbound network from worker containers (or strict egress allowlist only)

## OCR

Set `ENABLE_OCR=true` to enable OCR paths.

System dependencies are required:
- Tesseract OCR
- poppler (for PDF->image conversion used by OCR fallback)
