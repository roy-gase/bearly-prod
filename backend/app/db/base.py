"""Declarative base and portable column types.

Nothing here is SQLite-specific: the same metadata runs on PostgreSQL by
changing BEARLY_DATABASE_URL alone.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Money is stored as fixed-point decimal, never float. Numeric(14, 2) maps to
# NUMERIC on SQLite and NUMERIC(14,2) on PostgreSQL.
Money = Numeric(14, 2)
Rate = Numeric(7, 4)  # e.g. an APR of 24.9900 percent
Qty = Numeric(18, 6)


class UTCDateTime(TypeDecorator):
    """Timezone-aware datetimes that behave identically on SQLite and PostgreSQL.

    SQLite has no native timestamptz: it stores whatever it is handed and reads
    it back naive, so a comparison that works on PostgreSQL raises TypeError
    locally. This normalises both directions — always stored as UTC, always
    returned UTC-aware — so application code never has to know which backend it
    is talking to.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


TZDateTime = UTCDateTime()


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


ZERO = Decimal("0.00")
