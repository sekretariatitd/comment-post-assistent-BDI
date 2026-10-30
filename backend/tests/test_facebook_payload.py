import json

import pytest
from httpx import AsyncClient

from app.adapters.sources.facebook_payload import PayloadError, parse_payload

PAGE_URL = "https://www.facebook.com/examplepage"

# Shaped like the timeline GraphQL response copied from the browser (trimmed): a link share
# with no caption, wrapped in data.node.timeline_list_feed_units.edges[].node.
LINK_SHARE = {
    "__typename": "Story",
    "id": "UzpfSTE6MTA=",
    "post_id": "1001",
    "creation_time": 1792760775,
    "attachments": [
        {
            "styles": {
                "attachment": {
                    "media": {"large_share_image": {"uri": "https://scontent.example/img.jpg"}},
                    "title_with_entities": {"text": "Article title"},
                }
            }
        }
    ],
    "comet_sections": {
        "content": {
            "story": {
                "message": None,
                "wwwURL": f"{PAGE_URL}/posts/pfbid1001",
                "attachments": [
                    {
                        "comet_footer_renderer": {
                            "attachment": {
                                "description": {"text": "Article summary…"},
                                "target": {"external_url": "https://news.example/article"},
                            }
                        }
                    }
                ],
            }
        },
        "context_layout": {
            # Nested helper objects repeat parts of the story; they must not become posts.
            "story": {"post_id": "1001", "id": "UzpfSTE6MTA="},
            "metadata": [{"story": {"creation_time": 1792760775, "url": "x"}}],
        },
        "feedback": {"story": {"privacy_scope": {"description": "Publike"}}},
    },
    "permalink_url": f"{PAGE_URL}/posts/pfbid1001",
}
TEXT_POST = {
    "__typename": "Story",
    "post_id": "1002",
    "creation_time": 1792800000,
    "comet_sections": {
        "content": {"story": {"message": {"text": "Sot inauguruam shkollën e re."}}}
    },
    "permalink_url": f"{PAGE_URL}/posts/pfbid1002",
}
PHOTO_ONLY = {"__typename": "Story", "post_id": "1003", "creation_time": 1792700000}

FIRST_CHUNK = {
    "data": {
        "node": {
            "__typename": "User",
            "timeline_list_feed_units": {"edges": [{"node": LINK_SHARE, "cursor": "abc"}]},
        }
    },
    "extensions": {"is_final": False},
}
STREAMED_CHUNK = {"label": "ProfileCometTimelineFeed$stream$edges", "data": {"node": TEXT_POST}}


def _streamed() -> str:
    lines = [FIRST_CHUNK, STREAMED_CHUNK, {"data": {"node": PHOTO_ONLY}}]
    return "for (;;);" + "\n".join(json.dumps(x) for x in lines)


def test_parses_streamed_graphql_response() -> None:
    posts = parse_payload(_streamed())
    assert [p.platform_post_id for p in posts] == ["1002", "1001"]  # newest first, no photo-only

    text_post, link_share = posts
    assert text_post.text == "Sot inauguruam shkollën e re."
    assert text_post.url == f"{PAGE_URL}/posts/pfbid1002"

    assert link_share.text == (
        "Article title\n\nArticle summary…\n\nLink: https://news.example/article"
    )
    assert link_share.thumbnail_url == "https://scontent.example/img.jpg"
    assert link_share.published_at is not None
    assert link_share.published_at.year == 2026


def test_parses_single_json_document() -> None:
    assert [p.platform_post_id for p in parse_payload(json.dumps(FIRST_CHUNK))] == ["1001"]


def test_parses_page_html() -> None:
    html = (
        "<html><body><script>var x = 1;</script>"
        f'<script type="application/json" data-sjs>{json.dumps(FIRST_CHUNK)}</script>'
        f'<script type="application/json">{json.dumps(STREAMED_CHUNK)}</script></body></html>'
    )
    assert {p.platform_post_id for p in parse_payload(html)} == {"1001", "1002"}


def test_rejects_non_json() -> None:
    with pytest.raises(PayloadError):
        parse_payload("this is not json")


async def test_import_endpoint_dedupes(client: AsyncClient, admin_headers) -> None:
    src = await client.post(
        "/api/v1/sources",
        json={"platform": "facebook", "display_name": "Page", "url_or_handle": PAGE_URL},
        headers=admin_headers,
    )
    url = f"/api/v1/posts/import/{src.json()['id']}"

    first = await client.post(url, json={"payload": _streamed()}, headers=admin_headers)
    assert first.status_code == 200, first.text
    assert {k: first.json()[k] for k in ("found", "new")} == {"found": 2, "new": 2}

    again = await client.post(url, json={"payload": _streamed()}, headers=admin_headers)
    assert {k: again.json()[k] for k in ("found", "new")} == {"found": 2, "new": 0}

    empty = await client.post(
        url, json={"payload": json.dumps({"data": {}})}, headers=admin_headers
    )
    assert empty.status_code == 422
