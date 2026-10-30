import json
from pathlib import Path

from httpx import AsyncClient

from app.adapters.sources.tiktok_payload import handle_from, parse_payload

# Shaped like the Response of a profile's api/post/item_list/ request (trimmed).
ITEM_LIST = {
    "cursor": "1793360000000",
    "hasMore": True,
    "statusCode": 0,
    "itemList": [
        {
            "id": "7702437774070222088",
            "desc": "Kërcënimet as na frikësojnë e as na zmbrapsin ❗",
            "createTime": 1793360000,
            "author": {"id": "1", "uniqueId": "bajram.rexhepi3", "nickname": "Bajram Rexhepi"},
            "video": {"id": "7702437774070222088", "cover": "https://p16.tiktokcdn.example/c.jpg"},
            "music": {"id": "77", "title": "original sound - Bajram Rexhepi"},
            "stats": {"diggCount": 56, "commentCount": 1},
        },
        {
            "id": "7702000000000000001",
            "desc": "",  # no caption: nothing to respond to
            "createTime": "1793300000",
            "author": {"uniqueId": "bajram.rexhepi3"},
            "video": {"cover": "https://p16.tiktokcdn.example/d.jpg"},
        },
        {
            "id": "7701000000000000002",
            "desc": "Takim me qytetarët e Tetovës.",
            "createTime": "1793200000",
            "video": {},
        },
    ],
}


def test_parses_item_list_response() -> None:
    posts = parse_payload(json.dumps(ITEM_LIST), default_handle="fallback")
    assert [p.platform_post_id for p in posts] == ["7702437774070222088", "7701000000000000002"]

    latest, older = posts
    assert latest.url == "https://www.tiktok.com/@bajram.rexhepi3/video/7702437774070222088"
    assert latest.text.startswith("Kërcënimet as na frikësojnë")
    assert latest.thumbnail_url == "https://p16.tiktokcdn.example/c.jpg"
    assert latest.published_at is not None

    # No author on the item: the source's handle is used; string timestamps are accepted.
    assert older.url == "https://www.tiktok.com/@fallback/video/7701000000000000002"
    assert older.published_at is not None and older.thumbnail_url is None


def test_parses_video_page_html() -> None:
    rehydration = {
        "__DEFAULT_SCOPE__": {
            "webapp.video-detail": {"itemInfo": {"itemStruct": ITEM_LIST["itemList"][0]}}
        }
    }
    html = (
        '<html><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
        f"{json.dumps(rehydration)}</script></html>"
    )
    assert [p.platform_post_id for p in parse_payload(html)] == ["7702437774070222088"]


def test_handle_from() -> None:
    assert handle_from("https://www.tiktok.com/@bajram.rexhepi3?lang=en") == "bajram.rexhepi3"
    assert handle_from("@some_user") == "some_user"
    assert handle_from("no handle here") is None


async def test_import_endpoint_uses_tiktok_parser(client: AsyncClient, admin_headers) -> None:
    src = await client.post(
        "/api/v1/sources",
        json={
            "platform": "tiktok",
            "display_name": "TikTok",
            "url_or_handle": "https://www.tiktok.com/@bajram.rexhepi3",
        },
        headers=admin_headers,
    )
    assert src.json()["adapter"] == "manual"
    url = f"/api/v1/posts/import/{src.json()['id']}"

    first = await client.post(url, json={"payload": json.dumps(ITEM_LIST)}, headers=admin_headers)
    assert {k: first.json()[k] for k in ("found", "new")} == {"found": 2, "new": 2}
    again = await client.post(url, json={"payload": json.dumps(ITEM_LIST)}, headers=admin_headers)
    assert {k: again.json()[k] for k in ("found", "new")} == {"found": 2, "new": 0}

    posts = (
        await client.get(f"/api/v1/posts?source_id={src.json()['id']}", headers=admin_headers)
    ).json()
    assert {p["url"] for p in posts["items"]} == {
        "https://www.tiktok.com/@bajram.rexhepi3/video/7702437774070222088",
        "https://www.tiktok.com/@bajram.rexhepi3/video/7701000000000000002",
    }


def test_real_item_list_sample() -> None:
    """Trimmed real Response from tiktok.com/@bajram.rexhepi3 (nested video/music/author ids
    are digit strings too and must not be mistaken for videos)."""
    raw = (Path(__file__).parent / "fixtures" / "tiktok_item_list.json").read_text(encoding="utf-8")
    posts = parse_payload(raw)
    assert [p.platform_post_id for p in posts] == ["7702437774070222088", "7701325077484178695"]
    assert posts[0].url == "https://www.tiktok.com/@bajram.rexhepi3/video/7702437774070222088"
    assert posts[0].text.startswith("Kërcënimet as na frikësojnë")
    assert all(p.thumbnail_url and p.published_at for p in posts)
