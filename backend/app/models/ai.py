from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TZDateTime


class AIRecommendation(Base):
    """A stored agent response.

    `input_fingerprint` is a hash of the exact structured context sent to the
    agent. If the user's finances have not materially changed, the fingerprint
    matches and we serve this row instead of paying for inference again.
    """

    __tablename__ = "ai_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    agent: Mapped[str] = mapped_column(String(40), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    context_sent: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(60))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_stale: Mapped[bool] = mapped_column(default=False, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)

    __table_args__ = (
        Index("ix_ai_lookup", "user_id", "agent", "input_fingerprint"),
        Index("ix_ai_recent", "user_id", "agent", "created_at"),
    )
