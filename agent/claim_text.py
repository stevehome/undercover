"""A claim as text, the same wherever it is read: by the model or by the check."""

import json
from typing import Any


def claim_text(claim: dict[str, Any]) -> str:
    """Return the claim as the model and the check read it."""
    return json.dumps(claim, indent=2)
