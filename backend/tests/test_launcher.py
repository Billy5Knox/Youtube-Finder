import socket
import threading
import time

from app.launcher import ControlServer


def _send(port: int, payload: bytes) -> None:
    with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
        sock.sendall(payload)


def test_control_server_triggers_shutdown_event():
    event = threading.Event()
    server = ControlServer(event, port=0)
    server.start()
    try:
        _send(server.port, b"shutdown\n")
        assert event.wait(timeout=2.0) is True
    finally:
        server.stop()


def test_control_server_rejects_unknown_commands():
    event = threading.Event()
    server = ControlServer(event, port=0)
    server.start()
    try:
        _send(server.port, b"rm -rf /\n")
        # give server time to process
        time.sleep(0.2)
        assert event.is_set() is False
    finally:
        server.stop()
