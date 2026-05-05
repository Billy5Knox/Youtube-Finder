# Graceful App Shutdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Logoff button that gracefully shuts down both the backend (uvicorn) and frontend (vite) servers and their console windows, replacing the dual `cmd /k` launcher with a Python supervisor.

**Architecture:** A new `backend/app/launcher.py` module owns both children as subprocesses started with `CREATE_NEW_PROCESS_GROUP`, listens on `127.0.0.1:8765` for a "shutdown" command, and on receipt sends `CTRL_BREAK_EVENT` to each child group with timeout escalation. The browser triggers shutdown via a new `POST /auth/shutdown` endpoint that fires a fire-and-forget signal to the supervisor and returns 200 so the React app can switch to a `StoppedView`.

**Tech Stack:** Python 3.13 + FastAPI + uvicorn (backend), React + Vite (frontend), `subprocess` + `socketserver` + `threading` (supervisor), Windows `CTRL_BREAK_EVENT`.

---

## File Structure

**Create:**
- `launcher.py` — repo-root entry shim that boots `app.launcher.main`
- `backend/app/launcher.py` — `Supervisor`, `ControlServer`, `LogStreamer`, `main()`
- `backend/app/shutdown.py` — `request_supervisor_shutdown()` client
- `backend/pytest.ini` — sets pythonpath so tests can import from `app.*`
- `backend/tests/test_shutdown.py` — client + endpoint tests
- `backend/tests/test_launcher.py` — supervisor + control-server tests
- `backend/tests/test_launcher_integration.py` — slow integration smoke
- `frontend/src/components/StoppedView.jsx` — "App stopped" view
- `logs/.gitkeep` — keep `logs/` directory tracked

**Modify:**
- `backend/app/config.py` — add `SUPERVISOR_PORT`
- `backend/app/auth.py` — add `POST /auth/shutdown` endpoint
- `start.bat` — replace cmd /k spawns with `python launcher.py`
- `frontend/src/api.js` — add `shutdownApp()`
- `frontend/src/App.jsx` — track `stopped` state, render `StoppedView`
- `frontend/src/components/TopBar.jsx` — replace Logout link with Logoff button
- `.gitignore` — add `logs/*.log`

---

## Task 1: Pytest config + supervisor port setting

**Files:**
- Create: `backend/pytest.ini`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add pytest.ini so tests run from `backend/` cleanly**

Create `backend/pytest.ini`:

```ini
[pytest]
markers =
    slow: opt-in slower integration tests
testpaths = tests
```

- [ ] **Step 2: Add `SUPERVISOR_PORT` to settings**

Edit `backend/app/config.py`. After the existing `FRONTEND_URL` line in the `Settings` class, add:

```python
    SUPERVISOR_PORT: int = int(os.environ.get("SUPERVISOR_PORT", "8765"))
```

- [ ] **Step 3: Verify existing tests still pass**

Run from `backend/`:
```
python -m pytest tests/ -v
```
Expected: 19 passed (same as before).

- [ ] **Step 4: Commit**

```bash
git add backend/pytest.ini backend/app/config.py
git commit -m "feat: add SUPERVISOR_PORT setting and pytest config"
```

---

## Task 2: Supervisor control-socket client

**Files:**
- Create: `backend/app/shutdown.py`
- Create: `backend/tests/test_shutdown.py`

- [ ] **Step 1: Write failing tests for the client**

Create `backend/tests/test_shutdown.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_shutdown.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'app.shutdown'`.

- [ ] **Step 3: Implement the client**

Create `backend/app/shutdown.py`:

```python
import logging
import socket

from app.config import settings

log = logging.getLogger(__name__)


def _supervisor_port() -> int:
    return settings.SUPERVISOR_PORT


def request_supervisor_shutdown() -> None:
    port = _supervisor_port()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2.0) as sock:
            sock.sendall(b"shutdown\n")
    except (ConnectionRefusedError, OSError) as exc:
        log.warning("supervisor not running on port %s, skipping (%s)", port, exc)
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_shutdown.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/shutdown.py backend/tests/test_shutdown.py
git commit -m "feat: add supervisor control-socket client"
```

---

## Task 3: `POST /auth/shutdown` endpoint

**Files:**
- Modify: `backend/app/auth.py`
- Modify: `backend/tests/test_shutdown.py` (add endpoint tests)

- [ ] **Step 1: Add failing endpoint tests**

Append to `backend/tests/test_shutdown.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_shutdown.py -v
```
Expected: 2 new tests FAIL — first with 404 (no endpoint), second similarly.

- [ ] **Step 3: Implement the endpoint**

