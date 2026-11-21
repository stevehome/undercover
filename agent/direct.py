"""The direct route: the model's tools called on the app and the context layer.

The app is called with the agent's API key, as the rest of the agent calls it.
"""

from collections.abc import Callable
from typing import Any

from agent import api

OPERATIONS: dict[str, Callable[..., Any]] = {
    "get_claim": api.get_claim,
    "list_sections": api.list_sections,
    "get_section": api.get_section,
    "calculate_payout": api.calculate_payout,
    "decide_claim": api.decide_claim,
    "pay_claim": api.pay_claim,
}


class DirectRoute:
    """Calls operations without the Gateway, under their own names."""

    def tool_name(self, target: str, operation: str) -> str:
        """Return the operation's own name."""
        return operation

    def call(self, target: str, operation: str, arguments: dict[str, Any]) -> Any:
        """Call an operation on the app."""
        return OPERATIONS[operation](**arguments)
