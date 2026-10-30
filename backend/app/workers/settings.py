import logging
from typing import ClassVar

from arq import cron, func
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.workers.jobs import (
    draft_comments,
    enqueue_due_sources,
    poll_source,
    publish_draft,
    score_post,
)

# ARQ logs its own job lines; give our "app.*" loggers a handler without duplicating those.
_app_logger = logging.getLogger("app")
_app_logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
_app_logger.addHandler(_handler)
_app_logger.propagate = False


class WorkerSettings:
    # keep_result=0 so a finished poll doesn't block re-queuing the same job id.
    functions: ClassVar[list] = [
        func(poll_source, keep_result=0, timeout=120),
        func(score_post, keep_result=0, timeout=300),
        func(draft_comments, keep_result=0, timeout=300),
        func(publish_draft, keep_result=0, timeout=120),
    ]
    # LLM calls are slow I/O; run a few in parallel.
    max_jobs = 5
    cron_jobs: ClassVar[list] = [
        cron(enqueue_due_sources, second=0, run_at_startup=True, keep_result=0),
    ]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
