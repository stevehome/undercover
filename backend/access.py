"""Who may read what both the agent and the dashboard use: the key or a handler."""

from typing import Annotated

from fastapi import Depends, Header
from jwt import PyJWKClient

from backend import api_key
from backend.auth import handler_for_token, key_client

BEARER_PREFIX = "Bearer "


def key_or_handler(
    keys: Annotated[PyJWKClient, Depends(key_client)],
    x_api_key: api_key.KeyHeader = None,
    authorization: Annotated[str | None, Header(include_in_schema=False)] = None,
) -> None:
    """Let a request through with the agent's key, or else with a handler's sign-in."""
    if api_key.is_valid(x_api_key):
        return
    token = None
    if authorization and authorization.startswith(BEARER_PREFIX):
        token = authorization.removeprefix(BEARER_PREFIX)
    handler_for_token(token, keys)
