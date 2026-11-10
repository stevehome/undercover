"""What a claim run knows, handed to its tools and nodes."""

from dataclasses import dataclass


@dataclass
class ClaimContext:
    """The claim an agent is deciding, and the run it is worked in, if any."""

    claim_id: str
    run_id: int | None
