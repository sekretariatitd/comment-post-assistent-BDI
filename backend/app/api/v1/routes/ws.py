import asyncio
import contextlib
import uuid

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models import User
from app.services import events

router = APIRouter(tags=["live updates"])


async def _authenticated(token: str) -> bool:
    try:
        user_id = uuid.UUID(decode_access_token(token)["sub"])
    except (jwt.InvalidTokenError, ValueError, KeyError):
        return False
    async with SessionLocal() as db:
        user = await db.get(User, user_id)
    return user is not None and user.is_active


@router.websocket("/ws/queue")
async def queue_events(ws: WebSocket, token: str = Query(default="")) -> None:
    """Pushes draft.created / draft.updated / post.created events as JSON text frames.
    Browsers can't set headers on WebSockets, so the JWT comes as ?token=."""
    if not await _authenticated(token):
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await ws.accept()

    pubsub = events.redis_client().pubsub()
    await pubsub.subscribe(events.CHANNEL)

    async def forward() -> None:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await ws.send_text(message["data"].decode())

    async def until_closed() -> None:
        with contextlib.suppress(WebSocketDisconnect):
            while True:
                await ws.receive_text()

    tasks = [asyncio.create_task(forward()), asyncio.create_task(until_closed())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await pubsub.unsubscribe(events.CHANNEL)
        await pubsub.aclose()
