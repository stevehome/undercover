import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from backend import db
from backend.main import app
from conftest import API_KEY


@pytest.fixture(autouse=True)
def one_connection_at_a_time(monkeypatch):
    """Fail any code that opens a connection while it holds one.

    On Lambda the engine keeps one connection, so a nested one would wait for the
    pool to time out; the laptop's pool of four would hide it.
    """
    held = threading.local()
    opened = db.connection

    @contextmanager
    def guarded():
        assert not getattr(held, "open", False), "a connection opened inside another"
        held.open = True
        try:
            with opened() as conn:
                yield conn
        finally:
            held.open = False

    monkeypatch.setattr(db, "connection", guarded)


@pytest.fixture
def client(tmp_path, monkeypatch, as_handler):
    """A TestClient against a fresh, temporary claim database, with the key and Dana."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    return TestClient(app, headers={**as_handler(), "X-API-Key": API_KEY})


@pytest.fixture
def anonymous(tmp_path, monkeypatch):
    """A client with no key and no sign-in, on the test's own database."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    return TestClient(app)


@pytest.fixture
def agent(tmp_path, monkeypatch):
    """A client holding only the agent's API key, on the test's own database."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    return TestClient(app, headers={"X-API-Key": API_KEY})


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
    """A stand-in for the agent's AgentCore app: it records each operation asked for."""

    calls: list[str] = []
    bodies: list[dict] = []
    keys: list[str | None] = []
    refuse = False

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length) or "{}")
        self.keys.append(self.headers.get("Authorization"))
        self.calls.append(payload.pop("operation"))
        self.bodies.append(payload)
        body = (
            {"refused": "A run is already going"}
            if self.refuse
            else {"accepted": True, "run_id": 5, "round_id": 5, "proposal_id": 5}
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, format, *args):
        pass


@pytest.fixture
def agent_stub(monkeypatch):
    """Point the backend at a stand-in agent service."""
    handler = type(
        "Stub",
        (AgentStub,),
        {"calls": [], "bodies": [], "keys": [], "refuse": False},
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("UNDERCOVER_AGENT", f"http://127.0.0.1:{server.server_port}")
    yield handler
    server.shutdown()
