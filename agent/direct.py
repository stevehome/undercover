"""The direct route: the model's tools called on the app and the context layer.

The app is called with the agent's API key, as the rest of the agent calls it. The
context layer is called over MCP without signing, at `UNDERCOVER_CONTEXT` or on the
laptop's port.
"""

from collections.abc import Callable
from typing import Any

from agent import api, endpoints
from agent.mcp_connection import McpConnection, ToolError
from agent.refusals import BY_CONTEXT_LAYER, Refusal
from agent.tool_route import CONTEXT

DEFAULT_CONTEXT_URL = "http://127.0.0.1:8006/mcp"
OPERATIONS: dict[str, Callable[..., Any]] = {
    "get_claim": api.get_claim,
    "calculate_payout": api.calculate_payout,
    "decide_claim": api.decide_claim,
    "pay_claim": api.pay_claim,
}


class DirectRoute:
    """Calls operations without the Gateway, under their own names."""

    def __init__(self, context: McpConnection | None = None) -> None:
        self._context = context

    def tool_name(self, target: str, operation: str) -> str:
        """Return the operation's own name."""
        return operation

    def call(self, target: str, operation: str, arguments: dict[str, Any]) -> Any:
        """Call an operation on the app, or a tool of the context layer."""
        if target != CONTEXT:
            return OPERATIONS[operation](**arguments)
        context = self._context or McpConnection(
            endpoints.context_url() or DEFAULT_CONTEXT_URL
        )
        try:
            return context.call(operation, arguments)
        except ToolError as error:
            raise Refusal(BY_CONTEXT_LAYER, str(error)) from error