Edit `backend/app/auth.py`. Add to the imports near the top:

```python
from app.shutdown import request_supervisor_shutdown
```

At the bottom of the file, before any final blank line, add:

```python
@router.post("/shutdown")
def shutdown(request: Request, response: Response):
    user_id = require_user(request)
    session_id = request.cookies.get("session_id")
    if session_id:
        _sessions.pop(session_id, None)
    response.delete_cookie("session_id")
    request_supervisor_shutdown()
    return {"status": "shutting_down"}
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_shutdown.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Run the full backend suite to confirm no regressions**

```
python -m pytest tests/ -v
```
Expected: all passed (19 prior + 4 new = 23).

- [ ] **Step 6: Commit**

```bash
git add backend/app/auth.py backend/tests/test_shutdown.py
git commit -m "feat: add POST /auth/shutdown endpoint"
```

---

## Task 4: Launcher `ControlServer`

**Files:**
- Create: `backend/app/launcher.py` (initial stub with `ControlServer` only)
- Create: `backend/tests/test_launcher.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_launcher.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_launcher.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'app.launcher'`.

- [ ] **Step 3: Implement `ControlServer`**

Create `backend/app/launcher.py`:

```python
import logging
import socketserver
import threading

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
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_launcher.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/launcher.py backend/tests/test_launcher.py
git commit -m "feat: add launcher ControlServer"
```

---

## Task 5: `Supervisor.shutdown()` graceful escalation

**Files:**
- Modify: `backend/app/launcher.py`
- Modify: `backend/tests/test_launcher.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_launcher.py`:

```python
import subprocess
import sys

from app.launcher import Supervisor, ChildSpec


