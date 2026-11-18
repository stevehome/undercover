"""The agent's API: an OpenAPI document of the operations the claim agent is given."""

from typing import Any

from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute

AGENT_OPERATIONS = {
    "get_claim",
    "list_sections",
    "get_section",
    "calculate_payout",
    "decide_claim",
    "pay_claim",
}
TITLE = "UnderCover agent API"
VERSION = "1.0.0"


def agent_openapi(routes: list[BaseRoute]) -> dict[str, Any]:
    """Build the document from the app's own routes, so it can't drift from the app.

    It has no servers and no key: the gateway that serves it supplies both.
    """
    chosen = [
        route
        for route in routes
        if isinstance(route, APIRoute) and route.operation_id in AGENT_OPERATIONS
    ]
    return get_openapi(title=TITLE, version=VERSION, routes=chosen)
