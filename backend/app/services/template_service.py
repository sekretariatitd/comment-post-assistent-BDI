import asyncio
import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import prompts
from app.llm.client import LLMClient
from app.models import Draft, PromptTemplate, Source, User
from app.schemas.template import (
    PreviewRequest,
    PreviewResponse,
    RelevancePreview,
    TemplateCreate,
    TemplateFields,
    TemplateUpdate,
)
from app.services import audit_service
from app.services.errors import ConflictError, InvalidInputError, NotFoundError

# Changing any of these changes LLM output, so it bumps the template version.
VERSIONED_FIELDS = frozenset(TemplateFields.model_fields)


async def list_templates(db: AsyncSession) -> Sequence[PromptTemplate]:
    result = await db.execute(select(PromptTemplate).order_by(PromptTemplate.name))
    return result.scalars().all()


async def get_template(db: AsyncSession, template_id: uuid.UUID) -> PromptTemplate:
    template = await db.get(PromptTemplate, template_id)
    if template is None:
        raise NotFoundError("Template not found")
    return template


async def create_template(db: AsyncSession, actor: User, body: TemplateCreate) -> PromptTemplate:
    template = PromptTemplate(**body.model_dump(), version=1)
    db.add(template)
    await db.flush()
    audit_service.record(
        db,
        actor=actor,
        action="template.created",
        entity_type="template",
        entity_id=template.id,
        payload={"name": template.name, "version": template.version},
    )
    await db.commit()
    return template


async def update_template(
    db: AsyncSession, actor: User, template_id: uuid.UUID, body: TemplateUpdate
) -> PromptTemplate:
    template = await get_template(db, template_id)
    requested = body.model_dump(exclude_unset=True)
    if nulls := [k for k, v in requested.items() if v is None]:
        raise InvalidInputError(f"Fields cannot be null: {', '.join(sorted(nulls))}")

    changed = {k: v for k, v in requested.items() if getattr(template, k) != v}
    if not changed:
        return template

    for key, value in changed.items():
        setattr(template, key, value)
    if changed.keys() & VERSIONED_FIELDS:
        template.version += 1

    audit_service.record(
        db,
        actor=actor,
        action="template.updated",
        entity_type="template",
        entity_id=template.id,
        payload={"changed": sorted(changed), "version": template.version},
    )
    await db.commit()
    return template


async def delete_template(db: AsyncSession, actor: User, template_id: uuid.UUID) -> None:
    template = await get_template(db, template_id)
    sources = await db.scalar(
        select(func.count()).select_from(Source).where(Source.prompt_template_id == template_id)
    )
    drafts = await db.scalar(
        select(func.count()).select_from(Draft).where(Draft.template_id == template_id)
    )
    if sources or drafts:
        raise ConflictError(
            f"Template is used by {sources} source(s) and {drafts} draft(s). "
            "Deactivate it instead, or move those sources to another template first."
        )
    await db.delete(template)
    audit_service.record(
        db,
        actor=actor,
        action="template.deleted",
        entity_type="template",
        entity_id=template_id,
        payload={"name": template.name},
    )
    await db.commit()


def spec_for(
    template: PromptTemplate, overrides: TemplateFields | None = None
) -> prompts.TemplateSpec:
    fields = overrides or TemplateFields.model_validate(template, from_attributes=True)
    return prompts.TemplateSpec(**fields.model_dump())


async def score(
    llm: LLMClient,
    spec: prompts.TemplateSpec,
    post_text: str,
    author: str | None = None,
    stance: str | None = None,
):
    system, user = prompts.build_relevance_prompt(spec, post_text, author=author, stance=stance)
    return await llm.generate(
        system=system,
        user=user,
        output_type=prompts.RelevanceOutput,
        effort="low",
        validate=prompts.check_relevance,
    )


async def draft(
    llm: LLMClient,
    spec: prompts.TemplateSpec,
    post_text: str,
    author: str | None = None,
    stance: str | None = None,
):
    system, user = prompts.build_drafting_prompt(spec, post_text, author=author, stance=stance)
    result = await llm.generate(
        system=system,
        user=user,
        output_type=prompts.DraftsOutput,
        effort="medium",
        validate=lambda out: prompts.check_drafts(out, spec.max_length),
    )
    # The model doesn't follow spelling/punctuation switches reliably, so enforce them here.
    result.value.drafts = [prompts.apply_style(d, spec) for d in result.value.drafts]
    return result


async def preview(
    template: PromptTemplate, body: PreviewRequest, llm: LLMClient, threshold: float
) -> PreviewResponse:
    """Run relevance + drafting against sample text. Nothing is saved."""
    spec = spec_for(template, body.overrides)
    relevance, drafts = await asyncio.gather(
        score(llm, spec, body.sample_text), draft(llm, spec, body.sample_text)
    )
    r = relevance.value
    return PreviewResponse(
        relevance=RelevancePreview(
            relevant=r.relevant,
            score=r.score,
            reason=r.reason,
            would_draft=r.relevant and r.score >= threshold,
        ),
        drafts=[d.strip() for d in drafts.value.drafts if d.strip()][:3],
        model_name=drafts.model,
        template_version=template.version,
        threshold=threshold,
    )
