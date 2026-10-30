import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.llm.prompts import DEFAULT_RELEVANCE_RULES


class TemplateFields(BaseModel):
    """The fields that shape LLM output. Changing any of them bumps the template version."""

    system_prompt: str = Field(min_length=1, max_length=20000)
    tone: str = Field(min_length=1, max_length=100)
    language: str = Field(min_length=1, max_length=50)
    max_length: int = Field(ge=20, le=5000)
    relevance_rules: str = Field(min_length=1, max_length=20000)
    plain_e: bool = False  # always write e, c instead of ë, ç
    no_dashes: bool = False  # never use dashes as punctuation


class TemplateCreate(TemplateFields):
    name: str = Field(min_length=1, max_length=200)
    relevance_rules: str = Field(default=DEFAULT_RELEVANCE_RULES, min_length=1, max_length=20000)
    is_active: bool = True


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=20000)
    tone: str | None = Field(default=None, min_length=1, max_length=100)
    language: str | None = Field(default=None, min_length=1, max_length=50)
    max_length: int | None = Field(default=None, ge=20, le=5000)
    relevance_rules: str | None = Field(default=None, min_length=1, max_length=20000)
    plain_e: bool | None = None
    no_dashes: bool | None = None
    is_active: bool | None = None


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    system_prompt: str
    tone: str
    language: str
    max_length: int
    relevance_rules: str
    plain_e: bool
    no_dashes: bool
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TemplateDefaults(BaseModel):
    relevance_rules: str


class PreviewRequest(BaseModel):
    sample_text: str = Field(min_length=1, max_length=20000)
    # Optional unsaved edits from the editor; when given they replace the saved template fields.
    overrides: TemplateFields | None = None


class RelevancePreview(BaseModel):
    relevant: bool
    score: float
    reason: str
    would_draft: bool  # relevant and the score clears RELEVANCE_THRESHOLD


class PreviewResponse(BaseModel):
    relevance: RelevancePreview
    drafts: list[str]
    model_name: str
    template_version: int
    threshold: float
