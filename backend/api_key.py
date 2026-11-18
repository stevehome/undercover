"""The agent's API key: checks the `X-API-Key` header against `UNDERCOVER_API_KEY`."""

import os
import secrets
from typing import Annotated

from fastapi import Header

from backend.errors import Unauthorized

API_KEY_VARIABLE = "UNDERCOVER_API_KEY"

KeyHeader = Annotated[str | None, Header(alias="X-API-Key", include_in_schema=False)]


def is_valid(key: str | None) -> bool:
    """Say whether the key matches the one set now; an unset key matches nothing."""
    expected = os.environ.get(API_KEY_VARIABLE)
    if not key or not expected:
        return False
    return secrets.compare_digest(key.encode(), expected.encode())


def require_api_key(x_api_key: KeyHeader = None) -> None:
    """Refuse a request that doesn't carry the agent's API key."""
    if not is_valid(x_api_key):
        raise Unauthorized("This needs the agent's API key")
