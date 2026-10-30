import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.core.config import get_settings
from app.db.session import get_db
from app.llm.client import LLMClient, get_llm_client
from app.llm.prompts import DEFAULT_RELEVANCE_RULES
from app.models import PromptTemplate, User
from app.schemas.template import (
    PreviewRequest,
    PreviewResponse,
    TemplateCreate,
    TemplateDefaults,
    TemplateOut,
    TemplateUpdate,
)
from app.services import template_service

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateOut])
async def list_templates(
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
) -> list[PromptTemplate]:
    return list(await template_service.list_templates(db))


@router.get("/defaults", response_model=TemplateDefaults)
async def template_defaults(_: User = Depends(get_current_user)) -> TemplateDefaults:
    return TemplateDefaults(relevance_rules=DEFAULT_RELEVANCE_RULES)


@router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: TemplateCreate, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)
) -> PromptTemplate:
    return await template_service.create_template(db, user, body)


@router.get("/{template_id}", response_model=TemplateOut)
async def get_template(
    template_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)
) -> PromptTemplate:
    return await template_service.get_template(db, template_id)


@router.patch("/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: uuid.UUID,
    body: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
) -> PromptTemplate:
    return await template_service.update_template(db, user, template_id, body)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(require_admin)
) -> None:
    await template_service.delete_template(db, user, template_id)


@router.post("/{template_id}/preview", response_model=PreviewResponse)
async def preview_template(
    template_id: uuid.UUID,
    body: PreviewRequest,
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
    _: User = Depends(get_current_user),
) -> PreviewResponse:
    template = await template_service.get_template(db, template_id)
    return await template_service.preview(
        template, body, llm, threshold=get_settings().relevance_threshold
    )
