"""Live review-queue events.

The API and the worker publish to one Redis channel; the WebSocket route (`/ws/queue`)
forwards each message to connected browsers. Publishing never fails the caller.
"""

import json
import logging
from typing import Any

from redis.asyncio import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

CHANNEL = "queue-events"

_redis: Redis | None = None


def redis_client() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url)
    return _redis


async def publish(event: str, **data: Any) -> None:
    """Publish e.g. publish("draft.updated", draft_id=..., post_id=...)."""
    try:
        await redis_client().publish(CHANNEL, json.dumps({"type": event, **data}, default=str))
    except Exception:
        logger.warning("Couldn't publish %s event", event, exc_info=True)
