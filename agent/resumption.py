"""Resuming a claim whose pause a handler has answered: a sign-off or a send back."""

from langgraph.checkpoint.base import BaseCheckpointSaver

from agent import agents, api, backend_http, heartbeat, paused


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


def work(claim_id: str) -> str:
    """Carry a claim on from its pause, telling the app every minute it is working."""
    with heartbeat.beating(lambda: api.hear_resume(claim_id)):
        return agents.decide_claim(claim_id)
