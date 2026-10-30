from app.adapters.sources.base import FetchedPost, FetchError, SourceAdapter
from app.adapters.sources.manual import ManualAdapter
from app.adapters.sources.meta_graph import MetaGraphAdapter
from app.adapters.sources.rss import RssAdapter

# TODO: no TikTok fetcher yet. Decide between TikTok's official API and a licensed data
# provider; until then TikTok sources use the manual adapter.
ADAPTERS: dict[str, SourceAdapter] = {
    a.key: a for a in (RssAdapter(), ManualAdapter(), MetaGraphAdapter())
}


def get_adapter(key: str) -> SourceAdapter:
    return ADAPTERS[key]


def pollable_keys() -> list[str]:
    return [key for key, adapter in ADAPTERS.items() if adapter.can_poll]


__all__ = ["ADAPTERS", "FetchError", "FetchedPost", "SourceAdapter", "get_adapter", "pollable_keys"]
