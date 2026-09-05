from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# Pin the test environment BEFORE app.core.config is imported.
#
# Environment variables outrank .env, so this holds even once a real key is
# configured for local use. Without it the suite makes live, billed API calls
# and the chat assertions become flaky against real model output.
os.environ["BEARLY_ENVIRONMENT"] = "development"
os.environ["BEARLY_AI_PROVIDER"] = "stub"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["TENKI_API_KEY"] = ""

from app.db.base import Base  # noqa: E402
from app.db.session import get_db, get_session_factory  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def db_engine():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(conn, _rec):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    import app.models  # noqa: F401

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
    os.unlink(path)


@pytest.fixture()
def client(db_engine):
    TestingSession = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # Streaming endpoints open their own session; point that at the test DB too.
    app.dependency_overrides[get_session_factory] = lambda: TestingSession
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def register(client, email="a@example.com", password="Sup3rSecret!pw"):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body


@pytest.fixture()
def auth(client):
    headers, _ = register(client)
    return headers
