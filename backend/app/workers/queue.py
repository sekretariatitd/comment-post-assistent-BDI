"""ARQ connection used by the API to enqueue background jobs."""

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from app.core.config import get_settings

_pool: ArqRedis | None = None


async def get_queue() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    return _pool


def poll_job_id(source_id: object) -> str:
    """One queued poll per source at a time (ARQ won't enqueue a duplicate job id)."""
    return f"poll_source:{source_id}"


async def enqueue_scoring(queue: ArqRedis, post_ids: list) -> None:
    """Queue relevance scoring (and then drafting) for newly stored posts."""
    for post_id in post_ids:
        await queue.enqueue_job("score_post", str(post_id), _job_id=f"score_post:{post_id}")
