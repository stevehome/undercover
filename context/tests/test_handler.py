import json

from context.server import handler
from context.tests.test_server import HOST, function_url_event, rpc

NO_CONTEXT = None


def call(body):
    response = handler(function_url_event(body), NO_CONTEXT)
    assert response["statusCode"] == 200
    return json.loads(response["body"])["result"]


def test_the_handler_lists_the_tools_and_then_calls_one_in_one_process():
    listed = call(rpc("tools/list"))
    assert len(listed["tools"]) == 7

    called = call(
        rpc("tools/call", {"name": "lookup_term", "arguments": {"term": "carrier"}}, 2)
    )

    answer = json.loads(called["content"][0]["text"])
    assert answer["answer"]["term"] == "Carrier"
    assert not called.get("isError")


def test_a_function_urls_host_is_not_refused():
    assert HOST.endswith(".on.aws")
    assert call(rpc("tools/list"))["tools"]


def test_a_section_that_does_not_exist_comes_back_as_a_tool_error():
    arguments = {"document": "claims_manual", "number": 99}

    called = call(rpc("tools/call", {"name": "read_section", "arguments": arguments}))

    assert called["isError"] is True
    assert "no section 99" in called["content"][0]["text"]
