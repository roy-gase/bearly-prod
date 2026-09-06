# Deploying Bearly

This repository is the production configuration. For local development, see
the Quick start in `README.md` — that path uses SQLite and needs no credentials.

---

## What differs from the dev app

| | Development | Production |
|---|---|---|
| Database | SQLite file | PostgreSQL 16 |
| Schema | `create_all()` at startup | Alembic migrations, run before the server starts |
| Server | `uvicorn --reload`, 1 process | gunicorn + uvicorn workers |
| Frontend | Vite dev server | Static build served by nginx |
| API docs | `/docs` open | Disabled |
| Password reset | Token returned in the response | Emailed over SMTP; **never** returned |
| Failed logins | Unlimited | Account locks after N attempts |
| Host header | Anything | `TrustedHostMiddleware` allowlist |
| CORS | `localhost:5173` | Exact origins; wildcards refused |
| Secret key | Insecure default | Required, ≥32 chars, refuses to boot otherwise |
| HSTS | Off | On |

The application code is otherwise identical — the same finance engine, the same
agents, the same chat.

---

## Deploy

```bash
cp .env.production.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # → BEARLY_SECRET_KEY
$EDITOR .env
docker compose up -d --build
```

Then put a TLS terminator in front of it. Nothing in the stack terminates HTTPS;
`web` listens on `127.0.0.1:8080` expecting a proxy. With Caddy that is two lines:

