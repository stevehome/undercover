import pytest

from agent import harness

VERSION_1 = {"model": "openai/gpt-6-luna", "reasoning_effort": "low"}


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)


def test_a_versions_model_and_effort_are_used():
    settings = harness.model_settings(VERSION_1)

    assert settings == harness.ModelSettings("openai/gpt-6-luna", "low")
    assert harness.model(settings).model_name == "openai/gpt-6-luna"
    assert harness.model(settings).reasoning_effort == "low"


def test_another_effort_is_passed_on():
    settings = harness.model_settings({**VERSION_1, "reasoning_effort": "none"})

    assert harness.model(settings).reasoning_effort == "none"


def test_model_name_wins_with_no_effort_set(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")

    settings = harness.model_settings(VERSION_1)

    assert settings == harness.ModelSettings("openrouter/free", "default")
    assert harness.model(settings).model_name == "openrouter/free"
    assert harness.model(settings).reasoning_effort is None


def test_model_has_a_request_timeout():
    settings = harness.model_settings(VERSION_1)

    assert harness.model(settings).request_timeout == harness.MODEL_TIMEOUT_SECONDS
