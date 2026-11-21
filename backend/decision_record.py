"""What a decision record must hold: claims manual section 14.

"Every decision record holds the decision, the payout, the calculation, the section
relied on, a reason in plain language, who or what made the decision and when."
Each refusal names section 14 and says what is missing.
"""

from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, WithJsonSchema, field_validator, model_validator

from backend.errors import Invalid
from backend.money import Amount

SECTION_14 = "Claims manual section 14"

DecisionKind = Annotated[
    Literal["approve", "decline", "refer"],
    WithJsonSchema(
        {"type": "string", "description": "approve, decline or refer"},
        mode="validation",
    ),
]
"""The Gateway makes an enum its own Cedar type, which a policy can't compare with a
string; the document says `string`, and the check still allows only the three."""


class Decision(BaseModel):
    """A decision as the agent records it, checked against section 14."""

    decision: DecisionKind
    payout: Amount
    reason: str
    policy_reference: str
    decided_by: str

    @field_validator("reason", "policy_reference", "decided_by")
    @classmethod
    def not_blank(cls, value: str, info) -> str:
        if not value.strip():
            what = {
                "reason": "a reason in plain language",
                "policy_reference": "the section relied on",
                "decided_by": "who or what made the decision",
            }[info.field_name]
            raise ValueError(f"{SECTION_14}: a decision record needs {what}")
        return value

    @model_validator(mode="after")
    def payout_fits_the_decision(self) -> Self:
        if self.decision == "approve" and self.payout == 0:
            raise ValueError(f"{SECTION_14}: an approval needs a payout above zero")
        if self.decision != "approve" and self.payout != 0:
            raise ValueError(f"{SECTION_14}: a decline or a referral pays nothing")
        return self


def require_calculation(kept: tuple[list, Decimal] | None, payout: Decimal) -> list:
    """Return the calculation an approval rests on, or raise `Invalid`.

    An approval needs a calculation on file for this attempt, and a payout equal to it.
    """
    if kept is None:
        raise Invalid(
            f"{SECTION_14}: an approval needs the payout's calculation on file "
            "for this attempt, from calculate_payout"
        )
    lines, calculated = kept
    if calculated != payout:
        raise Invalid(
            f"{SECTION_14}: the payout of {payout} is not the calculation's "
            f"payout of {calculated}"
        )
    return lines
