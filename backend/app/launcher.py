import logging
import os
import signal
import socketserver
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


class _ShutdownHandler(socketserver.StreamRequestHandler):
    def handle(self):
        line = self.rfile.readline().decode(errors="replace").strip()
        if line == "shutdown":
            log.info("control: shutdown requested")
            self.server.shutdown_event.set()
        else:
            log.warning("control: ignoring unknown command %r", line)


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class ControlServer:
    def __init__(self, shutdown_event: threading.Event, port: int):
        self._event = shutdown_event
        self._requested_port = port
        self._server: _Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        assert self._server is not None, "server not started"
        return self._server.server_address[1]

    def start(self) -> None:
        self._server = _Server(("127.0.0.1", self._requested_port), _ShutdownHandler)
        self._server.shutdown_event = self._event
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)


_IS_WINDOWS = sys.platform == "win32"
_CREATION_FLAGS = subprocess.CREATE_NEW_PROCESS_GROUP if _IS_WINDOWS else 0


@dataclass
class ChildSpec:
    name: str
    argv: list[str]
    cwd: str | None


@dataclass
class Child:
    spec: ChildSpec
    process: subprocess.Popen
    escalated: bool = False


class Supervisor:
    def __init__(
        self,
        specs: list[ChildSpec],
        control_port: int,
        response_grace: float = 1.0,
    ):
        self._specs = specs
        self._control_port = control_port
        self._response_grace = response_grace
        self._shutdown_event = threading.Event()
        self._control = ControlServer(self._shutdown_event, port=control_port)
        self.children: list[Child] = []

    def start_children(self) -> None:
        self._control.start()
        for spec in self._specs:
            proc = subprocess.Popen(
                spec.argv,
                cwd=spec.cwd,
                creationflags=_CREATION_FLAGS,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                text=True,
            )
            self.children.append(Child(spec=spec, process=proc))
            log.info("started %s pid=%s", spec.name, proc.pid)

    def wait_for_shutdown(self, poll_interval: float = 0.5, max_wait: float | None = None) -> str:
        """Block until shutdown event is set OR a child dies. Returns the reason."""
        start = time.monotonic()
        while True:
            if self._shutdown_event.is_set():
                return "control-server: shutdown command"
            for child in self.children:
                if child.process.poll() is not None:
                    return f"unexpected child exit: {child.spec.name} (rc={child.process.returncode})"
            if max_wait is not None and time.monotonic() - start > max_wait:
                return "max_wait reached"
            time.sleep(poll_interval)

    def _send_break(self, child: Child) -> None:
        if child.process.poll() is not None:
            return
        try:
            if _IS_WINDOWS:
                child.process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                child.process.send_signal(signal.SIGINT)
        except OSError as exc:
            log.warning("%s: send_signal failed: %s", child.spec.name, exc)

    def shutdown_children(self, signal_timeout: float = 5.0, terminate_timeout: float = 2.0) -> None:
        time.sleep(self._response_grace)

        # Order: frontend first if present, then backend; otherwise insertion order
        ordered = sorted(
            self.children,
            key=lambda c: 0 if c.spec.name == "frontend" else 1 if c.spec.name == "backend" else 2,
        )

        for child in ordered:
            if child.process.poll() is not None:
                continue

            self._send_break(child)
            try:
                child.process.wait(timeout=signal_timeout)
                log.info("%s: exited cleanly (rc=%s)", child.spec.name, child.process.returncode)
                continue
            except subprocess.TimeoutExpired:
                log.warning("%s: timeout after CTRL_BREAK; terminating", child.spec.name)

            child.escalated = True
            try:
                child.process.terminate()
                child.process.wait(timeout=terminate_timeout)
            except subprocess.TimeoutExpired:
                log.error("%s: terminate timed out; killing", child.spec.name)
                child.process.kill()
                child.process.wait(timeout=2.0)

    def stop_control_server(self) -> None:
        self._control.stop()
