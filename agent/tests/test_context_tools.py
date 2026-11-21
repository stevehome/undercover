import asyncio

from agent.tools import CLAIM_TOOLS
from context.server import build_server


def listed_by_the_context_layer():
    loop = asyncio.new_event_loop()
    try:
        tools = loop.run_until_complete(build_server().list_tools())
    finally:
        loop.close()
    return {tool.name: tool for tool in tools}


def test_the_agents_context_tools_are_the_context_layers_tools_with_the_same_inputs():
    layer = listed_by_the_context_layer()
    agents = {tool.name: tool for tool in CLAIM_TOOLS if tool.name in layer}

    assert set(agents) == set(layer)
    for name, tool in agents.items():
        assert set(tool.args) == set(layer[name].inputSchema["properties"]), name
