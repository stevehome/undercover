"""A stopwatch for spots that can stall: it logs each step, and warns when it ran long.

Nothing configures logging, so a fast run stays out of sight at INFO and a slow one
(SLOW_MS or more) shows as a warning in the console, with the step that took the time.
"""

import logging
import time

SLOW_MS = 3000
NANOSECONDS_PER_MS = 1_000_000

logger = logging.getLogger("undercover.timing")


class Stopwatch:
    """Times a piece of work in steps; `lap` ends a step and `log` reports them all."""

    def __init__(self, what: str):
        self.what = what
        self.started = self.last = time.monotonic_ns()
        self.steps: list[str] = []

    def lap(self, step: str) -> None:
        """Record how long the step since the last lap took."""
        now = time.monotonic_ns()
        self.steps.append(f"{step} {(now - self.last) // NANOSECONDS_PER_MS} ms")
        self.last = now

    def log(self) -> None:
        """Log the total and the steps, as a warning when the total was slow."""
        total = (time.monotonic_ns() - self.started) // NANOSECONDS_PER_MS
        level = logging.WARNING if total >= SLOW_MS else logging.INFO
        logger.log(level, "%s took %d ms (%s)", self.what, total, ", ".join(self.steps))
