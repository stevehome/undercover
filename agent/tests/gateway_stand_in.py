"""A stand-in for the Gateway: an MCP server over streamable HTTP, in process.

It names its tools as the Gateway does, records what it is asked, and refuses a
tool the way the Policy does: a protocol error that starts "Tool Execution Denied".
"""

import json
from collections.abc import Callable
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

DENIED = (
    "Tool Execution Denied: Tool call not allowed due to policy enforcement "
    "[Policy evaluation denied due to undercover_payment_limit]"
)

Tool = Callable[[dict[str, Any]], tuple[str, bool]]


class StandInGateway:
    """Tools by name, each taking its arguments and giving (text, is_error)."""

    def __init__(self) -> None:
        self.tools: dict[str, Tool] = {}
        self.denied: set[str] = set()
        self.calls: list[dict[str, Any]] = []
        self.app = Starlette(
            routes=[Route("/mcp", self._handle, methods=["POST", "GET"])]
        )

    async def _handle(self, request: Request) -> Response:
        if request.method == "GET":
            return Response(status_code=405)
        message = await request.json()
        method, ident = message.get("method"), message.get("id")
        if ident is None:
            return Response(status_code=202)
        if method == "initialize":
            return self._result(
                ident,
                {
                    "protocolVersion": message["params"]["protocolVersion"],
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "stand-in-gateway", "version": "1"},
                },
            )
        if method == "tools/list":
            tools = [
                {"name": name, "inputSchema": {"type": "object"}} for name in self.tools
            ]
            return self._result(ident, {"tools": tools})
        return self._call(ident, message["params"], request)

    def _call(self, ident: int, params: dict[str, Any], request: Request) -> Response:
        name = params["name"]
        self.calls.append(
            {
                "name": name,
                "arguments": params["arguments"],
                "authorization": request.headers.get("authorization", ""),
            }
        )
        if name in self.denied:
            error = {"code": -32600, "message": DENIED}
            return JSONResponse({"jsonrpc": "2.0", "id": ident, "error": error})
        text, is_error = self.tools[name](params["arguments"])
        content = [{"type": "text", "text": text}]
        return self._result(ident, {"content": content, "isError": is_error})

    @staticmethod
    def _result(ident: int, result: dict[str, Any]) -> Response:
        return JSONResponse({"jsonrpc": "2.0", "id": ident, "result": result})

    @property
    def names(self) -> list[str]:
        """The tools called so far, in order."""
        return [call["name"] for call in self.calls]


def answer(response: Any) -> tuple[str, bool]:
    """Turn a backend response into what the Gateway gives for a tool."""
    if response.is_error:
        text = f"Client error: API request failed with status: {response.status_code}"
        return f"{text} - {json.dumps(response.json())}", True
    return response.text, False
