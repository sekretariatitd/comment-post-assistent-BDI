from datetime import datetime

from app.adapters.sources.base import FetchedPost
from app.models import Source


class MetaGraphAdapter:
    """Facebook Page posts via the Meta Graph API. Not implemented yet.

    Reading posts from Pages we don't manage requires Meta's "Page Public Content Access"
    feature, which needs a Meta app that has passed App Review (and business verification).
    Until that's in place, add Facebook posts by hand (POST /posts) under the Facebook source.
    """

    key = "meta_graph"
    can_poll = False

    async def fetch_new_posts(self, source: Source, since: datetime | None) -> list[FetchedPost]:
        raise NotImplementedError(
            "Meta Graph fetching needs Page Public Content Access (App Review)"
        )
