"""A tool call that something refused, with who refused it and why."""

BY_APP = "the app"
BY_GATEWAY = "the Gateway"
BY_CONTEXT_LAYER = "the context layer"
BY_MEMORY = "the memory"


class Refusal(Exception):  # noqa: N818 - a refusal, not a failure
    """Something refused a tool call; the message says who and why, for the model."""

    def __init__(self, source: str, detail: str) -> None:
        super().__init__(f"{source}: {detail}")
        self.source = source
        self.detail = detail

    @property
    def message(self) -> str:
        """What the model reads: a refusal, never an answer that looks like success."""
        return f"Refused by {self.source}: {self.detail}"
