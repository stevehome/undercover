"""The agent's word to the app, every minute, that work is still going."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from threading import Event, Thread

MILLISECONDS_PER_SECOND = 1_000
INTERVAL_MILLISECONDS = 60 * MILLISECONDS_PER_SECOND


@contextmanager
def beating(
    tell: Callable[[], None], milliseconds: int = INTERVAL_MILLISECONDS
) -> Iterator[None]:
    """Call `tell` every `milliseconds` in the background while the block runs."""
    done = Event()
    beat = Thread(target=_beat, args=(tell, milliseconds, done))
    beat.start()
    try:
        yield
    finally:
        done.set()
        beat.join()


def _beat(tell: Callable[[], None], milliseconds: int, done: Event) -> None:
    while not done.wait(milliseconds / MILLISECONDS_PER_SECOND):
        tell()
