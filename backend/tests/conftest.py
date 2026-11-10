import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient against a fresh, temporary claim database."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    return TestClient(app)


class AgentStub(BaseHTTPRequestHandler):
    """A stand-in for the agent's service that records the paths it is asked for."""

    calls: list[str] = []
    bodies: list[dict] = []
    refuse = False

    def do_POST(self):
        self.calls.append(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        self.bodies.append(json.loads(self.rfile.read(length) or "{}"))
        status, body = (
            (409, {"detail": "A run is already going"})
            if self.refuse
            else (202, {"run_id": 5})
        )
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, format, *args):
        pass


@pytest.fixture
def agent_stub(monkeypatch):
    """Point the backend at a stand-in agent service."""
    handler = type("Stub", (AgentStub,), {"calls": [], "bodies": [], "refuse": False})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("UNDERCOVER_AGENT", f"http://127.0.0.1:{server.server_port}")
    yield handler
    server.shutdown()
