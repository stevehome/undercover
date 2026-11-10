"""Errors the backend's logic raises; `main.py` turns them into HTTP responses."""


class NotFound(Exception):
    """Something asked for does not exist (404)."""


class Conflict(Exception):
    """The request clashes with the current state (409)."""


class ServiceUnavailable(Exception):
    """A service we depend on can't be reached (503)."""
