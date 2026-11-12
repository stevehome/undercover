"""The improver's four tools, with the names its recipe uses.

A tool gets its state from `ToolRuntime[ImproverContext]`. The two propose tools run
only once a handler has approved: the service records the proposal and the
decision before it resumes the improver, so these only report the outcome.
"""

import json
from contextvars import Context
from typing import Any

from langchain.tools import ToolRuntime, tool

from agent import api, dispatcher, harness, improver_api
from agent.backend_http import ApiRefusal
from agent.contexts import ImproverContext

EVALUATIONS = ("evaluation", "held_out", "held_out")
FIRST = "first evaluations"
LATER = "evaluations"


def run_round_evaluation(
    round_id: int,
    parent_run_id: int,
    eval_set: str,
    used: api.ModelUsed,
    check_spending: bool,
) -> None:
    """Start a whole-set evaluation for a round and work it, in a fresh context.

    The dispatcher's graph has no checkpointer of its own, so inside the improver's
    it would save into the improver's thread; a fresh `Context` keeps the claim
    graphs' threads their own, as the harness does for each claim.
    """
    run = improver_api.create_round_evaluation(
        round_id, parent_run_id, eval_set, used, check_spending
    )
    concurrency = int(
        improver_api.get_round(round_id)["settings"]["improver_agents_at_once"]
    )
    Context().run(dispatcher.run_dispatch, run["run_id"], concurrency)


def used_by(version: int) -> api.ModelUsed:
    """The model, effort and version an evaluation of a version works to."""
    configuration = improver_api.get_configuration(version)
    settings = harness.model_settings(configuration)
    return api.ModelUsed(
        model=settings.name,
        reasoning_effort=settings.reasoning_effort,
        configuration_version=version,
    )


def _describe(verdict: dict[str, Any]) -> str:
    kept = "Kept" if verdict["verdict"] == "kept" else "Rolled back"
    scores = {"held_out_before": verdict["before"], "held_out_after": verdict["after"]}
    return f"{kept} version {verdict['version']}: {verdict['reason']}.\n" + json.dumps(
        scores, indent=2, default=str
    )


def _refused(round_id: int, refusal: ApiRefusal) -> str:
    """Report a refused evaluation; the version, never evaluated, is rolled back."""
    try:
        verdict = improver_api.record_verdict(round_id)
    except ApiRefusal:
        return f"Stopped: {refusal.detail}"
    return f"Refused: {refusal.detail}.\n{_describe(verdict)}"


@tool
def read_results(runtime: ToolRuntime[ImproverContext]) -> str:
    """Read the current version of the claim agent's configuration and its scores on
    both sets; on the evaluation set its mistakes and the right decisions it explained
    least well, with the handlers' reasons; the earlier rounds; the objectives, the
    noise and the tolerance; what is left of the round's spending limit; and the
    models allowed."""
    view = improver_api.get_view(runtime.context.round_id)
    return json.dumps(view, indent=2, default=str)


@tool(parse_docstring=True)
def propose_change(
    instructions: str,
    model: str,
    reasoning_effort: str,
    reason: str,
    runtime: ToolRuntime[ImproverContext],
) -> str:
    """Propose a new version of the claim agent's configuration. A handler reviews it.

    Args:
        instructions: The claim agent's complete instructions
        model: One of the models allowed
        reasoning_effort: A reasoning effort allowed for that model
        reason: Why this change should improve the scores
    """
    version = improver_api.get_round(runtime.context.round_id)["configuration_version"]
    return f"A handler approved it and it is saved as version {version}."


@tool
def run_evaluation(runtime: ToolRuntime[ImproverContext]) -> str:
    """Run the newest version once on the evaluation set and twice on the held-out
    set, then keep it or roll it back by the rule."""
    context = runtime.context
    round_row = improver_api.get_round(context.round_id)
    version = round_row["configuration_version"]
    if version is None or round_row["verdict"] is not None:
        return "There's no new version to evaluate. Propose a change first."
    used = used_by(version)
    try:
        for number, eval_set in enumerate(EVALUATIONS, start=1):
            improver_api.record_stage(context.round_id, LATER, number)
            run_round_evaluation(context.round_id, context.run_id, eval_set, used, True)
        verdict = improver_api.record_verdict(context.round_id)
    except ApiRefusal as refusal:
        return _refused(context.round_id, refusal)
    return _describe(verdict)


@tool(parse_docstring=True)
def propose_recipe(
    recipe: str, reason: str, runtime: ToolRuntime[ImproverContext]
) -> str:
    """Propose a new version of your recipe for improving the claim agent. A handler
    reviews it.

    Args:
        recipe: The complete new recipe
        reason: What this round showed, and why the new recipe should lead to better
            changes
    """
    proposals = improver_api.get_round(runtime.context.round_id)["proposals"]
    version = [p["version"] for p in proposals if p["kind"] == "recipe"][-1]
    return f"A handler approved it and it is saved as recipe version {version}."


IMPROVER_TOOLS = [read_results, propose_change, run_evaluation, propose_recipe]
