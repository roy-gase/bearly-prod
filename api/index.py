"""Vercel serverless entrypoint.

Vercel's Python runtime looks for a module-level ASGI app, so this exposes the
same FastAPI application the container image runs — no separate code path.

The whole backend lives in ../backend, which vercel.json bundles via
includeFiles, so it has to go on sys.path before the import.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Vercel Postgres and the Neon integration export these names; the app reads
# BEARLY_DATABASE_URL. Map whichever is present, preferring a pooled URL —
# serverless opens a connection per invocation, and an unpooled endpoint runs
# out of slots quickly.
def _clean_pg_url(url: str) -> str:
    """Strip query parameters libpq does not understand.

    Vercel's POSTGRES_PRISMA_URL carries Prisma-only options such as
    `pgbouncer=true` and `connection_limit`; psycopg rejects the whole URL with
    `invalid URI query parameter`. Anything libpq does not own is dropped.
    """
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url)
    if not parts.query:
        return url
    # Options libpq actually accepts; everything else is an ORM-ism.
    keep = {
        "sslmode", "sslrootcert", "sslcert", "sslkey", "connect_timeout",
        "application_name", "options", "target_session_attrs", "channel_binding",
    }
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k in keep]
    return urlunsplit(parts._replace(query=urlencode(kept)))


if not os.getenv("BEARLY_DATABASE_URL"):
    # POSTGRES_URL first: it is the plain pooled URL. The Prisma variant is a
    # last resort because its extra parameters have to be stripped.
    for candidate in ("POSTGRES_URL", "DATABASE_URL", "POSTGRES_PRISMA_URL"):
        value = os.getenv(candidate)
        if value:
            os.environ["BEARLY_DATABASE_URL"] = _clean_pg_url(value)
            break

def _migrate() -> None:
    """Bring the schema up to date on cold start.

    There is no shell on Vercel, so `alembic upgrade head` cannot be run by hand.
    Alembic is idempotent: once the database is current this is a fast no-op that
    only reads alembic_version. A failure is logged rather than raised, so a
    migration problem does not turn every request into a 500 with no diagnostics.
    """
    import logging

    log = logging.getLogger("bearly.migrate")
    try:
        from alembic import command
        from alembic.config import Config

        cfg = Config(str(BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND / "alembic"))
        command.upgrade(cfg, "head")
        log.info("Schema is up to date")
    except Exception as exc:  # noqa: BLE001
        log.error("Migration failed on cold start: %s: %s", type(exc).__name__, exc)


if os.getenv("BEARLY_AUTO_MIGRATE", "").lower() in ("1", "true", "yes"):
    _migrate()

from app.main import app  # noqa: E402  — must follow the sys.path setup

__all__ = ["app"]
