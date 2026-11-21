"""Which route a claim's tools take: the Gateway's when it is set, else direct."""

from agent import endpoints
from agent.direct import DirectRoute
from agent.gateway import GatewayRoute
from agent.tool_route import ToolRoute


def choose() -> ToolRoute:
    """Return the Gateway route when `UNDERCOVER_GATEWAY_URL` is set, else direct."""
    url = endpoints.gateway_url()
    return GatewayRoute(url) if url else DirectRoute()
