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


import subprocess
import sys

from app.launcher import Supervisor, ChildSpec


_SLEEP_CMD = [sys.executable, "-c", "import time; time.sleep(60)"]
_IGNORE_BREAK_CMD = [
    sys.executable,
    "-c",
    "import ctypes, time; "
    "HANDLER = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong); "
    "h = HANDLER(lambda sig: True); "
    "ctypes.windll.kernel32.SetConsoleCtrlHandler(h, True); "
    "time.sleep(0.1); "
    "time.sleep(60)",
]


def _make_supervisor(specs):
    sup = Supervisor(specs, control_port=0, response_grace=0.0)
    return sup


def test_supervisor_signals_children_to_exit():
    specs = [
        ChildSpec(name="frontend", argv=_SLEEP_CMD, cwd=None),
        ChildSpec(name="backend", argv=_SLEEP_CMD, cwd=None),
    ]
    sup = _make_supervisor(specs)
    sup.start_children()
    try:
        sup.shutdown_children(signal_timeout=3.0, terminate_timeout=2.0)
        for child in sup.children:
            assert child.process.poll() is not None
    finally:
        sup.stop_control_server()


def test_supervisor_escalates_to_terminate_on_timeout():
    specs = [ChildSpec(name="stubborn", argv=_IGNORE_BREAK_CMD, cwd=None)]
    sup = _make_supervisor(specs)
    sup.start_children()
    # Give the child time to start and register its console-ctrl handler
    # before we send CTRL_BREAK_EVENT; without this the process may not
    # have reached Python code yet and the default handler kills it.
    time.sleep(0.5)
    try:
        sup.shutdown_children(signal_timeout=1.0, terminate_timeout=2.0)
        assert sup.children[0].process.poll() is not None
        assert sup.children[0].escalated is True
    finally:
        sup.stop_control_server()


def test_supervisor_detects_unexpected_child_death():
    specs = [
        ChildSpec(name="quick", argv=[sys.executable, "-c", "import sys; sys.exit(0)"], cwd=None),
        ChildSpec(name="long", argv=_SLEEP_CMD, cwd=None),
    ]
    sup = _make_supervisor(specs)
    sup.start_children()
    try:
        reason = sup.wait_for_shutdown(poll_interval=0.1, max_wait=5.0)
        assert "child exit" in reason.lower()
        sup.shutdown_children(signal_timeout=2.0, terminate_timeout=2.0)
        for child in sup.children:
            assert child.process.poll() is not None
    finally:
        sup.stop_control_server()
