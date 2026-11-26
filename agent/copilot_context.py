"""What a Copilot turn knows, handed to its tools and nodes.

The handler's sign-in lives here and nowhere the graph saves: LangGraph saves the
state and the config with each checkpoint, and never the context.
"""

from dataclasses import dataclass, field

from agent.copilot_memory import HandlerMemory
from agent.tool_route import ToolRoute


@dataclass
class CopilotContext:
    """The handler a turn works for, their sign-in, the conversation, the route to
    the context layer and the handler's memory if there is one."""

    handler_id: str
    handler_name: str
    can_approve_over_limit: bool
    conversation_id: str
    sign_in: str = field(repr=False)
    route: ToolRoute
    memory: HandlerMemory | None
