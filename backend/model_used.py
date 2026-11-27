"""The model and reasoning effort a run is recorded with.

The claim agent's are the current configuration's, or `MODEL_NAME` with no effort set
when it is. The Copilot's are the improver's: a general model, not the claim agent's
configuration. The improver's are written here once, and the agent reads them from the
stretch's record.
"""

import os

from backend import versions
from backend.runs import RunSettings

NO_EFFORT = "default"
IMPROVER_MODEL = "openai/gpt-6-luna"
IMPROVER_EFFORT = "medium"
COPILOT_MODEL = IMPROVER_MODEL
COPILOT_EFFORT = IMPROVER_EFFORT
APPEAL_CHECK_MODEL = "openai/gpt-6-luna"
APPEAL_CHECK_EFFORT = "none"


def for_claim_agent() -> RunSettings:
    """What a dispatch or an evaluation on the current configuration runs on."""
    configuration = versions.current_configuration()
    name = os.getenv("MODEL_NAME")
    return RunSettings(
        model=name or configuration["model"],
        reasoning_effort=NO_EFFORT if name else configuration["reasoning_effort"],
        configuration_version=configuration["version"],
    )


def for_copilot() -> tuple[str, str]:
    """The model and effort a Copilot turn runs on: the improver's general model."""
    name = os.getenv("MODEL_NAME")
    return (name, NO_EFFORT) if name else (COPILOT_MODEL, COPILOT_EFFORT)


def for_appeal_check() -> tuple[str, str | None]:
    """The model and effort that check an appeal's text, as the claims' check does.

    With `MODEL_NAME` set the effort is left to the model.
    """
    name = os.getenv("MODEL_NAME")
    return (name, None) if name else (APPEAL_CHECK_MODEL, APPEAL_CHECK_EFFORT)


def for_improver() -> tuple[str, str]:
    """The model and effort a stretch of the improver's work is recorded with."""
    name = os.getenv("MODEL_NAME")
    return (name, NO_EFFORT) if name else (IMPROVER_MODEL, IMPROVER_EFFORT)
