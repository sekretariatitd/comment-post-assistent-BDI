"""Thin wrapper around the Anthropic SDK: Pydantic-validated structured output, one retry."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

import anthropic
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)

Effort = Literal["low", "medium", "high"]

# Models that accept server-side refusal fallbacks (`fallbacks: "default"`) on the Claude API.
# On a policy decline the API re-runs the request on a suitable model inside the same call.
_FALLBACK_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5", "claude-opus-5", "claude-fable-5-1"}
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(Exception):
    """Base error. Messages are safe to show to users (no secrets, no raw payloads)."""


class LLMNotConfiguredError(LLMError):
    pass


class LLMRefusalError(LLMError):
    pass


class LLMInvalidOutputError(LLMError):
    pass


@dataclass(frozen=True)
class LLMResult[T: BaseModel]:
    value: T
    model: str  # the model that actually produced the output (may differ after a fallback)


class LLMClient:
    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key) if api_key else None

    async def generate[T: BaseModel](
        self,
        *,
        system: str,
        user: str,
        output_type: type[T],
        effort: Effort = "medium",
        max_tokens: int = 8000,
        validate: Callable[[T], None] | None = None,
    ) -> LLMResult[T]:
        """Call the model with a JSON schema derived from `output_type`.

        Retries once when the output fails schema or `validate` checks (validate raises ValueError).
        """
        if self._client is None:
            raise LLMNotConfiguredError("ANTHROPIC_API_KEY is not set on the server.")

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_format": output_type,
            "output_config": {"effort": effort},
        }
        if self.model in _FALLBACK_MODELS:
            kwargs |= {"betas": [_FALLBACK_BETA], "fallbacks": "default"}

        problem = "unknown"
        for attempt in (1, 2):
            try:
                response = await self._client.beta.messages.parse(**kwargs)
            except anthropic.AuthenticationError:
                raise LLMError("The Anthropic API key was rejected.") from None
            except anthropic.RateLimitError:
                raise LLMError("Anthropic rate limit reached. Try again shortly.") from None
            except anthropic.APIStatusError as e:
                logger.warning("Anthropic API error %s (request %s)", e.status_code, e.request_id)
                raise LLMError(f"Anthropic API error ({e.status_code}).") from None
            except anthropic.APIConnectionError:
                raise LLMError("Couldn't reach the Anthropic API.") from None
            except ValueError as e:  # malformed JSON or schema validation failure
                problem = f"invalid JSON: {e}"
                logger.warning("LLM output invalid on attempt %d: %s", attempt, e)
                continue

            if response.stop_reason == "refusal":
                raise LLMRefusalError("The model declined to respond to this content.")
            if response.stop_reason == "max_tokens":
                problem = "output was cut off"
                continue
            parsed = response.parsed_output
            if parsed is None:
                problem = "no structured output returned"
                continue
            if validate is not None:
                try:
                    validate(parsed)
                except ValueError as e:
                    problem = str(e)
                    logger.warning("LLM output rejected on attempt %d: %s", attempt, e)
                    continue
            return LLMResult(value=parsed, model=response.model)

        raise LLMInvalidOutputError(f"The model returned unusable output twice ({problem}).")


@lru_cache
def get_llm_client() -> LLMClient:
    settings = get_settings()
    return LLMClient(api_key=settings.anthropic_api_key, model=settings.anthropic_model)
