"""Work the agent does after it has answered, on a thread of its own.

Each piece is registered with the AgentCore app as an async task before the request
is answered and completed when the work ends, however it ends, so Runtime's ping says
HealthyBusy while anything is going and the session lasts as long as its work.
"""

import logging
from collections.abc import Callable
from threading import Thread
from typing import Any

logger = logging.getLogger(__name__)


class BackgroundWork:
    """Starts work on a thread, tracked by the AgentCore app's two task methods."""

    def __init__(
        self,
        add_task: Callable[[str], int],
        complete_task: Callable[[int], object],
    ) -> None:
        self._add_task = add_task
        self._complete_task = complete_task

    def start(self, name: str, work: Callable[..., object], *arguments: Any) -> None:
        """Register `work` as a task, then run it with `arguments` on its own thread."""
        task_id = self._add_task(name)
        Thread(target=self._run, args=(task_id, name, work, arguments)).start()

    def _run(
        self,
        task_id: int,
        name: str,
        work: Callable[..., object],
        arguments: tuple[Any, ...],
    ) -> None:
        try:
            work(*arguments)
        except Exception:
            logger.exception("The agent's work %s failed", name)
        finally:
            self._complete_task(task_id)
