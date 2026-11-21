"""The claim agent's graph: its nodes joined by edges, and the checkpointer.

START -> screen -> agent <-> tools, or refer_flagged -> END for a flagged claim.
agent -> settle; settle -> agent (no decision yet) or remember (decided);
remember -> END (decline or referral), pay (at or under the limit) or approval,
which ends the graph: a sign-off pays.
"""

from functools import partial
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from agent import claim_nodes, step_recording
from agent.claim_state import ClaimState
from agent.contexts import ClaimContext
from agent.memory import CustomerMemory
from agent.tools import claim_tools


def after_screen(state: ClaimState) -> Literal["agent", "refer_flagged"]:
    """Refer a claim the check flagged; otherwise the claim agent works it."""
    return "refer_flagged" if state["flagged"] else "agent"


def after_agent(state: ClaimState) -> Literal["tools", "settle"]:
    """Run the tools the model asked for, or move on to the decision."""
    return "tools" if state["messages"][-1].tool_calls else "settle"


def after_settle(state: ClaimState) -> Literal["agent", "remember"]:
    """Send the claim back to the agent, or on to be remembered once it is decided."""
    return "remember" if state["decision"] else "agent"


def after_remember(state: ClaimState) -> str:
    """End a decline or a referral, or send an approval to a sign-off or a payment."""
    if state["decision"] != "approve":
        return END
    return "approval" if state["needs_sign_off"] else "pay"


def build_graph(
    checkpointer: BaseCheckpointSaver,
    model: BaseChatModel,
    instructions: str,
    screening_model: BaseChatModel,
    memory: CustomerMemory | None,
) -> CompiledStateGraph[ClaimState, ClaimContext, ClaimState, ClaimState]:
    """Build the claim graph on a checkpointer.

    With a memory the agent also has a tool to search it, and the decided claim is
    saved to it; with none, the graph's `remember` node does nothing.
    """
    tools = claim_tools(memory is not None)
    builder = StateGraph(ClaimState, context_schema=ClaimContext)
    builder.add_node("screen", partial(claim_nodes.screen, model=screening_model))
    builder.add_node("refer_flagged", claim_nodes.refer_flagged)
    builder.add_node(
        "agent",
        partial(
            claim_nodes.agent,
            model=model.bind_tools(tools),
            instructions=instructions,
        ),
    )
    builder.add_node(
        "tools",
        ToolNode(
            tools,
            handle_tool_errors=False,
            wrap_tool_call=step_recording.record_tool_call,
        ),
    )
    builder.add_node("settle", claim_nodes.settle)
    builder.add_node("remember", partial(claim_nodes.remember, memory=memory))
    builder.add_node("approval", claim_nodes.approval)
    builder.add_node("pay", claim_nodes.pay)

    builder.add_edge(START, "screen")
    builder.add_conditional_edges("screen", after_screen, ["agent", "refer_flagged"])
    builder.add_edge("refer_flagged", END)
    builder.add_conditional_edges("agent", after_agent, ["tools", "settle"])
    builder.add_edge("tools", "agent")
    builder.add_conditional_edges("settle", after_settle, ["agent", "remember"])
    builder.add_conditional_edges("remember", after_remember, ["approval", "pay", END])
    builder.add_edge("approval", END)
    builder.add_edge("pay", END)
    return builder.compile(checkpointer=checkpointer)
