"""Reading the answer of an AgentCore app we asked to take some work."""

from typing import Any

from backend.errors import Conflict, ServiceUnavailable


def taken(answer: dict[str, Any], who: str) -> dict[str, Any]:
    """Return the answer when the app took the work.

    A refusal is a Conflict with the app's own reason; anything else that isn't an
    acceptance is ServiceUnavailable.
    """
    if "refused" in answer:
        raise Conflict(answer["refused"])
    if not answer.get("accepted"):
        raise ServiceUnavailable(f"{who} didn't take it: {answer}")
    return answer
