"""One MCP endpoint, called from synchronous code.

The agent is synchronous and LangGraph runs a lone task on the caller's thread, so
each call gets an event loop of its own and closes it. It never takes the thread's
loop away: `asyncio.run` on the main thread would leave it with none, and Mangum,
which the Lambda tests use, asks for the main thread's loop.
"""

import asyncio
import json
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import McpError

TIMEOUT_SECONDS = 60


class ToolError(Exception):
    """The tool ran and answered with an error; the message is what it said."""


def _leaf(errors: BaseExceptionGroup[McpError]) -> BaseException:
    """Return the server's refusal, which the client's task groups wrap in groups."""
    error: BaseException = errors
    while isinstance(error, BaseExceptionGroup):
        error = error.exceptions[0]
    return error


class McpConnection:
    """A stateless MCP server over streamable HTTP, with optional request signing."""

    def __init__(
        self,
        url: str,
        auth: httpx.Auth | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.url = url
        self.auth = auth
        self.transport = transport

    async def _call(self, tool: str, arguments: dict[str, Any]) -> Any:
        try:
            async with (
                httpx.AsyncClient(
                    auth=self.auth, transport=self.transport, timeout=TIMEOUT_SECONDS
                ) as http,
                streamable_http_client(self.url, http_client=http) as streams,
            ):
                read, write, _ = streams
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.call_tool(tool, arguments)
        except* McpError as errors:
            raise _leaf(errors) from None

    def call(self, tool: str, arguments: dict[str, Any]) -> Any:
        """Call a tool and return its answer: parsed JSON when it is JSON, else text.

        A tool that answers with an error raises `ToolError`. A server that refuses
        the call at the protocol level raises `McpError`, as the Gateway's Policy does.
        """
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self._call(tool, arguments))
        finally:
            loop.close()
        text = "".join(b.text for b in result.content if b.type == "text")
        if result.isError:
            raise ToolError(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
