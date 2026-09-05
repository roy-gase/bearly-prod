"""Behaviour that only matters in production: config guards, lockout, email."""
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from tests.conftest import register

API = "/api/v1"
PROD = {"environment": "production", "secret_key": "k" * 40,
        "trusted_hosts": "bearly.app", "cors_origins": "https://bearly.app",
        "smtp_host": "smtp.example.com"}


# --- Configuration refuses to start unsafely -------------------------------


@pytest.mark.parametrize(
    "override, reason",
    [
        ({"secret_key": "dev-insecure-change-me"}, "default secret key"),
        ({"secret_key": "tooshort"}, "weak secret key"),
        ({"trusted_hosts": "*"}, "wildcard host allowlist"),
        ({"cors_origins": "*"}, "wildcard CORS origin"),
        ({"cors_origins": "https://a.com,*"}, "wildcard among CORS origins"),
    ],
)
def test_production_rejects_unsafe_settings(override, reason):
    with pytest.raises(ValidationError):
        Settings(**{**PROD, **override})


def test_valid_production_settings_are_accepted():
    s = Settings(**PROD)
    assert s.is_production
    assert s.trusted_host_list == ["bearly.app"]
    assert s.email_configured


def test_create_all_is_disabled_in_production(monkeypatch):
    """The schema belongs to Alembic; create_all would let it drift silently."""
    from app.db import session as session_module

    monkeypatch.setattr(session_module.settings, "environment", "production")
    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        session_module.init_db()


# --- Brute-force protection ------------------------------------------------


def test_repeated_failures_lock_the_account(client, monkeypatch):
    from app.api.routes import auth as auth_module

    monkeypatch.setattr(auth_module.settings, "max_failed_logins", 3)
    register(client, email="target@example.com")

    for _ in range(3):
        r = client.post(
            f"{API}/auth/login",
            json={"email": "target@example.com", "password": "WrongPassword1!"},
        )
        assert r.status_code == 401

    # Locked now — and the correct password is refused too, which is the point.
    locked = client.post(
        f"{API}/auth/login",
        json={"email": "target@example.com", "password": "Sup3rSecret!pw"},
    )
    assert locked.status_code == 429
    assert "too many" in locked.json()["detail"].lower()


def test_successful_login_clears_the_failure_counter(client, monkeypatch):
    from app.api.routes import auth as auth_module
    from sqlalchemy import select
    from app.models import User

    monkeypatch.setattr(auth_module.settings, "max_failed_logins", 5)
    headers, _ = register(client, email="resets@example.com")

    for _ in range(3):
        client.post(
            f"{API}/auth/login",
            json={"email": "resets@example.com", "password": "WrongPassword1!"},
        )
    ok = client.post(
        f"{API}/auth/login",
        json={"email": "resets@example.com", "password": "Sup3rSecret!pw"},
    )
    assert ok.status_code == 200

    # Counter is back to zero, so a user who mistypes twice is not penalised later.
    for _ in range(4):
        assert client.post(
            f"{API}/auth/login",
            json={"email": "resets@example.com", "password": "WrongPassword1!"},
        ).status_code == 401


def test_lockout_does_not_reveal_whether_an_account_exists(client):
    """An unknown address must never return 429 — that would be an oracle."""
    for _ in range(12):
        r = client.post(
            f"{API}/auth/login",
            json={"email": "ghost@example.com", "password": "WrongPassword1!"},
        )
        assert r.status_code == 401


def test_password_reset_clears_a_lockout(client, monkeypatch):
    from app.api.routes import auth as auth_module

    monkeypatch.setattr(auth_module.settings, "max_failed_logins", 2)
    register(client, email="locked@example.com")
    for _ in range(2):
        client.post(
            f"{API}/auth/login", json={"email": "locked@example.com", "password": "Nope12345!"}
        )
    assert client.post(
        f"{API}/auth/login", json={"email": "locked@example.com", "password": "Sup3rSecret!pw"}
    ).status_code == 429

    token = client.post(
        f"{API}/auth/forgot-password", json={"email": "locked@example.com"}
    ).json()["dev_reset_token"]
    assert client.post(
        f"{API}/auth/reset-password", json={"token": token, "new_password": "Fr3shPassword!"}
    ).status_code == 204

    assert client.post(
        f"{API}/auth/login", json={"email": "locked@example.com", "password": "Fr3shPassword!"}
    ).status_code == 200


# --- Password reset delivery ----------------------------------------------


def test_reset_token_is_emailed_and_never_returned(client, monkeypatch):
    from app.api.routes import auth as auth_module

    sent = {}

    def fake_send(to, token):
        sent["to"] = to
        sent["token"] = token

    monkeypatch.setattr(auth_module.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(auth_module, "send_password_reset", fake_send)
    register(client, email="mailed@example.com")

    body = client.post(f"{API}/auth/forgot-password", json={"email": "mailed@example.com"}).json()
    assert "dev_reset_token" not in body          # never exposed once SMTP is configured
    assert sent["to"] == "mailed@example.com"
    assert sent["token"]

    # The emailed token really works.
    assert client.post(
        f"{API}/auth/reset-password",
        json={"token": sent["token"], "new_password": "Em4iledPassword!"},
    ).status_code == 204


def test_smtp_failure_still_reports_success(client, monkeypatch):
    """Delivery outcome must not be observable, or this becomes an account oracle."""
    from app.api.routes import auth as auth_module
    from app.services.email import EmailError

    def boom(to, token):
        raise EmailError("smtp down")

    monkeypatch.setattr(auth_module.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(auth_module, "send_password_reset", boom)
    register(client, email="bounce@example.com")

    r = client.post(f"{API}/auth/forgot-password", json={"email": "bounce@example.com"})
    assert r.status_code == 200
    assert "dev_reset_token" not in r.json()
