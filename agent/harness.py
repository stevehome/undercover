"""The agent harness: the model and its settings.

Nothing here knows about claims. What an agent can do is in `tools.py`.
"""

import os
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
DEFAULT_EFFORT = "low"
NO_EFFORT = "none"
MODEL_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class ModelSettings:
    """Which model runs and with what reasoning effort ("none" when unset)."""

    name: str
    reasoning_effort: str


def model_settings() -> ModelSettings:
    """Return the model named in MODEL_NAME with no effort set, else GPT-6 Luna, low."""
    name = os.getenv("MODEL_NAME")
    if name:
        return ModelSettings(name, NO_EFFORT)
    return ModelSettings(DEFAULT_MODEL, DEFAULT_EFFORT)


def model() -> ChatOpenAI:
    """Return the model that `model_settings` names."""
    settings = model_settings()
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
