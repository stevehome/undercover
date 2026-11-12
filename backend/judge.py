"""The judge: asks Jev how well an agent's explanation matches a handler's.

The one place that calls the Decisions endpoint, which is in alpha. Jev answers a
`score` question over the grades F, C, B and A, and two `noul` questions that say
which part matched, since Jev doesn't write an explanation.
"""

import os
from dataclasses import dataclass
from decimal import Decimal
from functools import cache
from typing import Any

from openrouter import OpenRouter

JEV = "typesafe/jev-1.13"
ORIGIN = os.environ.get("OPENROUTER_ORIGIN", "https://openrouter.ai")
TIMEOUT_MS = 10_000

# Jev numbers the grades by their position in the list, so F is 0 and A is 3.
RUBRIC = {
    "F": "different grounds from the handler's reason, or it contradicts the "
    "handler's reason",
    "C": "partly the same as the handler's reason: one of the handler's grounds or "
    "the section is missing, or it adds a ground the handler did not give",
    "B": "the same grounds and the same section of the policy wording as the "
    "handler's reason",
    "A": "the same grounds and section as the handler's reason, and clearly better "
    "expressed: clearer for the customer, with the section and the figures, "
    "shorter, and no jargon",
}
GRADES = list(RUBRIC)

QUESTIONS = {
    "grade": {
        "type": "score",
        "instructions": "An expert claims handler decided a travel insurance claim "
        "and gave `handler.reason`, resting on `handler.reference`. Grade how well "
        "`agent.rationale`, resting on `agent.section`, explains the same decision.",
        "criteria": [f"{letter}: {text}" for letter, text in RUBRIC.items()],
    },
    "same_grounds": {
        "type": "noul",
        "instructions": "`agent.rationale` gives the same main grounds for the "
        "decision as `handler.reason`",
    },
    "same_section": {
        "type": "noul",
        "instructions": "`agent.section` is the same section of the policy wording "
        "as `handler.reference`",
    },
}


@dataclass(frozen=True)
class Judgement:
    """Jev's grade of one explanation, with the two checks as probabilities."""

    score: Decimal
    letter: str
    same_grounds: Decimal
    same_section: Decimal
    cost: Decimal


@cache
def _client() -> OpenRouter:
    return OpenRouter(api_key=os.environ["OPENROUTER_API_KEY"])


def _decimal(value: Any) -> Decimal:
    """An answer from the SDK, which reports numbers as floats, to four places."""
    return Decimal(str(round(value, 4)))


def judge(handler: dict[str, str], agent: dict[str, str]) -> Judgement:
    """Ask Jev to grade the agent's explanation against the handler's.

    The call passes `server_url` (the client ignores one set on it), times out
    after 10 seconds and doesn't retry, so a slow judge can't hold up finishing.
    """
    response = _client().alpha.decisions.create(
        model=JEV,
        state={"handler": handler, "agent": agent},
        questions=QUESTIONS,
        server_url=ORIGIN,
        timeout_ms=TIMEOUT_MS,
        retries=None,
    )
    answers: Any = response.answers
    probabilities = answers["grade"].probabilities
    return Judgement(
        score=_decimal(answers["grade"].score),
        letter=GRADES[int(max(probabilities, key=probabilities.__getitem__))],
        same_grounds=_decimal(answers["same_grounds"].noul),
        same_section=_decimal(answers["same_section"].noul),
        cost=Decimal(str(response.usage.cost or 0)),
    )
