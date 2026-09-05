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

## Deploying with Vercel

Vercel hosts the **frontend**. The API runs elsewhere.

### Why the API is not on Vercel

Vercel's Python functions are serverless, and three things in this app do not fit:

- **The chat streams over SSE.** Serverless Python buffers the response, so a
  reply arrives all at once at the end — or times out first.
- **Function duration is capped.** A chat turn that runs tool calls takes several
  seconds; a planner turn can exceed the limit.
- **Database connections are per-invocation.** A long-lived pool is impossible,
  and Postgres connection slots exhaust quickly without an external pooler.

So: frontend on Vercel, API on a host that runs a persistent process. `render.yaml`
in this repo does exactly that. Railway, Fly.io and any container host work too —
they all build `backend/Dockerfile`.

### 1. Deploy the API

Render → **New** → **Blueprint** → select this repo. It creates the API and a
managed PostgreSQL instance. Fill in the variables marked `sync: false`.

`BEARLY_SECRET_KEY` is generated for you. Migrations run automatically on every
deploy — the container executes `alembic upgrade head` before gunicorn starts.

Note the resulting hostname, e.g. `bearly-api.onrender.com`.

### 2. Deploy the frontend

Vercel → **Add New Project** → select this repo → set **Root Directory** to
`frontend`. `frontend/vercel.json` supplies the build settings.

Add one environment variable:

```
VITE_API_URL = https://bearly-api.onrender.com
```

This is a **build-time** variable — Vite inlines it. Changing it later requires a
redeploy, not just a restart.

### 3. Connect the two

Back on Render, set these to your Vercel URL:

```
BEARLY_CORS_ORIGINS  = https://your-app.vercel.app
BEARLY_APP_BASE_URL  = https://your-app.vercel.app
BEARLY_TRUSTED_HOSTS = bearly-api.onrender.com
```

`BEARLY_TRUSTED_HOSTS` is the **API's** hostname, not the frontend's — it
validates the Host header arriving at the API.

### Two 404s this configuration fixes

**`/api/...` returned 404.** With `VITE_API_URL` empty, the browser calls
same-origin `/api/...`. That works locally only because the Vite dev server
proxies it; a built bundle has no proxy, and Vercel serves no API. Setting
`VITE_API_URL` points the browser at the real API.

**Refreshing on `/login` returned 404.** Vue Router owns those paths; no such
file exists in `dist/`. The rewrite in `frontend/vercel.json` returns
`index.html` for non-asset paths so the router can take over.

### If the chat appears to hang

Some proxies buffer Server-Sent Events, so the reply lands all at once instead of
streaming. Two mitigations, in order:

1. Point `VITE_API_URL` straight at the API (as above) rather than routing `/api`
   through a Vercel rewrite. This keeps the CDN out of the streaming path.
2. If it persists, set `VITE_CHAT_STREAMING=false` in Vercel and redeploy. The
   client then asks for `?stream=false` and receives one buffered JSON reply —
   identical content, no incremental typing. There is a test asserting the two
   paths produce the same answer.

### Connection strings

Render, Railway, Heroku and Fly hand out `postgres://...`. SQLAlchemy 2 rejects
that scheme and `postgresql://` selects a driver that is not installed, so the
app rewrites both to `postgresql+psycopg://` at startup. Paste the provider's
value unmodified.

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
