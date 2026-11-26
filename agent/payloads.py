"""Reading a payload sent to an AgentCore app: the operation it names, and its inputs.

A payload is an object with an `operation` and the inputs that operation takes. A
payload that is not right is answered with a 400 that says what is wrong, and never
with the value that was wrong: a payload may hold a handler's sign-in.
"""

from collections.abc import Mapping
from typing import Any, NamedTuple

from pydantic import BaseModel, ConfigDict, ValidationError

BAD_REQUEST = 400
UNAUTHORIZED = 401
OK = 200


class Inputs(BaseModel):
    """An operation's inputs; any input it doesn't name is wrong."""

    model_config = ConfigDict(extra="forbid")


class NoInputs(Inputs):
    pass


class Answer(NamedTuple):
    """What a payload is answered with."""

    status: int
    body: dict[str, Any]


def wrong(message: str) -> Answer:
    """The answer to a payload that is not right."""
    return Answer(BAD_REQUEST, {"error": message})


def _describe(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in problem['loc'])}: {problem['msg']}"
        for problem in error.errors()
    )


def read(
    payload: Any, operations: Mapping[str, type[Inputs]]
) -> tuple[str, Inputs] | Answer:
    """Return the operation a payload names with its checked inputs, or the 400."""
    if not isinstance(payload, dict) or "operation" not in payload:
        return wrong('Send an object with an "operation" and its inputs')
    name = payload["operation"]
    inputs = operations.get(name)
    if inputs is None:
        known = ", ".join(operations)
        return wrong(f"Unknown operation {name!r}; the operations are {known}")
    given = {key: value for key, value in payload.items() if key != "operation"}
    try:
        return name, inputs.model_validate(given)
    except ValidationError as error:
        return wrong(f"{name}: {_describe(error)}")
