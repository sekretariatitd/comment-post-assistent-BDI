import uuid
from typing import Any

from httpx import AsyncClient

RSS = {
    "platform": "rss",
    "display_name": "Example News",
    "url_or_handle": "https://example.com/feed.xml",
}


async def _template_id(client: AsyncClient, headers: dict[str, str]) -> str:
    resp = await client.post(
        "/api/v1/templates",
        json={
            "name": "T",
            "system_prompt": "p",
            "tone": "friendly",
            "language": "English",
            "max_length": 280,
        },
        headers=headers,
    )
    return resp.json()["id"]


async def _create(client: AsyncClient, headers: dict[str, str], **overrides: Any):
    return await client.post("/api/v1/sources", json=RSS | overrides, headers=headers)


async def test_create_defaults(client: AsyncClient, admin_headers) -> None:
    resp = await _create(client, admin_headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["adapter"] == "rss"
    assert body["poll_interval_minutes"] == 15
    assert body["is_active"] is True
    assert body["prompt_template_id"] is None

    fb = await _create(client, admin_headers, platform="facebook", url_or_handle="acmenews")
    assert fb.json()["adapter"] == "meta_graph"


async def test_validation(client: AsyncClient, admin_headers) -> None:
    bad_url = await _create(client, admin_headers, url_or_handle="example.com/feed")
    assert bad_url.status_code == 422

    bad_template = await _create(client, admin_headers, prompt_template_id=str(uuid.uuid4()))
    assert bad_template.status_code == 422

    bad_adapter = await _create(client, admin_headers, adapter="scraper")
    assert bad_adapter.status_code == 422

    bad_interval = await _create(client, admin_headers, poll_interval_minutes=0)
    assert bad_interval.status_code == 422


async def test_attach_and_detach_template(client: AsyncClient, admin_headers) -> None:
    template_id = await _template_id(client, admin_headers)
    source = (await _create(client, admin_headers)).json()
    url = f"/api/v1/sources/{source['id']}"

    attached = await client.patch(
        url, json={"prompt_template_id": template_id}, headers=admin_headers
    )
    assert attached.json()["prompt_template_id"] == template_id

    detached = await client.patch(url, json={"prompt_template_id": None}, headers=admin_headers)
    assert detached.json()["prompt_template_id"] is None

    null_name = await client.patch(url, json={"display_name": None}, headers=admin_headers)
    assert null_name.status_code == 422


async def test_platform_change_resets_adapter(client: AsyncClient, admin_headers) -> None:
    source = (await _create(client, admin_headers)).json()
    resp = await client.patch(
        f"/api/v1/sources/{source['id']}",
        json={"platform": "manual", "url_or_handle": "manual entries"},
        headers=admin_headers,
    )
    assert resp.json()["adapter"] == "manual"


async def test_reviewer_read_only_and_delete(
    client: AsyncClient, admin_headers, reviewer_headers
) -> None:
    source = (await _create(client, admin_headers)).json()
    listed = await client.get("/api/v1/sources", headers=reviewer_headers)
    assert [s["id"] for s in listed.json()] == [source["id"]]
    assert (await _create(client, reviewer_headers)).status_code == 403
    denied = await client.delete(f"/api/v1/sources/{source['id']}", headers=reviewer_headers)
    assert denied.status_code == 403

    ok = await client.delete(f"/api/v1/sources/{source['id']}", headers=admin_headers)
    assert ok.status_code == 204
    assert (
        await client.get(f"/api/v1/sources/{source['id']}", headers=admin_headers)
    ).status_code == 404


async def test_stance_defaults_to_neutral_and_can_change(
    client: AsyncClient, admin_headers
) -> None:
    source = (await _create(client, admin_headers)).json()
    assert source["stance"] == "neutral"
    resp = await client.patch(
        f"/api/v1/sources/{source['id']}", json={"stance": "ally"}, headers=admin_headers
    )
    assert resp.json()["stance"] == "ally"
    bad = await client.patch(
        f"/api/v1/sources/{source['id']}", json={"stance": "friend"}, headers=admin_headers
    )
    assert bad.status_code == 422
