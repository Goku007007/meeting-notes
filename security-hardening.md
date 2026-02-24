# Security Hardening Pack

This document captures the last-mile hardening controls for production/demo deployment.

## 1) Postgres Least-Privilege Roles

Run the following once as a Postgres superuser (adjust names/passwords/DB name):

```sql
-- 1) Create roles
CREATE ROLE meetingnotes_app LOGIN PASSWORD 'REPLACE_ME';
CREATE ROLE meetingnotes_migrator LOGIN PASSWORD 'REPLACE_ME';

-- 2) Lock down default public access
REVOKE ALL ON DATABASE meetingnotes FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;

-- 3) Grant DB connect
GRANT CONNECT ON DATABASE meetingnotes TO meetingnotes_app;
GRANT CONNECT ON DATABASE meetingnotes TO meetingnotes_migrator;

-- 4) Migrator can manage schema
GRANT USAGE, CREATE ON SCHEMA public TO meetingnotes_migrator;

-- 5) App can only use schema
GRANT USAGE ON SCHEMA public TO meetingnotes_app;

-- 6) After migrations create tables, grant table privileges to app
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO meetingnotes_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO meetingnotes_app;

-- 7) Ensure future tables/sequences inherit correct perms
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO meetingnotes_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO meetingnotes_app;
```

Use in deployment:
- API runtime user: `meetingnotes_app`
- Alembic migration user/job: `meetingnotes_migrator`

## 2) CI Security Checks

This repo includes a dedicated security workflow:
- `.github/workflows/security.yml`

It runs:
- Python dependency audit (`pip-audit`) for `apps/api`
- Node dependency audit (`npm audit`) for `apps/web`
- CodeQL analysis for Python + JavaScript/TypeScript

## 3) Trusted Proxy / Client IP Handling

Never trust `X-Forwarded-For` by default.

Only trust it when:
- the app is deployed behind a known reverse proxy/load balancer, and
- the trusted proxy range is configured at the platform/runtime layer.

Otherwise, use socket source IP (`request.client.host`) for rate limiting and abuse controls.

## 4) Operational Notes

- Keep rate limiting state in Redis (not in-process memory) for multi-instance correctness.
- Run workers with CPU/memory limits and non-root user.
- Prefer restricted worker egress where possible.
- Keep uploads in private storage (local private path in dev, S3/private bucket in prod).
