from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.publishers import AutomatedPublisher
from app.core.config import get_settings
from app.models import AuditLog, Draft, Platform, Post, PostingAccount, PromptTemplate, Source
from app.services import review_service
from app.services.errors import ConflictError


async def _draft(db: AsyncSession, text: str = "Draft one", max_length: int = 300) -> Draft:
    template = PromptTemplate(
        name="T",
        system_prompt="p",
        tone="t",
        language="Albanian",
        max_length=max_length,
        relevance_rules="r",
    )
    db.add(template)
    await db.flush()
    source = Source(
        platform=Platform.tiktok,
        display_name="TT",
        url_or_handle="https://www.tiktok.com/@x",
        adapter="manual",
        prompt_template_id=template.id,
    )
    db.add(source)
    await db.flush()
    post = Post(source_id=source.id, platform_post_id=text, url="https://t.example/1", text="c")
    db.add(post)
    await db.flush()
    draft = Draft(
        post_id=post.id,
        template_id=template.id,
        template_version=1,
        text=text,
        model_name="m",
    )
    db.add(draft)
    await db.flush()
    return draft


async def _account(client: AsyncClient, headers: dict[str, str], **body: Any) -> Any:
    payload = {"display_name": "Our TikTok", "is_active": True} | body
    return await client.put("/api/v1/posting-accounts/tiktok", json=payload, headers=headers)


async def test_approve_reject_and_invalid_transitions(
    client: AsyncClient, db_session: AsyncSession, reviewer_headers
) -> None:
    draft = await _draft(db_session)
    url = f"/api/v1/drafts/{draft.id}"

    approved = await client.post(f"{url}/approve", headers=reviewer_headers)
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "approved" and body["reviewer_id"] and body["reviewed_at"]

    again = await client.post(f"{url}/approve", headers=reviewer_headers)
    assert again.status_code == 409

    rejected = await client.post(f"{url}/reject", headers=reviewer_headers)
    assert rejected.json()["status"] == "rejected"
    edit = await client.patch(url, json={"text": "new"}, headers=reviewer_headers)
    assert edit.status_code == 409


async def test_editing_an_approved_draft_needs_reapproval(
    client: AsyncClient, db_session: AsyncSession, reviewer_headers
) -> None:
    draft = await _draft(db_session, max_length=20)
    url = f"/api/v1/drafts/{draft.id}"
    await client.post(f"{url}/approve", headers=reviewer_headers)

    edited = await client.patch(url, json={"text": "  Better text  "}, headers=reviewer_headers)
    body = edited.json()
    assert body["edited_text"] == "Better text"
    assert body["status"] == "pending" and body["reviewer_id"] is None

    too_long = await client.patch(url, json={"text": "x" * 21}, headers=reviewer_headers)
    assert too_long.status_code == 422


async def test_publishing_guardrails(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_headers,
    reviewer_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft = await _draft(db_session)
    url = f"/api/v1/drafts/{draft.id}"

    not_approved = await client.post(f"{url}/mark-published", headers=reviewer_headers)
    assert not_approved.status_code == 409

    await client.post(f"{url}/approve", headers=reviewer_headers)
    no_account = await client.post(f"{url}/mark-published", headers=reviewer_headers)
    assert no_account.status_code == 409
    assert "posting account" in no_account.json()["detail"]

    assert (await _account(client, admin_headers)).status_code == 200
    published = await client.post(f"{url}/mark-published", headers=reviewer_headers)
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published" and published.json()["published_at"]

    # A second approved draft on the same platform hits the hourly limit.
    monkeypatch.setattr(get_settings(), "max_comments_per_hour", 1)
    second = await _draft(db_session, text="Draft two")
    await client.post(f"/api/v1/drafts/{second.id}/approve", headers=reviewer_headers)
    limited = await client.post(
        f"/api/v1/drafts/{second.id}/mark-published", headers=reviewer_headers
    )
    assert limited.status_code == 429

    log = (await db_session.execute(select(AuditLog))).scalars().all()
    published_rows = [a for a in log if a.action == "draft.published"]
    assert len(published_rows) == 1
    assert published_rows[0].payload["account"] == "Our TikTok"
    assert published_rows[0].payload["text"] == "Draft one"


async def test_failed_publisher_marks_draft_failed(
    client: AsyncClient, db_session: AsyncSession, admin_headers, reviewer_headers
) -> None:
    draft = await _draft(db_session)
    await _account(client, admin_headers)
    await client.post(f"/api/v1/drafts/{draft.id}/approve", headers=reviewer_headers)

    with pytest.raises(ConflictError, match="not implemented"):
        await review_service.publish(db_session, draft.id, AutomatedPublisher())
    await db_session.refresh(draft)
    assert draft.status.value == "failed" and "not implemented" in (draft.error or "")


async def test_posting_account_credentials_are_never_returned(
    client: AsyncClient, db_session: AsyncSession, admin_headers, reviewer_headers
) -> None:
    denied = await _account(client, reviewer_headers)
    assert denied.status_code == 403

    resp = await _account(client, admin_headers, credentials="super-secret-token")
    body = resp.json()
    assert body["has_credentials"] is True
    assert "super-secret-token" not in resp.text and "credentials" not in body

    stored = (await db_session.execute(select(PostingAccount))).scalar_one()
    assert stored.encrypted_credentials and "super-secret" not in stored.encrypted_credentials

    listed = await client.get("/api/v1/posting-accounts", headers=reviewer_headers)
    assert "super-secret" not in listed.text
    audit = (await db_session.execute(select(AuditLog))).scalars().all()
    assert all("super-secret" not in str(a.payload) for a in audit)


async def test_review_filter_and_activity_log(
    client: AsyncClient, db_session: AsyncSession, reviewer_headers
) -> None:
    pending = await _draft(db_session, text="pending one")
    approved = await _draft(db_session, text="approved one")
    await client.post(f"/api/v1/drafts/{approved.id}/approve", headers=reviewer_headers)

    queue = (await client.get("/api/v1/posts?review=pending", headers=reviewer_headers)).json()
    assert [p["id"] for p in queue["items"]] == [str(pending.post_id)]
    ok = (await client.get("/api/v1/posts?review=approved", headers=reviewer_headers)).json()
    assert [p["id"] for p in ok["items"]] == [str(approved.post_id)]

    activity = (await client.get("/api/v1/activity?action=draft.", headers=reviewer_headers)).json()
    assert activity["total"] == 1
    row = activity["items"][0]
    assert row["action"] == "draft.approved"
    assert row["actor_email"] == "reviewer-test@example.com"
    assert row["entity_id"] == str(approved.id)


async def test_settings_endpoint(client: AsyncClient, reviewer_headers) -> None:
    body = (await client.get("/api/v1/settings", headers=reviewer_headers)).json()
    assert body["max_comments_per_hour"] == get_settings().max_comments_per_hour
    assert body["enable_automated_publishing"] is False
    assert "anthropic_api_key" not in body
