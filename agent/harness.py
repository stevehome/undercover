"""The agent harness: the model and its settings.

Nothing here knows about claims. What an agent can do is in `tools.py`.
"""

import os
from dataclasses import dataclass
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from agent import deadline

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
PRIVATE_PROVIDERS = {"data_collection": "deny", "zdr": True}
NO_EFFORT = "default"
MODEL_TIMEOUT_SECONDS = 120
MODEL_DEADLINE_SECONDS = 120
MODEL_RETRIES = 1
IMPROVER_TIMEOUT_SECONDS = 300
MAX_IMPROVER_CALLS = 40
SCREENING_MODEL = "openai/gpt-6-luna"
SCREENING_EFFORT = "none"


@dataclass(frozen=True)
class ModelSettings:
    """Which model runs and with what reasoning effort ("default" when unset)."""

    name: str
    reasoning_effort: str


def _named_model() -> ModelSettings | None:
    """Return MODEL_NAME, with no effort set, when it is set."""
    name = os.getenv("MODEL_NAME")
    return ModelSettings(name, NO_EFFORT) if name else None


def model_settings(configuration: dict[str, Any]) -> ModelSettings:
    """Return a version's model and effort, or MODEL_NAME with no effort set."""
    return _named_model() or ModelSettings(
        configuration["model"], configuration["reasoning_effort"]
    )


def _chat_model(settings: ModelSettings, timeout: int, **options: Any) -> ChatOpenAI:
    """Return a model set up for OpenRouter, on providers that keep no data."""
    return ChatOpenAI(
        model=settings.name,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=(
            None
            if settings.reasoning_effort == NO_EFFORT
            else settings.reasoning_effort
        ),
        timeout=timeout,
        extra_body={"provider": PRIVATE_PROVIDERS},
        **options,
    )


def model(settings: ModelSettings) -> ChatOpenAI:
    """Return the model that these settings name."""
    return _chat_model(
        settings,
        MODEL_TIMEOUT_SECONDS,
        max_retries=MODEL_RETRIES,
        http_client=deadline.client(MODEL_DEADLINE_SECONDS),
    )


def improver_model(settings: ModelSettings) -> ChatOpenAI:
    """Return the improver's model, with parallel tool calls off.

    A reply then never holds two proposals.
    """
    return _chat_model(
        settings,
        IMPROVER_TIMEOUT_SECONDS,
        model_kwargs={"parallel_tool_calls": False},
    )


def screening_model() -> ChatOpenAI:
    """Return the claim check's model: GPT-6 Luna with no reasoning, or MODEL_NAME."""
    return model(_named_model() or ModelSettings(SCREENING_MODEL, SCREENING_EFFORT))
