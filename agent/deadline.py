"""A total time limit for an HTTP response.

httpx's timeouts apply to each read, so a server that keeps sending a few bytes
never trips them and a call can wait for ever. This transport fails a response
that is still arriving once its deadline has passed.
"""

import time
from collections.abc import Iterator
from typing import cast

import httpx

NANOSECONDS = 1_000_000_000


class _Body(httpx.SyncByteStream):
    """A response body that raises a timeout once its deadline has passed."""

    def __init__(self, stream: httpx.SyncByteStream, deadline_ns: int):
        self.stream = stream
        self.deadline_ns = deadline_ns

    def __iter__(self) -> Iterator[bytes]:
        for chunk in self.stream:
            if time.monotonic_ns() > self.deadline_ns:
                raise httpx.ReadTimeout("The response passed its deadline")
            yield chunk

    def close(self) -> None:
        self.stream.close()


class _Deadline(httpx.BaseTransport):
    """A transport that gives each response a total number of seconds to arrive."""

    def __init__(self, seconds: int):
        self.seconds = seconds
        self.transport = httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        deadline_ns = time.monotonic_ns() + self.seconds * NANOSECONDS
        response = self.transport.handle_request(request)
        response.stream = _Body(
            cast(httpx.SyncByteStream, response.stream), deadline_ns
        )
        return response

    def close(self) -> None:
        self.transport.close()


def client(seconds: int) -> httpx.Client:
    """Return an HTTP client whose every response has this many seconds to arrive."""
    return httpx.Client(transport=_Deadline(seconds))
