"""Signing a request with AWS Signature Version 4, as boto3 does for its own calls."""

import boto3
import httpx
from boto3 import Session
from botocore.auth import SigV4Auth as BotocoreSigV4Auth
from botocore.awsrequest import AWSRequest

SIGNED_HEADERS = ("Authorization", "X-Amz-Date", "X-Amz-Security-Token")


class SigV4Auth(httpx.Auth):
    """Sign each request with the credentials and region the AWS CLI uses."""

    requires_request_body = True

    def __init__(self, service: str, session: Session | None = None) -> None:
        session = session or boto3.Session()
        self.credentials = session.get_credentials()
        self.region = session.region_name
        self.service = service

    def auth_flow(self, request: httpx.Request):
        headers = {
            "Host": request.url.netloc.decode(),
            "Content-Type": request.headers.get("content-type", ""),
        }
        signed = AWSRequest(
            method=request.method,
            url=str(request.url),
            data=request.content,
            headers=headers,
        )
        BotocoreSigV4Auth(
            self.credentials.get_frozen_credentials(), self.service, self.region
        ).add_auth(signed)
        for name in SIGNED_HEADERS:
            if name in signed.headers:
                request.headers[name] = signed.headers[name]
        yield request
