"""The agent's own key check, for a host of its own.

On Runtime, AWS checks that the caller may invoke the runtime before a request
reaches the agent, so it asks for no key. Off Runtime the app sends the agent's key
as `Authorization: Bearer <key>`.
"""

import hmac

from agent import backend_http, credentials

BEARER = "Bearer "


def refusal(authorization: str | None) -> str | None:
    """Why the request is refused, or None when it may go on."""
    if credentials.on_runtime():
        return None
    presented = (authorization or "").removeprefix(BEARER)
    if not hmac.compare_digest(presented.encode(), backend_http.require_key().encode()):
        return "A request to the agent needs the agent's key"
    return None
