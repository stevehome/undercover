"""Getting ready, on the first request and once in the process.

On Runtime every session starts from one snapshot, so nothing is fetched or opened
when the agent's code is imported: a key or a connection made then would be shared by
every session. If getting ready fails, that request answers the error and the next
one tries again.
"""

import random
from threading import Lock

from agent import api, backend_http, checkpoint, credentials

_getting_ready = Lock()
_ready = False


def ensure() -> None:
    """Get ready if the process isn't yet: credentials, the agent's key, the pool."""
    global _ready  # noqa: PLW0603 - once in the process
    with _getting_ready:
        if _ready:
            return
        if credentials.on_runtime():
            random.seed()
            credentials.fetch()
        backend_http.require_key()
        checkpoint.saver()
        api.stop_unfinished_runs()
        _ready = True


def forget() -> None:
    """Forget that the process is ready, so the next request gets ready again."""
    global _ready  # noqa: PLW0603
    with _getting_ready:
        _ready = False
