"""The model and reasoning effort a run is recorded with.

The claim agent's are the current configuration's, or `MODEL_NAME` with no effort set
when it is. The improver's are written here once, and the agent reads them from the
stretch's record.
"""

import os

from backend import versions
from backend.runs import RunSettings

NO_EFFORT = "default"
IMPROVER_MODEL = "openai/gpt-6-luna"
IMPROVER_EFFORT = "medium"


def for_claim_agent() -> RunSettings:
    """What a dispatch or an evaluation on the current configuration runs on."""
    configuration = versions.current_configuration()
    name = os.getenv("MODEL_NAME")
    return RunSettings(
        model=name or configuration["model"],
        reasoning_effort=NO_EFFORT if name else configuration["reasoning_effort"],
        configuration_version=configuration["version"],
    )


def for_improver() -> tuple[str, str]:
    """The model and effort a stretch of the improver's work is recorded with."""
    name = os.getenv("MODEL_NAME")
    return (name, NO_EFFORT) if name else (IMPROVER_MODEL, IMPROVER_EFFORT)
