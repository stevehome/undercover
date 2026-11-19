from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mangum import Mangum
from sqlalchemy import inspect

from backend import dashboard_files, db
from backend.main import app, handler
from conftest import API_KEY

NO_CONTEXT: Any = None


def function_url_event(path):
    """The event a Lambda Function URL sends for a GET."""
    return {
        "version": "2.0",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"host": "example.lambda-url.us-east-1.on.aws"},
        "isBase64Encoded": False,
        "requestContext": {
            "http": {
                "method": "GET",
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "203.0.113.1",
            },
            "stage": "$default",
        },
    }


@pytest.fixture
def lambda_with_three_variables(tmp_path, monkeypatch):
    """Lambda's environment: a database already seeded, and three variables."""
    url = f"sqlite:///{tmp_path / 'lambda.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    db.forget_engines()
    with db.connection():
        pass
    db.forget_engines()
    for name in (
        "DATABASE_PATH",
        "OPENROUTER_API_KEY",
        "UNDERCOVER_AGENT",
        "MODEL_NAME",
        "LANGFUSE_SECRET_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "undercover")
    monkeypatch.setenv("VITE_SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("UNDERCOVER_API_KEY", API_KEY)
    yield
    db.forget_engines()


def test_the_handler_answers_health_for_a_function_url_event():
    answer = handler(function_url_event("/api/health"), NO_CONTEXT)

    assert answer["statusCode"] == 200
    assert '"ok"' in answer["body"]


def test_the_handler_serves_the_dashboard_it_is_given(tmp_path):
    (tmp_path / "index.html").write_text("<html>the dashboard</html>")
    small = FastAPI()
    dashboard_files.serve(small, tmp_path)

    answer = Mangum(small, lifespan="off")(function_url_event("/"), NO_CONTEXT)

    assert answer["statusCode"] == 200
    assert "the dashboard" in answer["body"]


def test_with_only_the_three_variables_the_backend_answers(
    lambda_with_three_variables, as_handler
):
    client = TestClient(app)

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/claims", headers={"X-API-Key": API_KEY}).status_code == 200
    assert client.get("/api/handlers", headers=as_handler()).status_code == 200
    assert client.get("/api/claims").status_code == 401


def test_on_lambda_nothing_is_created_or_seeded(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'empty.db'}"
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "undercover")
    db.forget_engines()

    made = db.engine(url)

    assert inspect(made).get_table_names() == []
    db.forget_engines()
