"""The agent harness: the model and its settings.

Nothing here knows about claims. What an agent can do is in `tools.py`.
"""

import os
from dataclasses import dataclass
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
NO_EFFORT = "default"
MODEL_TIMEOUT_SECONDS = 120
IMPROVER_MODEL = "openai/gpt-6-luna"
IMPROVER_EFFORT = "medium"
IMPROVER_TIMEOUT_SECONDS = 300
MAX_IMPROVER_CALLS = 40


@dataclass(frozen=True)
class ModelSettings:
    """Which model runs and with what reasoning effort ("default" when unset)."""

    name: str
    reasoning_effort: str


def model_settings(configuration: dict[str, Any]) -> ModelSettings:
    """Return a version's model and effort, or MODEL_NAME with no effort set."""
    name = os.getenv("MODEL_NAME")
    if name:
        return ModelSettings(name, NO_EFFORT)
    return ModelSettings(configuration["model"], configuration["reasoning_effort"])


def model(settings: ModelSettings) -> ChatOpenAI:
    """Return the model, set up for OpenRouter, that these settings name."""
    return ChatOpenAI(
        model=settings.name,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=(
            None
            if settings.reasoning_effort == NO_EFFORT
            else settings.reasoning_effort
        ),
        timeout=MODEL_TIMEOUT_SECONDS,
    )


def improver_settings() -> ModelSettings:
    """Return the improver's model: GPT-6 Luna at medium effort, or MODEL_NAME."""
    name = os.getenv("MODEL_NAME")
    if name:
        return ModelSettings(name, NO_EFFORT)
    return ModelSettings(IMPROVER_MODEL, IMPROVER_EFFORT)


def improver_model(settings: ModelSettings) -> ChatOpenAI:
    """Return the improver's model, with parallel tool calls off.

    A reply then never holds two proposals.
    """
    return ChatOpenAI(
        model=settings.name,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=(
            None
            if settings.reasoning_effort == NO_EFFORT
            else settings.reasoning_effort
        ),
        timeout=IMPROVER_TIMEOUT_SECONDS,
        model_kwargs={"parallel_tool_calls": False},
    )
