"""The Copilot's route to the context layer: only the context layer.

The claim agent's routes reach the app too, as the agent. The Copilot reaches the app
only through `copilot_api`, as the handler, so this route refuses the app's target: a
tool can't call the app's operations as the agent, even by mistake.
"""

from typing import Any

from agent import routes
from agent.refusals import BY_APP, Refusal
from agent.tool_route import CONTEXT, ToolRoute


class ContextOnlyRoute:
    """Wraps a route so that only the context layer's tools go through it."""

    def __init__(self, route: ToolRoute) -> None:
        self.route = route

    def tool_name(self, target: str, operation: str) -> str:
        """Return the wrapped route's name for an operation."""
        return self.route.tool_name(target, operation)

    def call(self, target: str, operation: str, arguments: dict[str, Any]) -> Any:
        """Call a tool of the context layer; refuse any other target."""
        if target != CONTEXT:
            raise Refusal(BY_APP, f"The Copilot has no route to {target}")
        return self.route.call(target, operation, arguments)


def context_route() -> ContextOnlyRoute:
    """Return the route to the context layer: the Gateway's, else a direct one."""
    return ContextOnlyRoute(routes.choose())
