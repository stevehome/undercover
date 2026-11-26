"""Getting the Copilot ready, on the first request and once in the process.

As the claim agent's (`readiness.py`): nothing is fetched or opened when the code is
imported, since on Runtime every session starts from one snapshot, and a failure
answers its error and is tried again by the next request. The Copilot fetches only
the model's key and the database's address, never the agent's key.
"""

import random
from threading import Lock

from agent import checkpoint, credentials

NEEDED = {"OPENROUTER_API_KEY", "DATABASE_URL"}

_getting_ready = Lock()
_ready = False


def ensure() -> None:
    """Get ready if the process isn't yet: credentials, then the pool."""
    global _ready  # noqa: PLW0603 - once in the process
    with _getting_ready:
        if _ready:
            return
        if credentials.on_runtime():
            random.seed()
            credentials.fetch(NEEDED)
        checkpoint.saver()
        _ready = True


def forget() -> None:
    """Forget that the process is ready, so the next request gets ready again."""
    global _ready  # noqa: PLW0603
    with _getting_ready:
        _ready = False
