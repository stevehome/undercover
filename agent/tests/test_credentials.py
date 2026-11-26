import os

from agent import credentials


def test_fetch_can_be_limited_to_some_of_the_settings(monkeypatch):
    for name in ("OPENROUTER_API_KEY", "UNDERCOVER_API_KEY", "DATABASE_URL"):
        monkeypatch.setenv(f"AGENTCORE_CREDENTIAL_{name}_NAME", f"provider-{name}")
        monkeypatch.setenv(name, "")
    fetched = []

    def from_identity(provider):
        fetched.append(provider)
        return f"value-of-{provider}"

    monkeypatch.setattr(credentials, "from_identity", from_identity)

    credentials.fetch({"OPENROUTER_API_KEY", "DATABASE_URL"})

    assert sorted(fetched) == ["provider-DATABASE_URL", "provider-OPENROUTER_API_KEY"]
    assert os.environ["OPENROUTER_API_KEY"] == "value-of-provider-OPENROUTER_API_KEY"
    assert os.environ["UNDERCOVER_API_KEY"] == ""
