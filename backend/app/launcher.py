import logging
import os
import signal
import socketserver
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path

log = logging.getLogger(__name__)


def _open_browser_when_ready(
    repo_root: Path,
    url: str = "http://localhost:5173",
    backend_health_url: str = "http://localhost:8000/health",
    timeout: float = 60.0,
) -> None:
    def _reachable(probe_url: str) -> bool:
        try:
            urllib.request.urlopen(probe_url, timeout=1.0)
            return True
        except (urllib.error.URLError, OSError):
            return False

    def _wait_and_open():
        deadline = time.monotonic() + timeout
        backend_ready = False
        frontend_ready = False
        while time.monotonic() < deadline:
            if not backend_ready and _reachable(backend_health_url):
                backend_ready = True
            if not frontend_ready and _reachable(url):
                frontend_ready = True
            if backend_ready and frontend_ready:
                webbrowser.open(url)
                return
            time.sleep(0.5)
        log.warning(
            "ready check timed out after %.0fs (backend=%s, frontend=%s)",
            timeout, backend_ready, frontend_ready,
        )

    threading.Thread(target=_wait_and_open, daemon=True).start()


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


class LogStreamer:
    def __init__(self, name: str, stream, log_path: str):
        self._name = name
        self._stream = stream
        self._prefix = f"[{name.upper()}] "
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        self._handler = RotatingFileHandler(
            log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def join(self, timeout: float | None = None) -> None:
        self._thread.join(timeout=timeout)
        self._handler.close()

    def _run(self) -> None:
        try:
            for line in self._stream:
                line = line.rstrip("\r\n")
                print(self._prefix + line, flush=True)
                self._handler.emit(_make_record(self._name, line))
        except (ValueError, OSError):
            # stream closed during teardown
            pass


def _make_record(name: str, msg: str):
    record = logging.LogRecord(
        name=name, level=logging.INFO, pathname="", lineno=0,
        msg=msg, args=(), exc_info=None,
    )
    return record


def _build_specs(repo_root: Path) -> list[ChildSpec]:
    backend_dir = repo_root / "backend"
    frontend_dir = repo_root / "frontend"
    return [
        ChildSpec(
            name="backend",
            argv=["uvicorn", "app.main:app", "--reload"],
            cwd=str(backend_dir),
        ),
        ChildSpec(
            name="frontend",
            argv=["npm.cmd" if _IS_WINDOWS else "npm", "run", "dev"],
            cwd=str(frontend_dir),
        ),
    ]


def main(repo_root: Path | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="[LAUNCHER] %(message)s")

    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2]

    log_dir = repo_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    from app.config import settings
    port = settings.SUPERVISOR_PORT

    specs = _build_specs(repo_root)
    sup = Supervisor(specs, control_port=port, response_grace=1.0)
    sup.start_children()
    _open_browser_when_ready(repo_root)

    streamers: list[LogStreamer] = []
    for child in sup.children:
        log_path = log_dir / f"{child.spec.name}.log"
        streamer = LogStreamer(child.spec.name, child.process.stdout, str(log_path))
        streamer.start()
        streamers.append(streamer)

    if _IS_WINDOWS:
        signal.signal(signal.SIGBREAK, lambda *_: sup._shutdown_event.set())
    signal.signal(signal.SIGINT, lambda *_: sup._shutdown_event.set())

    log.info("supervisor running; control on 127.0.0.1:%s", port)
    reason = sup.wait_for_shutdown(poll_interval=0.5)
    log.info("shutting down: %s", reason)

    sup.shutdown_children(signal_timeout=5.0, terminate_timeout=2.0)
    sup.stop_control_server()

    for streamer in streamers:
        streamer.join(timeout=2.0)

    rc = 0 if "control-server" in reason else 1
    log.info("supervisor exit rc=%s", rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
