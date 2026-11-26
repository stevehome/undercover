"""Asking the agent on AgentCore Runtime: the same payload, through boto3.

A request is tried once: a retried request could start the same work twice. The claim
agent's start a session of their own; the Copilot's go to its conversation's session.
This is the one module that calls Runtime.
"""

import json
import uuid
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
)

from backend.errors import ServiceUnavailable, Unconfirmed

CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 20
SESSION_PREFIX = "session-"
BUSY_CODE = "ConflictException"


class SessionBusy(ServiceUnavailable):
    """The session is working and can't take another request just now."""


def _client() -> Any:
    """The Runtime client, in the region the app runs in, with one attempt per call."""
    config = Config(
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
        read_timeout=READ_TIMEOUT_SECONDS,
        retries={"total_max_attempts": 1},
    )
    return boto3.client("bedrock-agentcore", config=config)


def post(
    payload: dict[str, Any], arn: str, session_id: str | None = None
) -> dict[str, Any]:
    """Send a payload to a runtime, in a new session unless one is named.

    ServiceUnavailable when it never connected or Runtime answered with an error:
    nothing was started. Unconfirmed when anything else goes wrong once it was sent.
    """
    try:
        response = _client().invoke_agent_runtime(
            agentRuntimeArn=arn,
            runtimeSessionId=session_id or f"{SESSION_PREFIX}{uuid.uuid4().hex}",
            payload=json.dumps(payload).encode(),
            contentType="application/json",
            accept="application/json",
        )
    except (ConnectTimeoutError, EndpointConnectionError) as error:
        raise ServiceUnavailable("The agent's runtime couldn't be reached") from error
    except ClientError as error:
        if error.response["Error"]["Code"] == BUSY_CODE:
            raise SessionBusy("The session is busy") from error
        raise ServiceUnavailable(f"The agent's runtime refused: {error}") from error
    except BotoCoreError as error:
        raise Unconfirmed(str(error)) from error
    try:
        return json.loads(response["response"].read())
    except (BotoCoreError, ValueError) as error:
        raise Unconfirmed("The agent's answer was cut off") from error
