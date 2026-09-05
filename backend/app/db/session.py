from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_connect_args = {"check_same_thread": False} if settings.is_sqlite else {}

_pool_args = (
    {}
    if settings.is_sqlite
    else {"pool_size": settings.db_pool_size, "max_overflow": settings.db_max_overflow,
          "pool_recycle": 1800}
)

engine: Engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
    **_pool_args,
)

if settings.is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - driver glue
        """SQLite ignores foreign keys unless asked; PostgreSQL always enforces them.

        Turning them on locally keeps dev behaviour identical to production.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_session_factory():
    """The session factory, as a dependency.

    Streaming endpoints outlive the request-scoped session, so they open their
    own. Injecting the factory rather than importing SessionLocal directly keeps
    those endpoints overridable in tests instead of silently writing to the real
    database.
    """
    return SessionLocal


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables directly — development only.

    In production the schema is owned by Alembic (`alembic upgrade head`), so
    this refuses to run: create_all silently skips existing tables and would let
    a schema drift out of sync with the migration history without complaint.
    """
    if settings.is_production:
        raise RuntimeError(
            "init_db() is disabled in production. Run `alembic upgrade head` instead."
        )
    from app import models  # noqa: F401  (registers mappers)

    models.Base.metadata.create_all(bind=engine)
