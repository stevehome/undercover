"""What a route to the model's tools looks like.

The tools are the same on both routes. A target is one of the services they
reach: the app or the context layer.
"""

from typing import Any, Protocol, runtime_checkable

APP = "undercover-app"
CONTEXT = "undercover-context"


@runtime_checkable
class ToolRoute(Protocol):
    """A way to call the operations of the app and the context layer."""

    def tool_name(self, target: str, operation: str) -> str:
        """Return the name this route gives an operation, for the claim's steps."""
        ...

    def call(self, target: str, operation: str, arguments: dict[str, Any]) -> Any:
        """Call an operation and return its answer, or raise `Refusal`."""
        ...