```
bearly.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

Verify:

```bash
docker compose ps                  # all three healthy
curl -s localhost:8080/health      # ok
docker compose logs api | tail
```

### Required settings

The API **refuses to start** without these, by design — each one fails silently
and dangerously if missing:

| Variable | Why it is mandatory |
|---|---|
| `BEARLY_SECRET_KEY` | A known key means anyone can mint valid sessions |
| `POSTGRES_PASSWORD` | No default is safe |
| `BEARLY_SMTP_HOST` | Without email, password reset does nothing and locked-out users can never recover |
| `BEARLY_TRUSTED_HOSTS` | `*` allows Host-header forgery |
| `BEARLY_CORS_ORIGINS` | A wildcard exposes the API to any site |

---

## Deploying to Vercel (everything on one platform)

Frontend and API deploy together. `vercel.json` routes `/api/*` to a Python
serverless function and everything else to the SPA, so the two are **same
origin** — no CORS configuration, and `VITE_API_URL` stays empty.

### Steps

1. **Vercel → Add New Project →** import the repo.
   **Root Directory must be `/` (the repo root)**, not `frontend` — the build
   needs to see both `frontend/` and `api/`.

2. **Add a database.** Vercel → Storage → Create → Postgres (Neon). Connecting
   it sets `POSTGRES_URL` automatically; `api/index.py` maps it to
   `BEARLY_DATABASE_URL`, preferring the pooled URL because a serverless
   function opens a connection per invocation.

3. **Set environment variables:**

   | Key | Value |
   |---|---|
   | `BEARLY_ENVIRONMENT` | `production` |
   | `BEARLY_SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `BEARLY_TRUSTED_HOSTS` | your Vercel hostname, e.g. `bearly.vercel.app` |
   | `BEARLY_CORS_ORIGINS` | the same URL with `https://` |
   | `BEARLY_APP_BASE_URL` | the same `https://` URL |
   | `BEARLY_ALLOW_NO_EMAIL` | `true` until SMTP exists |
   | `BEARLY_AUTO_MIGRATE` | `true` |
   | `VITE_CHAT_STREAMING` | `false` |
   | `BEARLY_AI_PROVIDER` | `stub`, or `anthropic` with `ANTHROPIC_API_KEY` |

4. **Deploy.** Check `https://your-app.vercel.app/health` returns
   `{"status":"ok"}`, then register a user.

### Why these particular settings

**`BEARLY_AUTO_MIGRATE=true`** — there is no shell on Vercel, so
`alembic upgrade head` cannot be run by hand. The function runs it on cold
start instead. Alembic is idempotent, so once the schema is current it is a
fast no-op.

**`VITE_CHAT_STREAMING=false`** — Vercel's Python runtime buffers responses, so
Server-Sent Events would arrive all at once at the end and look like a hang.
The client asks for a single buffered reply instead. The content is identical;
there is a test asserting it.

**Postgres is required.** SQLite cannot work: the filesystem is ephemeral and
read-only, so every cold start would lose all data.

### Limits worth knowing

- **Cold starts.** The first request after idle pays for the Python runtime
  booting, the imports, and the migration check — several seconds.
- **60-second function ceiling.** Fine for chat turns (a few seconds), but this
  is a hard cap.
- **Connection pooling matters.** Use the pooled database URL. An unpooled
  endpoint runs out of connection slots as invocations scale.

If any of those become a problem, `render.yaml` in this repo deploys the same
`backend/Dockerfile` as a persistent service, where none of them apply — real
SSE streaming, no cold starts, a long-lived connection pool.


---

## Migrations

The schema belongs to Alembic. `init_db()` raises in production rather than
running `create_all`, which would silently skip existing tables and let the
database drift from the migration history.

The API container runs `alembic upgrade head` before gunicorn starts, so a
deploy can never serve against an older schema than the code expects.

```bash
docker compose exec api alembic current      # where the database is
docker compose exec api alembic history      # what exists
docker compose exec api alembic downgrade -1 # roll back one
```

After changing a model:

```bash
docker compose exec api alembic revision --autogenerate -m "what changed"
docker compose exec api alembic check        # confirms no drift remains
```

**Review every generated migration.** Autogenerate does not know your data. In
particular, adding a `NOT NULL` column to a populated table fails without a
`server_default` — the lockout migration in `alembic/versions/` shows the fix.

---

## Backups

The database is the whole product. Volume snapshots are not enough on their own.

```bash
docker compose exec -T db pg_dump -U bearly bearly | gzip > bearly-$(date +%F).sql.gz

gunzip -c bearly-2026-09-05.sql.gz | docker compose exec -T db psql -U bearly bearly
```

Automate it, store off-host, and **restore from a backup at least once** before
you rely on it.

---

## Operating notes

**Scaling.** `BEARLY_WORKERS` × the per-worker pool (5 + 10 overflow) must stay
under Postgres `max_connections` (default 100). Four workers is comfortable;
past eight, add PgBouncer rather than raising the limit.

**Streaming.** Chat replies over SSE. `proxy_buffering off` in `nginx.conf` and
the 120s gunicorn timeout both matter — with buffering on, answers arrive only
when the stream closes, which looks like a hang.

**Logs.** Access logs deliberately omit query strings: transaction filters carry
amounts and search terms. Validation errors never echo submitted values.

**AI cost.** `BEARLY_AI_PROVIDER=stub` runs the whole app with no inference and
no spend — a valid production configuration if you want the finance engine
without the model. With `anthropic`, `GET /api/v1/ai/usage` reports token spend
per user.

**Rotating the secret key** signs every session out. That is the intended
response to a suspected leak.

---

## What is not included

Deliberate omissions, so you know what you are taking on:

- **No rate limiting on registration.** Login is protected by account lockout,
  but signup and password-reset requests are not throttled. Put a WAF or a
  proxy-level rate limit in front, or add Redis-backed limiting.
- **No log aggregation, metrics, or error tracking.** Logs go to stdout for the
  container runtime to collect.
- **No automated backups.** The commands are above; wiring them to a schedule is
  yours.
- **Untested against a live PostgreSQL.** See below.

---

## Verification status

Verified on the build machine:

- 87 backend tests pass
- Alembic migrations apply, roll back, and re-apply cleanly; `alembic check`
  reports no drift
- The lockout migration was applied to a database **already containing users**,
  and backfilled without data loss
- Every table compiles as valid PostgreSQL DDL (`NUMERIC(14,2)`,
  `TIMESTAMP WITH TIME ZONE`, `JSON`)
- Production mode refuses a default/short secret key, wildcard hosts, wildcard
  CORS, and a missing SMTP host
- The frontend builds with no backend host baked in

**Not verified — no Docker or PostgreSQL on the build machine:**

- The images have never been built
- The stack has never been run
- Migrations have never been executed against a real PostgreSQL server
- SMTP delivery has never been exercised against a real mail server

Migrations were validated against SQLite plus PostgreSQL DDL compilation, which
catches schema errors but not server-side behaviour. **Run `docker compose up
--build` against a staging database before production.**
