"""Who is signed in: checks a handler's Supabase access token.

The token is signed with one of the project's public keys, so no secret is needed.
"""

import os
from functools import cache
from typing import Annotated, Any

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from backend import reference
from backend.errors import Forbidden, ServiceUnavailable, Unauthorized

AUDIENCE = "authenticated"
ALGORITHMS = ["ES256", "RS256"]

bearer = HTTPBearer(auto_error=False)


@cache
def key_client() -> PyJWKClient:
    """Return the client for the project's public keys, made once."""
    url = os.environ.get("VITE_SUPABASE_URL")
    if not url:
        raise ServiceUnavailable("Sign-in isn't set up: VITE_SUPABASE_URL is missing")
    return PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json")


def signed_in_handler(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    keys: Annotated[PyJWKClient, Depends(key_client)],
) -> dict[str, Any]:
    """Return the handler whose valid token came with the request, or Unauthorized."""
    if credentials is None:
        raise Unauthorized("Sign in to do this")
    token = credentials.credentials
    try:
        claims = jwt.decode(
            token,
            keys.get_signing_key_from_jwt(token).key,
            algorithms=ALGORITHMS,
            audience=AUDIENCE,
        )
    except jwt.PyJWTError as error:
        raise Unauthorized("Your sign-in isn't valid; sign in again") from error
    handler = reference.handler_by_email(claims.get("email", ""))
    if handler is None:
        raise Unauthorized("This account is not a claims handler")
    return handler


def senior_handler(
    handler: Annotated[dict[str, Any], Depends(signed_in_handler)],
) -> dict[str, Any]:
    """Return the signed-in handler if they can sign off over the limit."""
    if not handler["can_approve_over_limit"]:
        raise Forbidden(
            f"{handler['name']} can't do this: only a handler who can sign off "
            "payouts over the limit can"
        )
    return handler
