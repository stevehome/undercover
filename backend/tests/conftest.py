import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from backend import db
from backend.main import app


@pytest.fixture
def client(tmp_path, monkeypatch, as_handler):
    """A TestClient against a fresh, temporary claim database, signed in as Dana."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    return TestClient(app, headers=as_handler())


@pytest.fixture
def statements_to_get(client):
    """A function that counts the SQL statements one GET runs."""

    def count(path):
        seen = []

        def record(*_):
            seen.append(1)

        engine = db.engine(db.database_url())
        event.listen(engine, "before_cursor_execute", record)
        try:
            client.get(path)
        finally:
            event.remove(engine, "before_cursor_execute", record)
        return len(seen)

    return count


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
            else (202, {"run_id": 5, "round_id": 5, "proposal_id": 5})
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
