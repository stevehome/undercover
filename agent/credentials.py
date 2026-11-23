"""The agent's credentials on Runtime: fetched from AgentCore Identity.

The deployment gives the agent a setting `AGENTCORE_CREDENTIAL_<NAME>_NAME` for each
credential, naming its provider in Identity. The value goes into the setting `<NAME>`,
where `.env` puts it on a laptop. This is the one module that imports
`bedrock_agentcore.identity`.
"""

import os

from bedrock_agentcore.identity.auth import requires_api_key

PREFIX = "AGENTCORE_CREDENTIAL_"
SUFFIX = "_NAME"


def providers() -> dict[str, str]:
    """The settings to fill, each with the provider in Identity that holds its value."""
    return {
        name.removeprefix(PREFIX).removesuffix(SUFFIX): provider
        for name, provider in os.environ.items()
        if name.startswith(PREFIX) and name.endswith(SUFFIX)
    }


def on_runtime() -> bool:
    """Whether the agent is on Runtime, which is where the credentials' settings are."""
    return bool(providers())


def from_identity(provider: str) -> str:
    """Fetch one credential's value from Identity, for the request being handled."""

    @requires_api_key(provider_name=provider)
    def value(*, api_key: str = "") -> str:
        return api_key

    return value()


def fetch() -> None:
    """Put each credential's value from Identity into its setting."""
    for setting, provider in providers().items():
        os.environ[setting] = from_identity(provider)
