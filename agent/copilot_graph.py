"""The Copilot's graph: its nodes joined by edges, and the checkpointer.

START -> recall -> agent <-> tools; agent -> confirm -> tools when the reply asks for
a payment, a sign-off or redress, which pauses for the handler; agent -> remember when
it has no more tools to call; remember -> END.
"""

from functools import partial
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from agent import copilot_nodes, copilot_recording
from agent.copilot_confirm import PAYMENTS, confirm
from agent.copilot_context import CopilotContext
from agent.copilot_state import CopilotState
from agent.copilot_tools import COPILOT_TOOLS


def after_agent(state: CopilotState) -> Literal["confirm", "tools", "remember"]:
    """Ask the handler about a payment first, else run the tools, else finish."""
    calls = state["messages"][-1].tool_calls
    if any(call["name"] in PAYMENTS for call in calls):
        return "confirm"
    return "tools" if calls else "remember"


def build_copilot_graph(
    checkpointer: BaseCheckpointSaver, model: BaseChatModel
) -> CompiledStateGraph[CopilotState, CopilotContext, CopilotState, CopilotState]:
    """Build the Copilot's graph on a checkpointer."""
    builder = StateGraph(CopilotState, context_schema=CopilotContext)
    builder.add_node("recall", copilot_nodes.recall)
    builder.add_node(
        "agent", partial(copilot_nodes.agent, model=model.bind_tools(COPILOT_TOOLS))
    )
    builder.add_node(
        "tools",
        ToolNode(
            COPILOT_TOOLS,
            handle_tool_errors=False,
            wrap_tool_call=copilot_recording.record_tool_call,
        ),
    )
    builder.add_node("confirm", confirm)
    builder.add_node("remember", copilot_nodes.remember)

    builder.add_edge(START, "recall")
    builder.add_edge("recall", "agent")
    builder.add_conditional_edges(
        "agent", after_agent, ["confirm", "tools", "remember"]
    )
    builder.add_edge("confirm", "tools")
    builder.add_edge("tools", "agent")
    builder.add_edge("remember", END)
    return builder.compile(checkpointer=checkpointer)
