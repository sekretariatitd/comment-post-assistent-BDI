from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.models import Source


@dataclass(frozen=True)
class FetchedPost:
    platform_post_id: str  # stable id within the source; (source_id, platform_post_id) dedupes
    url: str
    text: str
    thumbnail_url: str | None = None
    published_at: datetime | None = None


class FetchError(Exception):
    """The source couldn't be fetched (network, HTTP error, unparseable feed)."""


class SourceAdapter(Protocol):
    key: str
    # False for adapters whose posts are added by hand (or that aren't implemented yet);
    # the poller skips them.
    can_poll: bool

    async def fetch_new_posts(
        self, source: Source, since: datetime | None
    ) -> list[FetchedPost]: ...
