import socket
import threading
import socketserver

from app import shutdown as shutdown_module


class _RecordingHandler(socketserver.StreamRequestHandler):
    def handle(self):
        line = self.rfile.readline().decode().strip()
        self.server.received.append(line)


def _start_recording_server():
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _RecordingHandler)
    server.received = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_request_supervisor_shutdown_sends_command(monkeypatch):
    server = _start_recording_server()
    port = server.server_address[1]
    monkeypatch.setattr(shutdown_module, "_supervisor_port", lambda: port)

    shutdown_module.request_supervisor_shutdown()

    # give the handler a beat to flush
    for _ in range(50):
        if server.received:
            break
        threading.Event().wait(0.02)

    assert server.received == ["shutdown"]
    server.shutdown()


def test_request_supervisor_shutdown_handles_no_supervisor(monkeypatch, caplog):
    # Pick a port that's almost certainly not bound
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    closed_port = s.getsockname()[1]
    s.close()

    monkeypatch.setattr(shutdown_module, "_supervisor_port", lambda: closed_port)

    # Should not raise
    shutdown_module.request_supervisor_shutdown()

    assert any("supervisor not running" in rec.message.lower() for rec in caplog.records)


from fastapi.testclient import TestClient

from app.main import app
from app import auth as auth_module


def test_shutdown_endpoint_requires_auth():
    client = TestClient(app)
    res = client.post("/auth/shutdown")
    assert res.status_code == 401


def test_shutdown_endpoint_clears_session_and_calls_supervisor(monkeypatch):
    called = []
    monkeypatch.setattr(
        "app.auth.request_supervisor_shutdown",
        lambda: called.append(True),
    )

    auth_module._sessions["test-session"] = "test-user-id"

    client = TestClient(app)
    res = client.post(
        "/auth/shutdown",
        cookies={"session_id": "test-session"},
    )

    assert res.status_code == 200
    assert res.json() == {"status": "shutting_down"}
    assert called == [True]
    assert "test-session" not in auth_module._sessions
