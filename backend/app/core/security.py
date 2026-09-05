"""Password hashing and token issuing.

Passwords are hashed with bcrypt and never stored or logged in plaintext.
Refresh and password-reset tokens are random secrets; only their SHA-256
digests are persisted, so a database leak does not yield usable tokens.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

ALGORITHM = "HS256"
_ACCESS = "access"


def _prehash(password: str) -> bytes:
    """bcrypt silently truncates past 72 bytes; hashing first keeps the whole
    password significant and makes long passphrases safe."""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(password), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, expires_minutes: int | None = None) -> tuple[str, datetime]:
    minutes = expires_minutes or settings.access_token_minutes
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": _ACCESS,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": secrets.token_urlsafe(8),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return token, expires_at


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != _ACCESS:
        return None
    return payload


def generate_opaque_token() -> tuple[str, str]:
    """Return (plaintext, sha256 digest). Only the digest is stored."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
