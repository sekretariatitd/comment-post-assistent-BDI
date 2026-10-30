from typing import Any

import pytest
from httpx import AsyncClient
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import prompts
from app.llm.client import LLMClient, LLMInvalidOutputError, LLMResult, get_llm_client
from app.main import app
from app.models import (
    AuditLog,
    Draft,
    DraftStatus,
    Platform,
    Post,
    PostStatus,
    PromptTemplate,
    Source,
)
from app.services import drafting_service


class ScriptedLLM(LLMClient):
    def __init__(self, score: float = 0.9, fail_drafts: bool = False) -> None:
        self.model = "fake-model"
        self.score = score
        self.fail_drafts = fail_drafts
        self.systems: list[str] = []
        self.batch = 0

    async def generate(self, *, system: str, user: str, output_type: type[BaseModel], **_: Any):
        self.systems.append(system)
        if output_type is prompts.RelevanceOutput:
            return LLMResult(
                prompts.RelevanceOutput(relevant=self.score >= 0.5, score=self.score, reason="r"),
                self.model,
            )
        if self.fail_drafts:
            raise LLMInvalidOutputError("bad output")
        self.batch += 1
        texts = [f"Draft {self.batch}.{n}" for n in (1, 2, 3)]
        return LLMResult(prompts.DraftsOutput(drafts=texts), self.model)


async def _setup(db: AsyncSession, *, with_template: bool = True) -> tuple[Post, PromptTemplate]:
    template = PromptTemplate(
        name="Supportive",
        system_prompt="SUPPORTIVE-PROMPT",
        tone="warm",
        language="Albanian",
        max_length=300,
        relevance_rules="rules",
    )
    db.add(template)
    await db.flush()
    source = Source(
        platform=Platform.tiktok,
        display_name="TT",
        url_or_handle="https://www.tiktok.com/@x",
        adapter="manual",
        prompt_template_id=template.id if with_template else None,
    )
    db.add(source)
    await db.flush()
    post = Post(
        source_id=source.id, platform_post_id="1", url="https://t.example/1", text="caption"
    )
    db.add(post)
    await db.flush()
    return post, template


async def test_relevant_post_is_scored_then_drafted(db_session: AsyncSession) -> None:
    post, template = await _setup(db_session)
    llm = ScriptedLLM(score=0.85)

    assert await drafting_service.score_post(db_session, post.id, llm, threshold=0.6) is True
    assert post.relevance_score == 0.85 and post.status == PostStatus.new

    drafts = await drafting_service.draft_comments(db_session, post.id, llm)
    assert [d.text for d in drafts] == ["Draft 1.1", "Draft 1.2", "Draft 1.3"]
    assert all(
        d.status == DraftStatus.pending
        and d.template_version == template.version
        and d.model_name == "fake-model"
        for d in drafts
    )
    assert post.status == PostStatus.drafted

    # Scoring is idempotent: an already-scored post isn't scored again.
    assert await drafting_service.score_post(db_session, post.id, llm, threshold=0.6) is False


async def test_low_score_is_skipped_with_reason(db_session: AsyncSession) -> None:
    post, _ = await _setup(db_session)
    assert not await drafting_service.score_post(db_session, post.id, ScriptedLLM(0.3), 0.6)
    assert post.status == PostStatus.skipped and post.relevance_reason == "r"
    audit = (await db_session.execute(select(AuditLog))).scalar_one()
    assert audit.action == "post.scored" and audit.payload["skipped"] is True


async def test_source_without_template_is_skipped(db_session: AsyncSession) -> None:
    post, _ = await _setup(db_session, with_template=False)
    assert not await drafting_service.score_post(db_session, post.id, ScriptedLLM(), 0.6)
    assert post.status == PostStatus.skipped
    assert "no active template" in (post.relevance_reason or "")


async def test_redraft_supersedes_pending_drafts(db_session: AsyncSession) -> None:
    post, _ = await _setup(db_session)
    llm = ScriptedLLM()
    first = await drafting_service.draft_comments(db_session, post.id, llm)
    second = await drafting_service.draft_comments(db_session, post.id, llm)

    assert all(d.status == DraftStatus.rejected for d in first)
    assert all(d.status == DraftStatus.pending for d in second)
    actions = [a.action for a in (await db_session.execute(select(AuditLog))).scalars()]
    assert actions.count("draft.created") == 6 and actions.count("draft.superseded") == 3


async def test_failed_drafting_changes_nothing(db_session: AsyncSession) -> None:
    post, _ = await _setup(db_session)
    with pytest.raises(LLMInvalidOutputError):
        await drafting_service.draft_comments(db_session, post.id, ScriptedLLM(fail_drafts=True))
    assert (await db_session.execute(select(Draft))).scalars().all() == []
    assert post.status == PostStatus.new


@pytest.fixture
def llm() -> ScriptedLLM:
    fake = ScriptedLLM()
    app.dependency_overrides[get_llm_client] = lambda: fake
    return fake


async def test_regenerate_with_other_template_and_listing(
    client: AsyncClient, db_session: AsyncSession, admin_headers, llm: ScriptedLLM
) -> None:
    post, _ = await _setup(db_session)
    critical = PromptTemplate(
        name="Critical",
        system_prompt="CRITICAL-PROMPT",
        tone="calm",
        language="Albanian",
        max_length=350,
        relevance_rules="rules",
    )
    db_session.add(critical)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/posts/{post.id}/regenerate",
        json={"template_id": str(critical.id)},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "drafted"
    assert [d["text"] for d in body["drafts"]] == ["Draft 1.1", "Draft 1.2", "Draft 1.3"]
    assert {d["template_id"] for d in body["drafts"]} == {str(critical.id)}
    assert "CRITICAL-PROMPT" in llm.systems[-1]

    listed = (await client.get("/api/v1/posts", headers=admin_headers)).json()
    assert len(listed["items"][0]["drafts"]) == 3
    pending = (await client.get("/api/v1/drafts?status=pending", headers=admin_headers)).json()
    assert len(pending) == 3


async def test_new_posts_are_queued_for_scoring(client: AsyncClient, admin_headers, queue) -> None:
    src = await client.post(
        "/api/v1/sources",
        json={"platform": "facebook", "display_name": "P", "url_or_handle": "https://fb.com/p"},
        headers=admin_headers,
    )
    resp = await client.post(
        "/api/v1/posts",
        json={"source_id": src.json()["id"], "url": "https://fb.com/p/posts/1", "text": "t"},
        headers=admin_headers,
    )
    post_id = resp.json()["id"]
    assert queue.jobs == [("score_post", (post_id,), f"score_post:{post_id}")]


async def test_unscored_posts_are_found(db_session: AsyncSession) -> None:
    post, _ = await _setup(db_session)
    assert await drafting_service.unscored_post_ids(db_session) == [post.id]
    await drafting_service.score_post(db_session, post.id, ScriptedLLM(0.2), 0.6)
    assert await drafting_service.unscored_post_ids(db_session) == []
