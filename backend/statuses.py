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
