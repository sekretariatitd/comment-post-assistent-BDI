from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import AsyncClient
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import prompts
from app.llm.client import LLMClient, LLMNotConfiguredError, LLMResult, get_llm_client
from app.main import app
from app.models import AuditLog

TEMPLATE = {
    "name": "Default",
    "system_prompt": "You are the social team of Acme News.",
    "tone": "friendly",
    "language": "English",
    "max_length": 280,
}


class FakeLLM(LLMClient):
    """Returns canned output and records the prompts it was given."""

    def __init__(self, score: float = 0.9, configured: bool = True) -> None:
        self.model = "fake-model"
        self.score = score
        self.configured = configured
        self.calls: list[dict[str, Any]] = []

    async def generate(self, *, system: str, user: str, output_type: type[BaseModel], **_: Any):
        if not self.configured:
            raise LLMNotConfiguredError("ANTHROPIC_API_KEY is not set on the server.")
        self.calls.append({"system": system, "user": user, "type": output_type})
        if output_type is prompts.RelevanceOutput:
            value = prompts.RelevanceOutput(
                relevant=self.score >= 0.5, score=self.score, reason="ok"
            )
        else:
            value = prompts.DraftsOutput(drafts=["First take.", "Second take.", " ", "Third."])
        return LLMResult(value=value, model=self.model)


@pytest.fixture
async def fake_llm() -> AsyncIterator[FakeLLM]:
    fake = FakeLLM()
    app.dependency_overrides[get_llm_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_llm_client, None)


async def _create(client: AsyncClient, headers: dict[str, str], **overrides: Any) -> dict:
    resp = await client.post("/api/v1/templates", json=TEMPLATE | overrides, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_uses_default_relevance_rules(client: AsyncClient, admin_headers) -> None:
    body = await _create(client, admin_headers)
    assert body["version"] == 1
    assert body["relevance_rules"] == prompts.DEFAULT_RELEVANCE_RULES
    assert "deaths" in body["relevance_rules"]


async def test_reviewer_can_read_but_not_write(
    client: AsyncClient, admin_headers, reviewer_headers
) -> None:
    created = await _create(client, admin_headers)
    resp = await client.get("/api/v1/templates", headers=reviewer_headers)
    assert [t["id"] for t in resp.json()] == [created["id"]]

    denied = await client.post("/api/v1/templates", json=TEMPLATE, headers=reviewer_headers)
    assert denied.status_code == 403
    patch = await client.patch(
        f"/api/v1/templates/{created['id']}", json={"tone": "x"}, headers=reviewer_headers
    )
    assert patch.status_code == 403


async def test_version_bumps_only_for_prompt_fields(client: AsyncClient, admin_headers) -> None:
    t = await _create(client, admin_headers)
    url = f"/api/v1/templates/{t['id']}"

    renamed = await client.patch(url, json={"name": "Renamed"}, headers=admin_headers)
    assert renamed.json()["version"] == 1

    retoned = await client.patch(url, json={"tone": "formal"}, headers=admin_headers)
    assert retoned.json()["version"] == 2

    same = await client.patch(url, json={"tone": "formal"}, headers=admin_headers)
    assert same.json()["version"] == 2

    null = await client.patch(url, json={"tone": None}, headers=admin_headers)
    assert null.status_code == 422


async def test_delete_blocked_while_used_by_source(client: AsyncClient, admin_headers) -> None:
    t = await _create(client, admin_headers)
    src = await client.post(
        "/api/v1/sources",
        json={
            "platform": "rss",
            "display_name": "Feed",
            "url_or_handle": "https://example.com/feed.xml",
            "prompt_template_id": t["id"],
        },
        headers=admin_headers,
    )
    assert src.status_code == 201

    blocked = await client.delete(f"/api/v1/templates/{t['id']}", headers=admin_headers)
    assert blocked.status_code == 409

    await client.delete(f"/api/v1/sources/{src.json()['id']}", headers=admin_headers)
    ok = await client.delete(f"/api/v1/templates/{t['id']}", headers=admin_headers)
    assert ok.status_code == 204
    gone = await client.get(f"/api/v1/templates/{t['id']}", headers=admin_headers)
    assert gone.status_code == 404


async def test_changes_are_audited(
    client: AsyncClient, db_session: AsyncSession, admin_headers
) -> None:
    t = await _create(client, admin_headers)
    await client.patch(
        f"/api/v1/templates/{t['id']}", json={"max_length": 200}, headers=admin_headers
    )
    # All rows share one test transaction (same now()), so look them up by action, not by time.
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    by_action = {r.action: r for r in rows}
    assert by_action["template.created"].entity_id is not None
    assert by_action["template.updated"].payload == {"changed": ["max_length"], "version": 2}
    assert by_action["template.updated"].actor_id is not None


async def test_preview_returns_relevance_and_drafts(
    client: AsyncClient, admin_headers, reviewer_headers, fake_llm: FakeLLM
) -> None:
    t = await _create(client, admin_headers)
    resp = await client.post(
        f"/api/v1/templates/{t['id']}/preview",
        json={"sample_text": "City opens new library."},
        headers=reviewer_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["drafts"] == ["First take.", "Second take.", "Third."]
    assert body["relevance"]["would_draft"] is True
    assert body["model_name"] == "fake-model"
    assert body["template_version"] == 1

    drafting = next(c for c in fake_llm.calls if c["type"] is prompts.DraftsOutput)
    assert "Acme News" in drafting["system"]
    assert "City opens new library." in drafting["user"]


async def test_preview_uses_unsaved_overrides(
    client: AsyncClient, admin_headers, fake_llm: FakeLLM
) -> None:
    t = await _create(client, admin_headers)
    overrides = TEMPLATE | {"tone": "sarcastic-test-tone", "relevance_rules": "only sports"}
    overrides.pop("name")
    await client.post(
        f"/api/v1/templates/{t['id']}/preview",
        json={"sample_text": "x", "overrides": overrides},
        headers=admin_headers,
    )
    systems = " ".join(c["system"] for c in fake_llm.calls)
    assert "sarcastic-test-tone" in systems
    assert "only sports" in systems


async def test_preview_below_threshold_would_not_draft(
    client: AsyncClient, admin_headers, fake_llm: FakeLLM
) -> None:
    fake_llm.score = 0.2
    t = await _create(client, admin_headers)
    resp = await client.post(
        f"/api/v1/templates/{t['id']}/preview", json={"sample_text": "x"}, headers=admin_headers
    )
    assert resp.json()["relevance"]["would_draft"] is False


async def test_preview_without_api_key_returns_503(
    client: AsyncClient, admin_headers, fake_llm: FakeLLM
) -> None:
    fake_llm.configured = False
    t = await _create(client, admin_headers)
    resp = await client.post(
        f"/api/v1/templates/{t['id']}/preview", json={"sample_text": "x"}, headers=admin_headers
    )
    assert resp.status_code == 503
    assert "ANTHROPIC_API_KEY" in resp.json()["detail"]
