# Deploy, Maintain, and Runbook

This guide is the practical ops reference for this project:
- what components exist and where they are hosted
- how to deploy safely
- how to maintain and operate the system
- how to start everything locally for development

## 1) System Topology

Core services:
- `apps/web` (Next.js): frontend UI
- `apps/api` (FastAPI): API + orchestration
- `apps/api` worker process (RQ): background indexing/extraction jobs
- Postgres: application data + chat history + document metadata
- Redis: queue backend for background work
- Object storage: local filesystem in dev, S3-compatible in staging/prod
- OpenAI API: embeddings + chat/verify model calls

High-level flow:
1. User uploads a file from web.
2. API stores document metadata, uploads file, enqueues indexing job.
3. Worker processes extraction/chunking/embedding and writes chunks.
4. Chat/verify endpoints retrieve grounded chunks and return results.

## 2) Environment and Secrets

Backend env templates:
- `apps/api/.env.example`
- `apps/api/.env.staging.example`
- `apps/api/.env.production.example`

Frontend env template:
- `apps/web/.env.example`

Minimum critical backend variables:
- `DATABASE_URL`
- `REDIS_URL`
- `OPENAI_API_KEY`
- `STORAGE_BACKEND` (`local` or `s3`)
- `S3_BUCKET` (required when `STORAGE_BACKEND=s3`)
- `ADMIN_API_TOKEN` (required for admin/ops endpoints)
- `MIN_ADMIN_API_TOKEN_BYTES` (recommended: `32`)

Operational guidance:
- never commit real secrets to git
- rotate keys on schedule and after any leak suspicion
- keep separate credentials per environment (dev/staging/prod)
- never place admin tokens in frontend or `NEXT_PUBLIC_*` variables

## 3) Deployment Checklist

Before deploy:
1. Confirm migrations are up-to-date (`alembic upgrade head` in target env).
2. Confirm `GET /health`, `/health/ready`, and `/health/worker` behave as expected.
3. Confirm CORS allowlist is set to exact frontend domains.
4. Confirm worker can connect to Redis and process a test job.
5. Confirm storage backend credentials and bucket/prefix access.
6. Confirm rate-limit/quota settings are intentional for that environment.

Deploy order:
1. Deploy API.
2. Run DB migrations.
3. Deploy/restart worker(s).
4. Deploy frontend.
5. Run smoke tests (session -> meeting -> upload -> chat -> verify).

After deploy:
1. Verify API readiness endpoint is green.
2. Verify worker count is non-zero.
3. Upload one sample doc and confirm it reaches `indexed`.
4. Check failed queue/dead-letter trends for first 15-30 minutes.

## 4) Maintenance Runbook

Daily checks:
1. API health endpoints: `GET /health`, `GET /health/ready`, `GET /health/worker`.
2. Queue depth and failed jobs.
3. Error-rate and latency anomalies.
4. Storage growth and DB size trends.

Weekly checks:
1. Dependency updates (security + bugfixes).
2. Rotate logs and verify retention policy.
3. Review quotas/rate limits against real traffic.
4. Validate backups and recovery path.

Incident quick actions:
- Worker backlog growing:
  - scale workers up temporarily
  - inspect failed jobs and extraction timeouts
  - verify Redis health and connectivity
- API unhealthy:
  - check DB connectivity and pool exhaustion
  - check Redis connectivity for queue-related routes
  - verify upstream/OpenAI network availability
- High OpenAI cost spike:
  - disable `OPENAI_API_KEY` in hosting secrets immediately
  - restart API + worker services so the key is no longer usable
  - rotate to a new key and re-enable only after traffic review
  - tighten quotas/rate limits before re-enable
  - inspect traffic and job volume for abuse or loops
  - review model usage per endpoint

## 5) Local: Start Everything

Use 4 terminals.

Terminal 1: infra services
```bash
cd meeting-notes
docker compose up -d db redis
docker compose ps
```

Terminal 2: backend API
```bash
cd meeting-notes/apps/api
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
set -a; source .env; set +a
./.venv/bin/alembic upgrade head
./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 3: worker
```bash
cd meeting-notes/apps/api
set -a; source .env; set +a
./scripts/run_worker_local.sh
```

Terminal 4: frontend
```bash
cd meeting-notes/apps/web
npm install
npm run dev -- --port 3010
```

Verify local runtime:
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/health
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/health/ready
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/health/worker
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3010
```

Expected:
- API endpoints return `200`
- web returns `200`
- worker terminal shows it is listening on queue `default`

## 6) Local: Stop Everything

Stop processes in API/worker/web terminals with `Ctrl+C`, then:

```bash
cd meeting-notes
docker compose down
```

## 7) References

- Base deployment notes: `infra/deployment.md`
- API contract: `backendap.md`
- Web local run notes: `apps/web/README.md`

## 8) GitHub Auto-Deploy Setup

This repo includes `.github/workflows/deploy.yml`:
- triggers on every push to `main`
- can also be run manually from GitHub Actions (`workflow_dispatch`)
- sends deploy-hook POSTs for API, worker, and web
- runs API post-deploy health checks when `PROD_API_BASE_URL` is configured

Set these GitHub repository secrets in:
`Settings -> Secrets and variables -> Actions -> New repository secret`

Required:
- `API_DEPLOY_HOOK_URL`
- `WORKER_DEPLOY_HOOK_URL`
- `WEB_DEPLOY_HOOK_URL`

Optional (recommended):
- `PROD_API_BASE_URL` (example: `https://api.yourdomain.com`)

Notes:
- Deploy hooks are available on platforms like Vercel/Render/Railway/Fly (service-dependent).
- Keep hooks secret; they are effectively deploy credentials.
- If any required deploy-hook secret is missing, the deploy workflow fails fast.
