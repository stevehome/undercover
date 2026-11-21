import asyncio
import json

from context.server import TOOLS, build_server

HOST = "abc123.lambda-url.us-east-1.on.aws"


def run(coroutine):
    """Run a coroutine on a loop of its own, leaving the main thread's loop alone."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coroutine)
    finally:
        loop.close()


def test_there_are_seven_tools_all_read_only():
    tools = run(build_server().list_tools())

    assert sorted(t.name for t in tools) == sorted(f.__name__ for f in TOOLS)
    assert len(tools) == 7
    assert all(t.annotations and t.annotations.readOnlyHint for t in tools)


def test_each_tool_has_a_one_line_description_and_no_optional_input():
    for tool in run(build_server().list_tools()):
        assert tool.description
        assert "\n" not in tool.description.strip(), tool.name
        schema = tool.inputSchema
        assert set(schema.get("required", [])) == set(schema["properties"]), tool.name


def function_url_event(body):
    """The event a Lambda Function URL sends for a POST to /mcp."""
    return {
        "version": "2.0",
        "rawPath": "/mcp",
        "rawQueryString": "",
        "headers": {
            "host": HOST,
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
        },
        "body": json.dumps(body),
        "isBase64Encoded": False,
        "requestContext": {
            "http": {
                "method": "POST",
                "path": "/mcp",
                "protocol": "HTTP/1.1",
                "sourceIp": "203.0.113.1",
            },
            "stage": "$default",
        },
    }


def rpc(method, params=None, ident=1):
    return {"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}}
