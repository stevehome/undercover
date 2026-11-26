from agent import backend_http, endpoints, routes
from agent.direct import DirectRoute
from agent.gateway import GatewayRoute


def test_nothing_is_set_by_default(monkeypatch):
    for name in (endpoints.GATEWAY_URL, endpoints.CONTEXT_URL, endpoints.MEMORY_ID):
        monkeypatch.delenv(name, raising=False)

    assert endpoints.gateway_url() is None
    assert endpoints.context_url() is None
    assert endpoints.memory_id() is None


def test_each_is_read_when_asked_not_when_imported(monkeypatch):
    monkeypatch.setenv(endpoints.GATEWAY_URL, "https://gateway.example/mcp")
    monkeypatch.setenv(endpoints.CONTEXT_URL, "https://context.example/mcp")
    monkeypatch.setenv(endpoints.MEMORY_ID, "memory-1")

    assert endpoints.gateway_url() == "https://gateway.example/mcp"
    assert endpoints.context_url() == "https://context.example/mcp"
    assert endpoints.memory_id() == "memory-1"


def test_the_route_is_the_gateways_only_when_its_address_is_set(monkeypatch):
    monkeypatch.delenv(endpoints.GATEWAY_URL, raising=False)
    assert isinstance(routes.choose(), DirectRoute)

    monkeypatch.setenv(endpoints.GATEWAY_URL, "https://gateway.example/mcp")
    assert isinstance(routes.choose(), GatewayRoute)


def test_the_apps_address_is_read_when_the_client_is_first_used(monkeypatch):
    monkeypatch.setattr(backend_http, "client", None)
    monkeypatch.setenv(endpoints.API_URL, "https://app.example")

    made = backend_http._client()  # noqa: SLF001 - the client made on first use

    assert str(made.base_url) == "https://app.example"
    assert backend_http._client() is made  # noqa: SLF001


def test_the_apps_address_is_this_laptop_when_none_is_set(monkeypatch):
    monkeypatch.setattr(backend_http, "client", None)
    monkeypatch.delenv(endpoints.API_URL, raising=False)

    assert endpoints.api_url() is None
    assert str(backend_http._client().base_url) == "http://localhost:8000"  # noqa: SLF001


def test_the_copilots_memory_is_read_when_asked(monkeypatch):
    monkeypatch.delenv(endpoints.COPILOT_MEMORY_ID, raising=False)
    assert endpoints.copilot_memory_id() is None

    monkeypatch.setenv(endpoints.COPILOT_MEMORY_ID, "copilot-memory-1")

    assert endpoints.copilot_memory_id() == "copilot-memory-1"
