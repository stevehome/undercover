from agent import harness


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert harness.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert harness.model().model_name == "openrouter/free"


def test_default_model_has_low_effort_and_another_has_none(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert harness.model_settings() == harness.ModelSettings("openai/gpt-6-luna", "low")
    assert harness.model().reasoning_effort == "low"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert harness.model_settings() == harness.ModelSettings("openrouter/free", "none")
    assert harness.model().reasoning_effort is None


def test_model_has_a_request_timeout(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    assert harness.model().request_timeout == harness.MODEL_TIMEOUT_SECONDS
