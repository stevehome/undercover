import boto3
import httpx

from agent.sigv4 import SigV4Auth


def test_a_request_is_signed_for_the_service_in_the_regions_scope():
    session = boto3.Session(
        aws_access_key_id="AKIATESTKEY",
        aws_secret_access_key="secret",  # noqa: S106 - a made-up test key
        aws_session_token="token",  # noqa: S106 - a made-up test token
        region_name="eu-west-2",
    )
    request = httpx.Request("POST", "https://gateway.example/mcp", json={"a": 1})

    signed = next(SigV4Auth("bedrock-agentcore", session).auth_flow(request))

    authorization = signed.headers["authorization"]
    assert authorization.startswith("AWS4-HMAC-SHA256 Credential=AKIATESTKEY/")
    assert "/eu-west-2/bedrock-agentcore/aws4_request" in authorization
    assert signed.headers["x-amz-date"]
    assert signed.headers["x-amz-security-token"] == "token"  # noqa: S105
