import socket
import threading
import time

from langchain_core.exceptions import ModelTimeoutError

from agent import harness


def trickling_server():
    """Return the port of a server that sends the headers, then a byte for ever."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()

    def trickle(conn):
        with conn:
            conn.recv(65536)
            conn.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                b"Transfer-Encoding: chunked\r\n\r\n"
            )
            try:
                while True:
                    conn.sendall(b"1\r\n \r\n")
                    time.sleep(0.1)
            except OSError:
                return  # the client hung up

    def accept():
        while True:
            conn, _ = listener.accept()
            threading.Thread(target=trickle, args=(conn,), daemon=True).start()

    threading.Thread(target=accept, daemon=True).start()
    return listener.getsockname()[1]


def test_a_model_call_that_trickles_bytes_still_ends_at_its_deadline(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "stub")
    monkeypatch.setattr(
        harness, "OPENROUTER_BASE_URL", f"http://127.0.0.1:{trickling_server()}/v1"
    )
    monkeypatch.setattr(harness, "MODEL_DEADLINE_SECONDS", 1)
    model = harness.model(harness.ModelSettings("openai/gpt-6-luna", "low"))
    errors = []

    def call():
        try:
            model.invoke("hi")
        except ModelTimeoutError as error:
            errors.append(error)

    caller = threading.Thread(target=call, daemon=True)
    caller.start()
    caller.join(timeout=15)

    assert len(errors) == 1
