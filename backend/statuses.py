"""The statuses a claim, a run and a run's claim can have, written once."""

from enum import StrEnum


class ClaimStatus(StrEnum):
    """Where a claim stands in the queue."""

    WAITING = "waiting"
    IN_PROGRESS = "in progress"
    WAITING_FOR_SIGN_OFF = "waiting for sign-off"
    DECIDED = "decided"


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
