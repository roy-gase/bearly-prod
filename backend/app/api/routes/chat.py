"""Chat endpoints.

The reply streams over Server-Sent Events so text appears as it is generated and
tool calls surface the moment they run.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Annotated, Callable, Iterator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, owned_or_404, owned_query
from app.db.session import get_session_factory
from app.models import ChatConversation, ChatMessage
from app.schemas.chat import (
    ChatMessageOut,
    ConversationDetail,
    ConversationOut,
    SendMessageRequest,
)
from app.services.ai import chat as chat_service

logger = logging.getLogger("bearly.chat")
router = APIRouter(prefix="/ai/chat", tags=["chat"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/starters")
def starters(user: CurrentUser) -> dict:
    return {"starters": chat_service.STARTERS, "provider": settings.ai_provider}


@router.get("/conversations", response_model=List[ConversationOut])
def list_conversations(user: CurrentUser, db: DbSession):
    return db.scalars(
        owned_query(ChatConversation, user)
        .order_by(ChatConversation.last_message_at.desc().nullslast(), ChatConversation.id.desc())
        .limit(50)
    ).all()


@router.post("/conversations", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED)
def create_conversation(user: CurrentUser, db: DbSession):
    convo = ChatConversation(user_id=user.id)
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return convo


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: int, user: CurrentUser, db: DbSession):
    return owned_or_404(db, ChatConversation, conversation_id, user)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: int, user: CurrentUser, db: DbSession) -> Response:
    convo = owned_or_404(db, ChatConversation, conversation_id, user)
    db.delete(convo)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/conversations/{conversation_id}/messages")
def send_message(
    conversation_id: int,
    payload: SendMessageRequest,
    user: CurrentUser,
    db: DbSession,
    session_factory: Annotated[Callable, Depends(get_session_factory)],
    stream: bool = Query(
        default=True,
        description="Set false to receive one JSON reply instead of an SSE stream. "
        "Needed behind proxies that buffer streaming responses.",
    ),
):
    """Append the user's turn, then return the assistant's reply.

    Streams over SSE by default. `?stream=false` collects the same events and
    returns a single JSON object, for CDNs and serverless platforms that buffer
    streaming responses — where a stream would arrive all at once at the end, or
    not at all.
    """
    convo = owned_or_404(db, ChatConversation, conversation_id, user)

    user_message = ChatMessage(
        conversation_id=convo.id, role="user", content=payload.content.strip(), created_at=_now()
    )
    db.add(user_message)
    if convo.title == "New conversation":
        convo.title = chat_service.title_from(payload.content)
    convo.last_message_at = _now()
    db.commit()
    db.refresh(convo)

    history = chat_service.build_history(convo)
    user_id = user.id
    convo_id = convo.id

    def event_stream() -> Iterator[str]:
        # The request session closes when the response starts streaming, so the
        # generator opens its own for the tool calls and the final write.
        session = session_factory()
        collected: List[str] = []
        tools_used: List[dict] = []
        meta = {"provider": settings.ai_provider, "model": None, "input_tokens": 0, "output_tokens": 0}
        try:
            from app.models import User

            current = session.get(User, user_id)
            for event in chat_service.stream_reply(session, current, history):
                if event["type"] == "text":
                    collected.append(event["delta"])
                elif event["type"] == "tool":
                    tools_used.append(
                        {"name": event["name"], "label": event.get("label"), "input": event.get("input", {})}
                    )
                elif event["type"] == "meta":
                    meta.update(
                        {
                            "provider": event.get("provider"),
                            "model": event.get("model"),
                            "input_tokens": event.get("input_tokens", 0),
                            "output_tokens": event.get("output_tokens", 0),
                        }
                    )
                    continue
                yield "data: %s\n\n" % json.dumps(event)

            text = "".join(collected).strip() or "I could not put an answer together — try rephrasing?"
            reply = ChatMessage(
                conversation_id=convo_id,
                role="assistant",
                content=text,
                tool_calls=tools_used,
                provider=meta["provider"],
                model=meta["model"],
                input_tokens=meta["input_tokens"],
                output_tokens=meta["output_tokens"],
                created_at=_now(),
            )
            session.add(reply)
            stored = session.get(ChatConversation, convo_id)
            if stored:
                stored.last_message_at = _now()
            session.commit()
            session.refresh(reply)
            yield "data: %s\n\n" % json.dumps(
                {"type": "done", "message_id": reply.id, "tools_used": tools_used,
                 "provider": meta["provider"], "model": meta["model"]}
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Chat stream failed: %s", type(exc).__name__)
            yield "data: %s\n\n" % json.dumps(
                {"type": "error", "message": "Something went wrong generating that reply."}
            )
        finally:
            session.close()

    if not stream:
        collected_text, tool_log, done_event = [], [], None
        for frame in event_stream():
            if not frame.startswith("data: "):
                continue
            event = json.loads(frame[6:].strip())
            if event["type"] == "text":
                collected_text.append(event["delta"])
            elif event["type"] == "tool":
                tool_log.append(
                    {"name": event["name"], "label": event.get("label"),
                     "input": event.get("input", {})}
                )
            elif event["type"] in ("done", "error"):
                done_event = event
        if done_event is not None and done_event.get("type") == "error":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=done_event["message"]
            )
        return {
            "role": "assistant",
            "content": "".join(collected_text),
            "tool_calls": (done_event or {}).get("tools_used", tool_log),
            "message_id": (done_event or {}).get("message_id"),
            "provider": (done_event or {}).get("provider"),
            "model": (done_event or {}).get("model"),
        }

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # stops nginx buffering the stream in production
        },
    )
