"""The improver: a LangChain agent that follows a recipe to improve the claim agent.

It reads results, proposes a change and waits for a handler (`HumanInTheLoopMiddleware`
pauses it on the two propose tools, which needs its checkpointer), has the change
evaluated, and proposes a new recipe. Code keeps or rolls back each version.
"""

from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    hook_config,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from agent import harness, improver_api
from agent.contexts import ImproverContext
from agent.improver_tools import IMPROVER_TOOLS

PROPOSALS = ("propose_change", "propose_recipe")
STOPPED = "stopped"

INSTRUCTIONS = """You improve the configuration of UnderCover's claim agent, an \
AI agent that decides travel insurance claims, and then your own recipe.

The claim agent works from its instructions, the policy wording and the claims \
manual, which it searches and reads by section as it needs, the claim, the policy \
and the customer's earlier claims, and its tools for working out a payout. It never \
sees the handlers' decisions or the scores. You may change only its instructions, \
its model and its reasoning effort, and only to the models allowed.

A change teaches the agent a rule that holds for any claim: it never names a claim \
or a claim's details. A handler reviews each proposal before it takes effect, and \
tells you why if they reject it, so that you can propose again. Code, not you, keeps \
or rolls back a version, by the rule you read in your results.

Your recipe is what you do in a round.

# Your recipe

{recipe}
"""

Middleware = AgentMiddleware[AgentState[Any], ImproverContext]


class RecordCost(Middleware):
    """Record each model call's tokens and cost with the round."""

    def after_model(
        self, state: AgentState[Any], runtime: Runtime[ImproverContext]
    ) -> dict[str, Any] | None:
        reply = state["messages"][-1]
        improver_api.record_call(
            runtime.context.round_id,
            reply.response_metadata["model_name"],
            reply.response_metadata["token_usage"],
        )
        return None


class EndWhenRoundIsStopped(Middleware):
    """Make no more model calls once a handler has stopped the round."""

    @hook_config(can_jump_to=["end"])
    def before_model(
        self, state: AgentState[Any], runtime: Runtime[ImproverContext]
    ) -> dict[str, Any] | None:
        if improver_api.get_round(runtime.context.round_id)["stage"] == STOPPED:
            return {"messages": [AIMessage("The round was stopped.")], "jump_to": "end"}
        return None


class RefuseModelsNotAllowed(Middleware):
    """Send a change that names a model or effort not allowed back to the improver.

    It runs before the handler's approval, so a bad proposal never reaches a handler.
    """

    @hook_config(can_jump_to=["model"])
    def after_model(
        self, state: AgentState[Any], runtime: Runtime[ImproverContext]
    ) -> dict[str, Any] | None:
        allowed = {
            m["model"]: m["reasoning_efforts"] for m in improver_api.models_allowed()
        }
        refusals = []
        for call in state["messages"][-1].tool_calls:  # pyright: ignore[reportAttributeAccessIssue]
            if call["name"] != "propose_change":
                continue
            model, effort = call["args"]["model"], call["args"]["reasoning_effort"]
            if effort not in allowed.get(model, []):
                refusals.append(
                    ToolMessage(
                        f"{model} at {effort} isn't allowed. Choose from: "
                        + "; ".join(
                            f"{m} ({', '.join(e)})" for m, e in allowed.items()
                        ),
                        tool_call_id=call["id"],
                        name=call["name"],
                        status="error",
                    )
                )
        return {"messages": refusals, "jump_to": "model"} if refusals else None


def build_improver(
    recipe: str, llm: BaseChatModel, checkpointer: BaseCheckpointSaver
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Build the improver from a recipe.

    The order matters. Hooks after the model run in reverse, so the cost is recorded
    first, a bad proposal is sent back second, and only then does the handler
    approval pause the improver.
    """
    approval = HumanInTheLoopMiddleware(
        interrupt_on={
            name: {"allowed_decisions": ["approve", "reject"]} for name in PROPOSALS
        }
    )
    middleware: list[Any] = [
        ModelCallLimitMiddleware(
            thread_limit=harness.MAX_IMPROVER_CALLS, exit_behavior="error"
        ),
        EndWhenRoundIsStopped(),
        approval,
        RefuseModelsNotAllowed(),
        RecordCost(),
    ]
    return create_agent(
        model=llm,
        tools=IMPROVER_TOOLS,
        system_prompt=INSTRUCTIONS.format(recipe=recipe),
        middleware=middleware,
        context_schema=ImproverContext,
        checkpointer=checkpointer,
    )
