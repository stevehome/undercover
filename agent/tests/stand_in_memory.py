"""A stand-in for AgentCore Memory: events kept as written, memories put by a test."""

from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any


class StandInMemory:
    """Keeps each event a claim saves, and answers a search from the memories given."""

    def __init__(self) -> None:
        self.events: list[tuple[tuple[str, ...], str, Mapping[str, Any]]] = []
        self.memories: list[tuple[tuple[str, ...], str]] = []
        self.searches: list[tuple[tuple[str, ...], str | None]] = []
        self.failure: Exception | None = None

    def put(
        self, namespace: tuple[str, ...], key: str, value: Mapping[str, Any]
    ) -> None:
        if self.failure:
            raise self.failure
        self.events.append((namespace, key, value))

    def search(
        self, namespace_prefix: tuple[str, ...], *, query: str | None = None, **_: Any
    ) -> list[Any]:
        if self.failure:
            raise self.failure
        self.searches.append((namespace_prefix, query))
        size = len(namespace_prefix)
        return [
            SimpleNamespace(namespace=namespace, value={"content": text})
            for namespace, text in self.memories
            if namespace[:size] == namespace_prefix
        ]
