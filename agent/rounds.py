"""A round, worked in stretches: the first evaluations, then the improver.

A stretch is the work between two pauses for a handler. It holds the one-run rule
while it runs and lets go when it ends. The backend keeps the round's records, so a
restart or a wait loses nothing: the improver's own progress is saved in Postgres.
"""

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command

from agent import checkpoint, harness, improver, improver_api, tracing
from agent.backend_http import ApiRefusal
from agent.contexts import ImproverContext
from agent.improver_tools import EVALUATIONS, FIRST, run_round_evaluation, used_by

logger = logging.getLogger(__name__)

STOPPED = "stopped"
FINISHED = "finished"
WORKING = "improver working"
START = {
    "messages": [
        {"role": "user", "content": "Please carry out one round of your recipe."}
    ]
}
CONTENT = {
    "propose_change": ("change", ("instructions", "model", "reasoning_effort")),
    "propose_recipe": ("recipe", ("recipe",)),
}


def new_round(handler_id: str) -> dict[str, Any]:
    """Start a round and its first stretch; ApiRefusal while a run is going."""
    settings = harness.improver_settings()
    return improver_api.create_round(
        handler_id, settings.name, settings.reasoning_effort
    )


def decision(approved: bool, reason: str) -> dict[str, Any]:
    """The handler's decision, in the form the improver is resumed with."""
    if approved:
        return {"decisions": [{"type": "approve"}]}
    message = f"A handler rejected your proposal and said why: {reason}"
    return {"decisions": [{"type": "reject", "message": message}]}


def _first_evaluations(round_id: int, run_id: int) -> bool:
    """Run the evaluations the current version lacks; say whether it has them all."""
    missing = improver_api.first_evaluations(round_id)
    if missing:
        version = improver_api.get_view(round_id)["current_version"]["version"]
        used = used_by(version)
        done = len(EVALUATIONS) - len(missing)
        for number, eval_set in enumerate(missing, start=done + 1):
            improver_api.record_stage(round_id, FIRST, number)
            run_round_evaluation(round_id, run_id, eval_set, used, False)
    return not improver_api.first_evaluations(round_id)


def _proposal(request: dict[str, Any]) -> tuple[str, dict[str, str], str]:
    """The kind, content and reason of the proposal the improver is waiting on."""
    kind, names = CONTENT[request["name"]]
    args = request["args"]
    return kind, {name: args[name] for name in names}, args["reason"]


def _improve(
    round_id: int,
    run_id: int,
    resume: dict[str, Any] | None,
    llm: BaseChatModel | None,
    saver: BaseCheckpointSaver | None,
) -> None:
    round_row = improver_api.get_round(round_id)
    if resume is None:
        if not _first_evaluations(round_id, run_id):
            improver_api.record_stage(round_id, FINISHED, 0)
            return
        improver_api.record_stage(round_id, WORKING, 0)
    graph = improver.build_improver(
        improver_api.recipe_text(round_row["recipe_version"]),
        llm or harness.improver_model(harness.improver_settings()),
        saver or checkpoint.saver(),
    )
    session = f"round-{round_id}"
    with tracing.trace(session, [session, f"run-{run_id}"]) as traced:
        config: RunnableConfig = {
            **traced,
            "configurable": {"thread_id": round_row["thread_id"]},
        }
        context = ImproverContext(round_id, run_id)
        start = START if resume is None else Command(resume=resume)
        while True:
            result = graph.invoke(start, config, context=context, durability="sync")
            if "__interrupt__" not in result:
                improver_api.record_stage(round_id, FINISHED, 0)
                return
            request = result["__interrupt__"][0].value["action_requests"][0]
            try:
                improver_api.record_proposal(round_id, *_proposal(request))
                return
            except ApiRefusal as refusal:
                start = Command(resume=decision(False, refusal.detail))


def work_stretch(
    round_id: int,
    run_id: int,
    resume: dict[str, Any] | None,
    llm: BaseChatModel | None = None,
    saver: BaseCheckpointSaver | None = None,
) -> None:
    """Work one stretch of a round, then let go of the one-run rule.

    It starts the round (the first evaluations, then the improver) or, with the
    handler's decision, resumes the improver where it paused. A stretch ends when
    the improver pauses for a handler or finishes. A round a handler has stopped
    records nothing more, so a refusal then is the end, not a failure.
    """
    try:
        _improve(round_id, run_id, resume, llm, saver)
    except ApiRefusal:
        if improver_api.get_round(round_id)["stage"] != STOPPED:
            raise
    except Exception:
        logger.exception("Round %s failed", round_id)
        improver_api.record_stage(round_id, STOPPED, 0)
        raise
    finally:
        improver_api.finish_run(run_id)
