"""The statuses a claim, a run and a run's claim can have, written once."""

from enum import StrEnum


class ClaimStatus(StrEnum):
    """Where a claim stands in the queue."""

    WAITING = "waiting"
    IN_PROGRESS = "in progress"
    WAITING_FOR_SIGN_OFF = "waiting for sign-off"
    SENT_BACK = "sent back"
    DECIDED = "decided"


class AppealStatus(StrEnum):
    """Where an appeal to the ombudsman stands."""

    WITH_THE_OMBUDSMAN = "with the ombudsman"
    UPHELD = "upheld"
    NOT_UPHELD = "not upheld"


class StepKind(StrEnum):
    """What a step of the agent's work is: a note, a tool call, a lookup in the
    context layer, a memory search or save, or a refusal."""

    NOTE = "note"
    TOOL_CALL = "tool_call"
    LOOKUP = "lookup"
    MEMORY_SEARCH = "memory_search"
    MEMORY_SAVE = "memory_save"
    REFUSAL = "refusal"


class RunKind(StrEnum):
    """What a run is for."""

    DISPATCH = "dispatch"
    EVALUATION = "evaluation"
    IMPROVER = "improver"


class RunStatus(StrEnum):
    """Where a run stands; only one run can be running."""

    RUNNING = "running"
    FINISHED = "finished"
    STOPPED = "stopped"


class ItemStatus(StrEnum):
    """Where one claim of a run stands."""

    TO_DO = "to do"
    IN_PROGRESS = "in progress"
    DONE = "done"
    LEFT_FOR_A_HANDLER = "left for a handler"
    STILL_IN_PROGRESS = "still in progress"


class Verdict(StrEnum):
    """What a round decided about the version it tried."""

    KEPT = "kept"
    ROLLED_BACK = "rolled back"


class Stage(StrEnum):
    """Where an improvement round has got to."""

    FIRST_EVALUATIONS = "first evaluations"
    IMPROVER_WORKING = "improver working"
    CHANGE_WAITING = "change waiting"
    EVALUATIONS = "evaluations"
    VERDICT = "verdict"
    RECIPE_WAITING = "recipe waiting"
    FINISHED = "finished"
    STOPPED = "stopped"


class ProposalKind(StrEnum):
    """What the improver proposes: a new configuration or a new recipe."""

    CHANGE = "change"
    RECIPE = "recipe"


class ProposalStatus(StrEnum):
    """Where a proposal stands; nothing it proposes counts until it is approved."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class TurnStatus(StrEnum):
    """Where a Copilot conversation's turn stands. `STOPPED` is never stored: it is
    what a turn that has worked too long reads as."""

    WORKING = "working"
    WAITING = "waiting for a confirmation"
    DONE = "done"
    FAILED = "failed"
    STOPPED = "stopped"


class StepState(StrEnum):
    """Where one step of the Copilot's turn stands."""

    WORKING = "working"
    DONE = "done"
    REFUSED = "refused"
    FAILED = "failed"


class CardKind(StrEnum):
    """What a step of the Copilot's turn looks at or does, for its card."""

    CLAIMS = "claims"
    CUSTOMERS = "customers"
    CONTEXT = "context"
    AGENT_WORK = "agent work"
    MEMORY = "memory"
    ACTION = "action"
