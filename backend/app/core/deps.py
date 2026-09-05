"""Request dependencies: the authenticated user, and ownership enforcement."""
from __future__ import annotations

from typing import Annotated, Optional, TypeVar

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User

_bearer = HTTPBearer(auto_error=False)

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or not credentials.credentials:
        raise CREDENTIALS_ERROR
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise CREDENTIALS_ERROR
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise CREDENTIALS_ERROR
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise CREDENTIALS_ERROR
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]

T = TypeVar("T")


def owned_or_404(db: Session, model: type[T], obj_id: int, user: User) -> T:
    """Fetch a row and prove it belongs to the caller.

    Every financial resource goes through here. A row owned by someone else is
    reported as 404, not 403, so IDs cannot be probed for existence.
    """
    obj = db.get(model, obj_id)
    if obj is None or getattr(obj, "user_id", None) != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{model.__name__} not found"
        )
    return obj


def owned_query(model: type[T], user: User):
    """Base select() already scoped to the caller. Use for every list endpoint."""
    return select(model).where(model.user_id == user.id)
