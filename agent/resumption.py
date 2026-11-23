"""Resuming a claim whose pause a handler has answered."""

from langgraph.checkpoint.base import BaseCheckpointSaver

from agent import agents, api, backend_http, paused


def refusal(
    claim_id: str, checkpointer: BaseCheckpointSaver | None = None
) -> str | None:
    """Why the claim can't be resumed, or None when it can.

    A claim resumes when its thread has an interrupt waiting and the app's record
    answers it.
    """
    try:
        claim = api.get_claim(claim_id)
    except backend_http.ApiRefusal as error:
        return error.detail
    if not agents.is_paused(claim, checkpointer):
        return f"{claim_id} is not waiting for an answer"
    if paused.answer(claim) is None:
        return f"{claim_id} is waiting for a handler to sign off"
    return None
