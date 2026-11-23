"""Whether a claim's thread is paused, and what the app's record answers it with."""

from typing import Any

from langchain_core.runnables import RunnableConfig


def waiting(graph: Any, config: RunnableConfig) -> bool:
    """Whether the thread has an interrupt waiting for an answer."""
    return bool(graph.get_state(config).interrupts)


def answer(claim: dict[str, Any]) -> dict[str, str] | None:
    """What the app's record of the claim answers its pause with, if it does."""
    if claim["signed_off_by"] is None:
        return None
    return {"handler": claim["signed_off_by"]}
