"""Registration, login, logout, refresh, password reset, profile."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models import PasswordResetToken, RefreshToken, User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenPair,
    UserOut,
    UserUpdate,
)
from app.services.email import EmailError, send_password_reset
from app.services.seed import seed_default_categories

logger = logging.getLogger("bearly.auth")
router = APIRouter(tags=["auth"])

INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _issue_tokens(db, user: User) -> TokenPair:
    access, expires_at = create_access_token(user.id)
    raw_refresh, refresh_digest = generate_opaque_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=refresh_digest,
            expires_at=_now() + timedelta(days=settings.refresh_token_days),
            created_at=_now(),
        )
    )
    user.last_login_at = _now()
    db.commit()
    return TokenPair(access_token=access, refresh_token=raw_refresh, expires_at=expires_at)


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession) -> TokenPair:
    email = payload.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="An account with that email already exists"
        )

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=(payload.full_name or "").strip() or None,
    )
    db.add(user)
    db.flush()
    seed_default_categories(db, user)
    db.commit()
    db.refresh(user)
    logger.info("User registered id=%s", user.id)  # id only, never the email
    return _issue_tokens(db, user)


LOCKED_OUT = HTTPException(
    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    detail="Too many failed sign-in attempts. Try again shortly.",
)


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: DbSession) -> TokenPair:
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))

    # Refuse early if this account is locked, before spending a bcrypt verify.
    if user is not None and user.locked_until is not None and user.locked_until > _now():
        raise LOCKED_OUT

    # Hash regardless so a missing account and a wrong password take the same time.
    valid = verify_password(payload.password, user.hashed_password if user else "$2b$12$" + "x" * 53)

    if not user or not valid or not user.is_active:
        if user is not None:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.max_failed_logins:
                user.locked_until = _now() + timedelta(minutes=settings.lockout_minutes)
                user.failed_login_attempts = 0
                logger.warning("Account locked after repeated failures id=%s", user.id)
            db.commit()
        raise INVALID_CREDENTIALS

    if user.failed_login_attempts or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None

    return _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    digest = hash_token(payload.refresh_token)
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == digest))
    if token is None or token.revoked_at is not None or token.expires_at <= _now():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is invalid or expired"
        )
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise INVALID_CREDENTIALS
    # Rotate: the presented token is spent.
    token.revoked_at = _now()
    return _issue_tokens(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, user: CurrentUser, db: DbSession) -> Response:
    digest = hash_token(payload.refresh_token)
    token = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == digest, RefreshToken.user_id == user.id
        )
    )
    if token is not None and token.revoked_at is None:
        token.revoked_at = _now()
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(user: CurrentUser, db: DbSession) -> Response:
    tokens = db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
        )
    ).all()
    for t in tokens:
        t.revoked_at = _now()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: DbSession) -> dict:
    """Always reports success so the endpoint cannot enumerate accounts."""
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    response: dict = {
        "message": "If an account exists for that email, a reset link has been sent."
    }

    if user is not None:
        raw, digest = generate_opaque_token()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=digest,
                expires_at=_now() + timedelta(minutes=settings.password_reset_minutes),
                created_at=_now(),
            )
        )
        db.commit()
        logger.info("Password reset requested for user id=%s", user.id)

        if settings.email_configured:
            try:
                send_password_reset(user.email, raw)
            except EmailError as exc:
                # Still report success: whether delivery succeeded must not be
                # observable, or this endpoint becomes an account oracle.
                logger.error("Password reset email failed: %s", exc)
        elif not settings.is_production:
            # Local development without SMTP: surface the token so the flow is
            # testable. Production refuses to start in this state (see below).
            response["dev_reset_token"] = raw
        else:
            logger.error("Password reset requested but SMTP is not configured")

    return response


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(payload: ResetPasswordRequest, db: DbSession) -> Response:
    digest = hash_token(payload.token)
    token = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == digest))
    if token is None or token.used_at is not None or token.expires_at <= _now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Reset link is invalid or expired"
        )
    user = db.get(User, token.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset link is invalid")

    user.hashed_password = hash_password(payload.new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    token.used_at = _now()
    # A password reset ends every existing session.
    for t in db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
        )
    ).all():
        t.revoked_at = _now()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(payload: ChangePasswordRequest, user: CurrentUser, db: DbSession) -> Response:
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect"
        )
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserOut)
def update_me(payload: UserUpdate, user: CurrentUser, db: DbSession) -> User:
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip() or None
    if payload.currency is not None:
        user.currency = payload.currency.upper()
    db.commit()
    db.refresh(user)
    return user
