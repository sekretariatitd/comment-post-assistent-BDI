from datetime import datetime

from app.adapters.sources.base import FetchedPost
from app.models import Source


class ManualAdapter:
    """Posts are added by a person (URL + text) via POST /posts; there is nothing to poll."""

    key = "manual"
    can_poll = False

    async def fetch_new_posts(self, source: Source, since: datetime | None) -> list[FetchedPost]:
        return []
