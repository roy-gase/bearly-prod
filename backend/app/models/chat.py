from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, TZDateTime


class ChatConversation(Base, TimestampMixin):
    """One coaching conversation, scoped to a single user."""

    __tablename__ = "chat_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), default="New conversation", nullable=False)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime, index=True)

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.id",
        lazy="selectin",
    )


class ChatMessage(Base):
    """A single turn.

    `tool_calls` records which deterministic functions ran to produce an answer,
    so the user can always see that a figure came from Bearly's engine rather
    than from the model's imagination.
    """

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("chat_conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    provider: Mapped[Optional[str]] = mapped_column(String(20))
    model: Mapped[Optional[str]] = mapped_column(String(60))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)

    conversation: Mapped["ChatConversation"] = relationship(back_populates="messages")

    __table_args__ = (Index("ix_chat_msg_convo", "conversation_id", "id"),)
