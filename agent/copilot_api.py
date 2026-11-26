"""The Copilot's way to the UnderCover backend: one function for each operation.

The Copilot calls the app as the handler it works for, with the handler's sign-in in
place of the agent's key, so it can do only what that handler can. Every function
takes the sign-in; none holds the agent's key, and none reaches a round, a proposal
or the improver's view.
"""

from typing import Any, Literal

from agent import backend_http

CardKind = Literal["claims", "customers", "context", "agent work", "memory", "action"]
StepState = Literal["done", "refused", "failed"]
EvalSet = Literal["evaluation", "held_out"]


def _call(sign_in: str, method: str, path: str, **kwargs: Any) -> Any:
    """Call the backend as the handler; a 4xx is an ApiRefusal."""
    headers = {"Authorization": f"Bearer {sign_in}"}
    return backend_http.answer(backend_http.request(method, path, headers, **kwargs))


def who_is_signed_in(sign_in: str) -> dict[str, Any]:
    """Return the handler the sign-in is, and whether they can sign off."""
    return _call(sign_in, "GET", "/api/me")


def list_claims(sign_in: str) -> list[dict[str, Any]]:
    """List every claim in the queue, oldest submitted first."""
    return _call(sign_in, "GET", "/api/claims")


def get_claim(sign_in: str, claim_id: str) -> dict[str, Any]:
    """Return one claim in full, with its policy and the customer's claim history."""
    return _call(sign_in, "GET", f"/api/claims/{claim_id}")


def claim_steps(sign_in: str, claim_id: str) -> list[dict[str, Any]]:
    """List the steps the agent took on a claim, in order."""
    return _call(sign_in, "GET", f"/api/claims/{claim_id}/steps")


def find_customers(sign_in: str, name: str) -> list[dict[str, Any]]:
    """List the customers whose name holds this text."""
    return _call(sign_in, "GET", "/api/customers", params={"name": name})


def get_customer(sign_in: str, customer_id: str) -> dict[str, Any]:
    """Return a customer with their policies, earlier claims and queue claims."""
    return _call(sign_in, "GET", f"/api/customers/{customer_id}")


def get_policy(sign_in: str, policy_id: str) -> dict[str, Any]:
    """Return a policy with the limits of its plan."""
    return _call(sign_in, "GET", f"/api/policies/{policy_id}")


def latest_dispatch(sign_in: str) -> dict[str, Any] | None:
    """Return the most recently started run with its claims and summary, or None."""
    return _call(sign_in, "GET", "/api/runs/current")


def get_run(sign_in: str, run_id: int) -> dict[str, Any]:
    """Return one run with its claims, totals and summary."""
    return _call(sign_in, "GET", f"/api/runs/{run_id}")


def evaluations(sign_in: str) -> list[dict[str, Any]]:
    """List the evaluations with their measures and cost, newest first."""
    return _call(sign_in, "GET", "/api/copilot/evaluations")


def settings(sign_in: str) -> list[dict[str, Any]]:
    """List the platform's settings with who last changed each."""
    return _call(sign_in, "GET", "/api/settings")


def what_needs_a_handler(sign_in: str) -> dict[str, Any]:
    """Return the held payouts, the referred claims and the sent-back claims."""
    return _call(sign_in, "GET", "/api/queue/needs-a-handler")


def payments_over_the_limit(sign_in: str) -> dict[str, Any]:
    """Return the claims paid over the approval limit and their sign-offs."""
    return _call(sign_in, "GET", "/api/payments/over-limit")


def start_dispatch(sign_in: str, concurrency: int) -> dict[str, Any]:
    """Start a dispatch of the queue; the app refuses while other work is going."""
    return _call(sign_in, "POST", "/api/dispatches", json={"concurrency": concurrency})


def start_evaluation(
    sign_in: str, concurrency: int, eval_set: str, tiny: bool
) -> dict[str, Any]:
    """Start an evaluation on a labeled set; the app refuses while work is going."""
    body = {"concurrency": concurrency, "eval_set": eval_set, "tiny": tiny}
    return _call(sign_in, "POST", "/api/evaluations", json=body)


def send_back_claim(sign_in: str, claim_id: str, note: str) -> dict[str, Any]:
    """Send a claim waiting for sign-off back to the agent with a note."""
    return _call(
        sign_in, "POST", f"/api/claims/{claim_id}/send-back", json={"note": note}
    )


def sign_off_claim(sign_in: str, claim_id: str) -> dict[str, Any]:
    """Sign off a claim waiting for sign-off, which pays it."""
    return _call(sign_in, "POST", f"/api/claims/{claim_id}/sign-off")


def start_step(
    sign_in: str, conversation_id: str, tool: str, kind: CardKind, input_text: str
) -> int:
    """Record a step of the turn as working; return its id."""
    body = {"tool": tool, "kind": kind, "input": input_text}
    path = f"/api/copilot/conversations/{conversation_id}/steps"
    return _call(sign_in, "POST", path, json=body)["step_id"]


def finish_step(sign_in: str, step_id: int, outcome: dict[str, Any]) -> None:
    """Finish a step as done, refused or failed, with its result and files."""
    _call(sign_in, "POST", f"/api/copilot/steps/{step_id}/finish", json=outcome)


def turn_waiting(sign_in: str, conversation_id: str, card: dict[str, Any]) -> None:
    """Tell the app the turn is waiting for the handler to answer a card."""
    path = f"/api/copilot/conversations/{conversation_id}/waiting"
    _call(sign_in, "POST", path, json={"card": card})


def turn_done(sign_in: str, conversation_id: str, answer: dict[str, Any]) -> None:
    """Tell the app the turn is over, with the answer and what it took."""
    _call(
        sign_in,
        "POST",
        f"/api/copilot/conversations/{conversation_id}/done",
        json=answer,
    )


def turn_failed(sign_in: str, conversation_id: str, reason: str) -> None:
    """Tell the app the turn failed, with the reason."""
    path = f"/api/copilot/conversations/{conversation_id}/failed"
    _call(sign_in, "POST", path, json={"reason": reason})
