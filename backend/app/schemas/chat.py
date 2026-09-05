from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    tool_calls: List[dict] = Field(default_factory=list)
    provider: Optional[str] = None
    model: Optional[str] = None
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    last_message_at: Optional[datetime] = None


class ConversationDetail(ConversationOut):
    messages: List[ChatMessageOut] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
