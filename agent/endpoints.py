"""Where the agent's services are: read when asked, never when this is imported.

The command line loads `.env` after its imports, so a value read at import would
miss it.
"""

import os

GATEWAY_URL = "UNDERCOVER_GATEWAY_URL"
CONTEXT_URL = "UNDERCOVER_CONTEXT"
MEMORY_ID = "UNDERCOVER_MEMORY_ID"
API_URL = "UNDERCOVER_API"
COPILOT_MEMORY_ID = "UNDERCOVER_COPILOT_MEMORY_ID"


def gateway_url() -> str | None:
    """Return the Gateway's address, or None to call the app and context directly."""
    return os.environ.get(GATEWAY_URL) or None


def context_url() -> str | None:
    """Return the context layer's address for the direct route, if one is set."""
    return os.environ.get(CONTEXT_URL) or None


def memory_id() -> str | None:
    """Return the id of the AgentCore Memory, or None when the agent has none."""
    return os.environ.get(MEMORY_ID) or None


def api_url() -> str | None:
    """Return the app's address, or None for the one on this laptop."""
    return os.environ.get(API_URL) or None


def copilot_memory_id() -> str | None:
    """Return the id of the Copilot's AgentCore Memory, or None when it has none."""
    return os.environ.get(COPILOT_MEMORY_ID) or None
