"""Asking the agent on AgentCore Runtime: the same payload, through boto3.

Each request starts a session of its own, and is tried once: a retried request could
start the same work twice. This is the one module that calls Runtime.
"""

import json
import os
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


def _client() -> Any:
    """The Runtime client, in the region the app runs in, with one attempt per call."""
    config = Config(
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
        read_timeout=READ_TIMEOUT_SECONDS,
        retries={"total_max_attempts": 1},
    )
    return boto3.client("bedrock-agentcore", config=config)


def post(payload: dict[str, Any]) -> dict[str, Any]:
    """Send a payload to the runtime in a new session and return the agent's answer.

    ServiceUnavailable when it never connected or Runtime answered with an error:
    nothing was started. Unconfirmed when anything else goes wrong once it was sent.
    """
    try:
        response = _client().invoke_agent_runtime(
            agentRuntimeArn=os.environ["UNDERCOVER_AGENT_RUNTIME"],
            runtimeSessionId=f"{SESSION_PREFIX}{uuid.uuid4().hex}",
            payload=json.dumps(payload).encode(),
            contentType="application/json",
            accept="application/json",
        )
    except (ConnectTimeoutError, EndpointConnectionError) as error:
        raise ServiceUnavailable("The agent's runtime couldn't be reached") from error
    except ClientError as error:
        raise ServiceUnavailable(f"The agent's runtime refused: {error}") from error
    except BotoCoreError as error:
        raise Unconfirmed(str(error)) from error
    try:
        return json.loads(response["response"].read())
    except (BotoCoreError, ValueError) as error:
        raise Unconfirmed("The agent's answer was cut off") from error