_SLEEP_CMD = [sys.executable, "-c", "import time; time.sleep(60)"]
_IGNORE_BREAK_CMD = [
    sys.executable,
    "-c",
    "import signal, time; "
    "signal.signal(signal.SIGBREAK, lambda *a: None); "
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
python -m pytest tests/test_launcher.py -v
```
Expected: 3 new tests FAIL with `ImportError` (Supervisor / ChildSpec missing).

- [ ] **Step 3: Implement `ChildSpec`, `Child`, and `Supervisor`**

Edit `backend/app/launcher.py`. After the existing `ControlServer` class, add:

```python
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

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
```

- [ ] **Step 4: Run tests to verify they pass**

```
python -m pytest tests/test_launcher.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/launcher.py backend/tests/test_launcher.py
git commit -m "feat: add Supervisor with graceful shutdown escalation"
```

---

## Task 6: `LogStreamer` — prefix + tee

**Files:**
- Modify: `backend/app/launcher.py`
- Modify: `backend/tests/test_launcher.py`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_launcher.py`:

```python
import io
from logging.handlers import RotatingFileHandler

from app.launcher import LogStreamer


def test_log_streamer_prefixes_and_writes_file(tmp_path, capsys):
    proc = subprocess.Popen(
        [sys.executable, "-c", "print('hello'); print('world')"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        text=True,
    )
    log_file = tmp_path / "child.log"
    streamer = LogStreamer(name="backend", stream=proc.stdout, log_path=str(log_file))
    streamer.start()
    proc.wait(timeout=5.0)
    streamer.join(timeout=2.0)

    captured = capsys.readouterr().out
    assert "[BACKEND] hello" in captured
    assert "[BACKEND] world" in captured

    contents = log_file.read_text()
    assert "hello" in contents
    assert "world" in contents
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_launcher.py::test_log_streamer_prefixes_and_writes_file -v
```
Expected: FAIL with `ImportError: cannot import name 'LogStreamer'`.

- [ ] **Step 3: Implement `LogStreamer`**

Edit `backend/app/launcher.py`. Add after the imports block (`Path` is already imported):

```python
from logging.handlers import RotatingFileHandler


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
```

- [ ] **Step 4: Run test to verify it passes**

```
python -m pytest tests/test_launcher.py::test_log_streamer_prefixes_and_writes_file -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/launcher.py backend/tests/test_launcher.py
git commit -m "feat: add LogStreamer for prefixed console + rotating file output"
```

---

## Task 7: `main()` wiring + repo-root entry shim

**Files:**
- Modify: `backend/app/launcher.py`
- Create: `launcher.py` (repo root)
- Create: `logs/.gitkeep`
- Modify: `.gitignore`

- [ ] **Step 1: Add `main()` entry point**

Edit `backend/app/launcher.py`. At the bottom, add:

```python
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
```

- [ ] **Step 2: Create the repo-root entry shim**

Create `launcher.py` at the repo root:

```python
"""Repo-root entry point for the YouTube Finder supervisor.

Adds backend/ to sys.path so we can `import app.launcher` cleanly,
then delegates to its main().
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.launcher import main

if __name__ == "__main__":
    sys.exit(main(REPO_ROOT))
```

- [ ] **Step 3: Track logs directory**

Create `logs/.gitkeep` (empty file):

```bash
mkdir -p logs && touch logs/.gitkeep
```

Edit `.gitignore`. Append:

```
logs/*.log
logs/*.log.*
```

- [ ] **Step 4: Verify backend tests still pass**

```
python -m pytest tests/ -v
```
Expected: all passed.

- [ ] **Step 5: Manual smoke (optional but recommended)**

From the repo root, run:
```
python launcher.py
```

You should see prefixed `[BACKEND]` and `[FRONTEND]` log lines in the same console. Hit `Ctrl+Break` (Windows) or `Ctrl+C`. Both children should exit cleanly within a few seconds.

- [ ] **Step 6: Commit**

```bash
git add backend/app/launcher.py launcher.py logs/.gitkeep .gitignore
git commit -m "feat: wire launcher main() and repo-root entry shim"
```

---

## Task 8: Integration smoke test

**Files:**
- Create: `backend/tests/test_launcher_integration.py`

- [ ] **Step 1: Write the slow integration test**

Create `backend/tests/test_launcher_integration.py`:

```python
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _wait_for_port(port: int, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


@pytest.mark.slow
def test_full_shutdown_flow(tmp_path):
    """Spawn the real launcher with stub child commands; send shutdown; assert clean exit."""
    # Launch a stripped-down version: monkey-patch _build_specs via env-driven hook
    env = os.environ.copy()
    env["SUPERVISOR_PORT"] = "0"  # not honored by real main(); see comment below
    # NOTE: This integration test exercises the launcher via a small driver script
    # so we don't need the real backend/frontend to be runnable here.
    driver = tmp_path / "driver.py"
    driver.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        f"sys.path.insert(0, {repr(str(REPO_ROOT / 'backend'))})\n"
        "from app.launcher import Supervisor, ChildSpec, LogStreamer\n"
        "import logging, signal, sys\n"
        "logging.basicConfig(level=logging.INFO)\n"
        "specs = [\n"
        "    ChildSpec(name='frontend', argv=[sys.executable, '-c', 'import time; time.sleep(60)'], cwd=None),\n"
        "    ChildSpec(name='backend',  argv=[sys.executable, '-c', 'import time; time.sleep(60)'], cwd=None),\n"
        "]\n"
        "sup = Supervisor(specs, control_port=8765, response_grace=0.2)\n"
        "sup.start_children()\n"
        "reason = sup.wait_for_shutdown(poll_interval=0.2)\n"
        "sup.shutdown_children(signal_timeout=3.0, terminate_timeout=2.0)\n"
        "sup.stop_control_server()\n"
        "sys.exit(0 if 'control-server' in reason else 1)\n"
    )

    proc = subprocess.Popen(
        [sys.executable, str(driver)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        assert _wait_for_port(8765, timeout=10.0), "supervisor never bound control port"
        with socket.create_connection(("127.0.0.1", 8765), timeout=2.0) as sock:
            sock.sendall(b"shutdown\n")
        rc = proc.wait(timeout=15.0)
        assert rc == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2.0)
```

- [ ] **Step 2: Run the slow test**

```
python -m pytest tests/test_launcher_integration.py -v -m slow
```
Expected: 1 passed (~5–8s runtime).

- [ ] **Step 3: Confirm default run still excludes it**

```
python -m pytest tests/ -v
```
Expected: slow test is collected but deselected (pytest.ini has the marker registered; default run excludes it via `-m "not slow"`).

If the default run picks it up, edit `backend/pytest.ini` to add:
```
addopts = -m "not slow"
```

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_launcher_integration.py backend/pytest.ini
git commit -m "test: add launcher full-shutdown integration smoke"
```

---

## Task 9: Update `start.bat`

**Files:**
- Modify: `start.bat`

- [ ] **Step 1: Replace with a one-liner that runs the supervisor**

Replace the entire contents of `start.bat` with:

```bat
@echo off
title YouTube Finder
cd /d "%~dp0"
python launcher.py
```

The supervisor itself handles the "wait for backend ready" / "open browser" steps in the next sub-step.

- [ ] **Step 2: Add browser-open step to the supervisor**

Edit `backend/app/launcher.py`. In `main()`, after `sup.start_children()` and before `signal.signal(...)`, add:

```python
    _open_browser_when_ready(repo_root)
```

Add this helper near the top of the module (after imports):

```python
import urllib.request
import webbrowser


def _open_browser_when_ready(repo_root: Path, url: str = "http://localhost:5173", timeout: float = 30.0) -> None:
    def _wait_and_open():
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                urllib.request.urlopen(url, timeout=1.0)
                webbrowser.open(url)
                return
            except (urllib.error.URLError, OSError):
                time.sleep(0.5)
        log.warning("frontend never became reachable at %s within %.0fs", url, timeout)

    threading.Thread(target=_wait_and_open, daemon=True).start()
```

- [ ] **Step 3: Manual verification**

Double-click `start.bat` (or run it from a terminal). Expected:
- One supervisor console window opens
- `[BACKEND]` and `[FRONTEND]` log lines appear interleaved
- After ~5–10s, the browser opens to `http://localhost:5173`
- Press `Ctrl+Break` in the supervisor window: both children exit cleanly within ~6s, supervisor exits, window closes

- [ ] **Step 4: Commit**

```bash
git add start.bat backend/app/launcher.py
git commit -m "feat: replace dual cmd /k launcher with single supervisor"
```

---

## Task 10: Frontend `shutdownApp()` API call

**Files:**
- Modify: `frontend/src/api.js`

- [ ] **Step 1: Add the API call**

Edit `frontend/src/api.js`. Append:

```javascript
export async function shutdownApp() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 3000);
  try {
    const res = await fetch(`${API_BASE}/auth/shutdown`, {
      method: "POST",
      credentials: "include",
      signal: controller.signal,
    });
    return res.ok;
  } catch (err) {
    // Either the server died mid-flight or we timed out; treat as success
    // since the user's intent (stop the app) has been delivered.
    console.warn("shutdownApp: ignoring error", err);
    return false;
  } finally {
    clearTimeout(timer);
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat: add shutdownApp client call with 3s timeout"
```

---

## Task 11: Frontend `StoppedView` component

**Files:**
- Create: `frontend/src/components/StoppedView.jsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/StoppedView.jsx`:

```jsx
function StoppedView() {
  return (
    <div className="stopped-view">
      <h1>YouTube Finder has stopped</h1>
      <p>You can safely close this tab.</p>
      <p className="hint">Run <code>start.bat</code> to launch it again.</p>
    </div>
  );
}

export default StoppedView;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/StoppedView.jsx
git commit -m "feat: add StoppedView component"
```

---

## Task 12: TopBar — replace Logout link with Logoff button

**Files:**
- Modify: `frontend/src/components/TopBar.jsx`

- [ ] **Step 1: Replace the existing Logout anchor with a Logoff button**

Edit `frontend/src/components/TopBar.jsx`. Replace the entire file contents with:

```jsx
// frontend/src/components/TopBar.jsx
import { useState } from "react";
import { triggerSync, shutdownApp } from "../api";

function TopBar({ user, onStopped }) {
  const [syncing, setSyncing] = useState(false);
  const [lastSync, setLastSync] = useState(user.last_sync_at);
  const [loggingOff, setLoggingOff] = useState(false);

  async function handleSync() {
    setSyncing(true);
    try {
      const result = await triggerSync();
      setLastSync(result.last_sync_at);
    } catch (err) {
      console.error("Sync failed:", err);
    } finally {
      setSyncing(false);
    }
  }

  async function handleLogoff() {
    setLoggingOff(true);
    await shutdownApp();
    onStopped();
  }

  function formatSyncTime(isoString) {
    if (!isoString) return "Never";
    return new Date(isoString).toLocaleString();
  }

  return (
    <header className="top-bar">
      <div className="top-bar-left">
        <h1 className="logo">YouTube Finder</h1>
      </div>
      <div className="top-bar-right">
        <span className="sync-status">
          Last synced: {formatSyncTime(lastSync)}
        </span>
        <button
          className="sync-button"
          onClick={handleSync}
          disabled={syncing || loggingOff}
        >
          {syncing ? "Syncing..." : "Sync Now"}
        </button>
        <div className="user-info">
          {user.picture && (
            <img src={user.picture} alt="" className="avatar" />
          )}
          <span className="user-name">{user.name}</span>
        </div>
        <button
          className="logoff-button"
          onClick={handleLogoff}
          disabled={loggingOff}
        >
          {loggingOff ? "Stopping..." : "Logoff"}
        </button>
      </div>
    </header>
  );
}

export default TopBar;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/TopBar.jsx
git commit -m "feat: replace Logout link with Logoff button"
```

---

## Task 13: `App.jsx` — `stopped` state + render `StoppedView`

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Wire `stopped` state and render gating**

Edit `frontend/src/App.jsx`. Replace the entire file contents with:

```jsx
// frontend/src/App.jsx
import { useState, useEffect } from "react";
import { fetchCurrentUser } from "./api";
import TopBar from "./components/TopBar";
import SearchBar from "./components/SearchBar";
import ResultsGrid from "./components/ResultsGrid";
import PlaylistFilter from "./components/PlaylistFilter";
import StoppedView from "./components/StoppedView";
import "./App.css";

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [results, setResults] = useState([]);
  const [query, setQuery] = useState("");
  const [selectedPlaylist, setSelectedPlaylist] = useState(null);
  const [stopped, setStopped] = useState(false);

  useEffect(() => {
    fetchCurrentUser()
      .then(setUser)
      .finally(() => setLoading(false));
  }, []);

  if (stopped) {
    return <StoppedView />;
  }

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  if (!user) {
    return (
      <div className="login-page">
        <h1>YouTube Finder</h1>
        <p>Search across all your YouTube playlists.</p>
        <a href="/auth/login" className="login-button">
          Sign in with Google
        </a>
      </div>
    );
  }

  return (
    <div className="app">
      <TopBar user={user} onStopped={() => setStopped(true)} />
      <main className="main-content">
        <SearchBar
          query={query}
          setQuery={setQuery}
          setResults={setResults}
          selectedPlaylist={selectedPlaylist}
        />
        <PlaylistFilter
          selectedPlaylist={selectedPlaylist}
          setSelectedPlaylist={setSelectedPlaylist}
        />
        <ResultsGrid
          results={results}
          query={query}
          selectedPlaylist={selectedPlaylist}
        />
      </main>
    </div>
  );
}

export default App;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: switch to StoppedView after Logoff"
```

---

## Task 14: Manual end-to-end checklist

This task is a verification gate — no code changes. Run each step against a real launch.

- [ ] **Step 1: Happy path**

1. Run `start.bat` from the repo root.
2. Wait for the browser to open at `http://localhost:5173`.
3. Sign in if needed.
4. Click **Logoff**.
5. Expected: button switches to "Stopping...", page switches to the "YouTube Finder has stopped" view within ~3s, supervisor console exits within ~6s.

- [ ] **Step 2: Logoff with no supervisor running**

1. From `backend/`, run `uvicorn app.main:app --reload` directly.
2. From `frontend/`, run `npm run dev`.
3. Sign in, click **Logoff**.
4. Expected: page switches to `StoppedView`. The backend console logs `supervisor not running on port 8765, skipping`. The two manually-started processes are still running (we did not kill them).

- [ ] **Step 3: Logoff during an in-flight search**

1. Run `start.bat`.
2. Sign in, type a query that triggers a search, and immediately click **Logoff** while results are loading.
3. Expected: search response either completes before or right at the moment of shutdown; the UI lands on `StoppedView` regardless. No browser-side stack traces beyond the warning from `shutdownApp`.

- [ ] **Step 4: Stubborn child handling (synthetic check)**

This was already covered by `test_supervisor_escalates_to_terminate_on_timeout`, but to verify on real runs: temporarily edit `backend/app/main.py` to register a long-running shutdown handler (e.g., `time.sleep(20)` in a FastAPI lifespan shutdown hook), launch via `start.bat`, click Logoff. Expected: supervisor escalates to `terminate()` after the 5s grace and exits anyway. Revert the hack after verification.

- [ ] **Step 5: Document anything that misbehaved**

If any step fails, file an issue (or note in the project diary) with the supervisor's `logs/backend.log` and `logs/frontend.log` attached. Do NOT mark this task complete on the basis of partial success.

---

## Self-Review Notes

- **Spec coverage:** All sections in the design doc are mapped — Architecture (Tasks 4–7), Components (Tasks 1–7, 9–13), Shutdown sequence (Task 5), Error/edge cases (Tasks 2–3, 5, 10), Testing (Tasks 2–8 cover unit + integration; Task 14 covers manual checklist). Out-of-scope items (auto-relaunch, cross-platform, Vitest, control encryption) are explicitly not in the plan.
- **Placeholder scan:** No "TBD"/"TODO"/"add appropriate X" entries. Every code step has full code.
- **Type consistency:** `Supervisor` API used in tests (Task 5 → 8) and `main()` (Task 7) is consistent: `start_children()`, `wait_for_shutdown()`, `shutdown_children(signal_timeout=, terminate_timeout=)`, `stop_control_server()`, `children: list[Child]`. `ControlServer.start()/stop()/.port` consistent across Tasks 4 and 5/7. `LogStreamer.__init__(name, stream, log_path)` matches Task 6 test and Task 7 wiring.
