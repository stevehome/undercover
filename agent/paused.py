"""Whether a claim's thread is paused, and what the app's record answers it with."""

from typing import Any

from langchain_core.runnables import RunnableConfig

from agent import review_message


def waiting(graph: Any, config: RunnableConfig) -> bool:
    """Whether the thread has an interrupt waiting for an answer."""
    return bool(graph.get_state(config).interrupts)


def answer(claim: dict[str, Any]) -> dict[str, str] | None:
    """What the app's record of the claim answers its pause with, if it does.

    A sign-off, or a send back: the decision the thread paused on is gone from the
    record and the last decision sent back has its note.
    """
    if claim["signed_off_by"] is not None:
        return {"handler": claim["signed_off_by"]}
    if claim["decision"] is None and claim["sent_back_decisions"]:
        last = claim["sent_back_decisions"][-1]
        return {
            "message": review_message.build(last["sent_back_by"], last["note"]),
            "handler": last["sent_back_by"],
        }
    return None
