"""The Gateway route: the model's tools as the Gateway's MCP tools, signed.

The Gateway names each tool `<target>___<operation>` and turns the app's and the
context layer's operations into tools, with the Policy in front of them.
"""

import random
import re
import time
from decimal import Decimal
from typing import Any

from mcp.shared.exceptions import McpError
from pydantic import BaseModel

from agent.mcp_connection import McpConnection, ToolError
from agent.refusals import BY_APP, BY_CONTEXT_LAYER, BY_GATEWAY, Refusal
from agent.sigv4 import SigV4Auth
from agent.tool_route import CONTEXT

SERVICE = "bedrock-agentcore"
DENIED = "Tool Execution Denied"
BUSY = re.compile(
    r"^(McpException - .*statusCode=429"
    r"|ValidationException - MCP server .* returned HTTP 429"
    r"|Client error: API request failed with status: 429)\b",
    re.DOTALL,
)
BUSY_TRIES = 6
LONGEST_WAIT_SECONDS = 8


def _wire(value: Any) -> Any:
    """Turn arguments into what a JSON request holds.

    The Gateway's schema says an amount is a number, so an amount goes as one here
    and nowhere else: money is `Decimal` everywhere else in the agent.
    """
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, BaseModel):
        return _wire(value.model_dump())
    if isinstance(value, dict):
        return {key: _wire(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_wire(item) for item in value]
    return value


class GatewayRoute:
    """Calls operations as tools of the Gateway at one address."""

    def __init__(self, url: str, connection: McpConnection | None = None) -> None:
        self.connection = connection or McpConnection(url, auth=SigV4Auth(SERVICE))

    def tool_name(self, target: str, operation: str) -> str:
        """Return the Gateway's name for an operation."""
        return f"{target}___{operation}"

    def call(self, target: str, operation: str, arguments: dict[str, Any]) -> Any:
        """Call a tool through the Gateway, again after a wait if Lambda was busy.

        A 429 in a refusal means the call was never run, as when Lambda has no free
        slot for it, so it is sent again, up to BUSY_TRIES times in all. Any other
        refusal is the model's to read.
        """
        for tries in range(1, BUSY_TRIES):
            try:
                return self._call_once(target, operation, arguments)
            except Refusal as refusal:
                if not BUSY.search(refusal.detail):
                    raise
            time.sleep(min(2**tries, LONGEST_WAIT_SECONDS) * random.uniform(0.5, 1.5))  # noqa: S311 - jitter
        return self._call_once(target, operation, arguments)

    def _call_once(self, target: str, operation: str, arguments: dict[str, Any]) -> Any:
        """Call a tool through the Gateway.

        A tool the app or the context layer refuses, and a call the Gateway's
        Policy refuses, both raise `Refusal`, each with its own source.
        """
        try:
            return self.connection.call(
                self.tool_name(target, operation), _wire(arguments)
            )
        except ToolError as error:
            source = BY_CONTEXT_LAYER if target == CONTEXT else BY_APP
            raise Refusal(source, str(error)) from error
        except McpError as error:
            if DENIED not in str(error):
                raise
            raise Refusal(BY_GATEWAY, str(error)) from error
