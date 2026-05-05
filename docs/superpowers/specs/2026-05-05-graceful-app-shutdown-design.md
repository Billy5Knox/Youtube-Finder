# Graceful App Shutdown via Logoff Button

## Goal

Add a "Logoff" button to YouTube Finder that stops the running app cleanly: clears the user session, shuts down both the backend (uvicorn) and frontend (vite) servers gracefully, closes their console windows, and leaves the browser on a "App stopped, safe to close" view.

The current launcher (`start.bat`) spawns two `cmd /k` windows that the user must close manually. This design replaces it with a single Python supervisor that owns the children's lifecycle and can shut them down via real OS signals.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              launcher.py (supervisor process)           │
│                                                          │
│   • Spawns and owns both children                       │
│   • Streams their stdout/stderr to its console &        │
│     log files, prefixed [BACKEND] / [FRONTEND]          │
│   • Listens on 127.0.0.1:8765 for a "shutdown" command  │
│   • On shutdown: graceful → wait → escalate → exit      │
│                                                          │
│   ├──► child A: uvicorn (CREATE_NEW_PROCESS_GROUP)      │
│   │              port 8000                              │
│   │                                                      │
│   └──► child B: npm run dev → node → vite               │
│                  (CREATE_NEW_PROCESS_GROUP)             │
│                  port 5173                              │
└─────────────────────────────────────────────────────────┘
```

Click flow:

```
Browser ──POST /auth/shutdown──► Backend
Backend ──clear session──► (DB)
Backend ──"shutdown"──► Supervisor (TCP 127.0.0.1:8765, fire-and-forget)
Backend ──200 OK──► Browser
Browser ──switches to "App stopped" client-side view──

Supervisor (after ~1s grace):
  1. CTRL_BREAK_EVENT → frontend group  → vite exits
  2. CTRL_BREAK_EVENT → backend group   → uvicorn lifespan shutdown
  3. wait up to 5s each, escalate to terminate() if needed
  4. supervisor exits, its console window closes
```

### Why these choices

- **`CREATE_NEW_PROCESS_GROUP`** is the only way to deliver a true SIGINT-equivalent (`CTRL_BREAK_EVENT`) to a Windows child. uvicorn and vite both handle it cleanly.
- **Loopback TCP control** beats sentinel files (no polling, no race) and named pipes (Windows-only, finickier). Bound to 127.0.0.1, so nothing off-host can reach it.
- **Fire-and-forget from backend → supervisor**, then the 1s grace, ensures the HTTP 200 actually reaches the browser before uvicorn gets killed.
- **Single console window** for the supervisor; the two old log windows fold into one prefixed stream. Output is also tee'd to `logs/backend.log` and `logs/frontend.log` (rotating) so crashes are recoverable.

## Components

### New files

```
launcher.py                              # supervisor entry point
backend/app/shutdown.py                  # control-socket client
frontend/src/components/StoppedView.jsx  # "App stopped" client-side view
```

### Modified files

```
start.bat                       # just runs `python launcher.py` now
backend/app/auth.py             # adds POST /auth/shutdown endpoint
backend/app/config.py           # adds SUPERVISOR_PORT setting
frontend/src/App.jsx            # tracks "stopped" state, renders StoppedView
frontend/src/components/TopBar.jsx  # adds Logoff button
frontend/src/api.js             # adds shutdownApp() call
```

### `launcher.py`

Single file, ~150 lines. Three responsibilities:

1. **`Supervisor`** — owns two `subprocess.Popen` children, started with `creationflags=CREATE_NEW_PROCESS_GROUP`, stdout/stderr piped.
2. **`LogStreamer`** — per-child thread that reads child output line-by-line, writes prefixed line to console *and* to a `RotatingFileHandler` log file under `logs/`.
3. **`ControlServer`** — `socketserver.ThreadingTCPServer` on `127.0.0.1:SUPERVISOR_PORT`, accepts a single line of text. On `"shutdown\n"` it sets a `threading.Event` the main thread is waiting on. Any other input is rejected and logged.

Main loop: spawn both children, start the control server in a thread, wait on the shutdown event *or* either child dying unexpectedly. On either trigger, run the graceful-shutdown sequence (below), then exit.

### `backend/app/shutdown.py`

Small helper (~30 lines):

- `request_supervisor_shutdown()` — opens a socket to `127.0.0.1:SUPERVISOR_PORT`, sends `"shutdown\n"`, closes. Wrapped in `try/except (ConnectionRefusedError, OSError)` so a missing supervisor (e.g., dev runs without launcher) just logs a warning instead of erroring.

### `backend/app/config.py`

Add:
```python
SUPERVISOR_PORT: int = int(os.environ.get("SUPERVISOR_PORT", "8765"))
```

`launcher.py` imports the same value (via `from app.config import settings`) so the constant lives in one place.

### `backend/app/auth.py`

New endpoint:

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

### Frontend

- **`TopBar.jsx`** — add a "Logoff" button next to the user's avatar/name.
- **`api.js`** — `shutdownApp()` does `POST /auth/shutdown` with `credentials: "include"`. 3-second timeout (via `AbortController`) so a delayed/dropped response still resolves.
- **`App.jsx`** — adds `stopped` state. Logoff handler: call `shutdownApp()`, then set `stopped = true` regardless of success/failure (the goal state is the same either way). When `stopped` is true, render `<StoppedView />` and skip the rest of the tree.
- **`StoppedView.jsx`** — pure presentational. Text: "YouTube Finder has stopped. You can safely close this tab. Run `start.bat` to launch it again."

## Shutdown Sequence

```python
def shutdown(self, reason: str):
    log(f"shutdown triggered: {reason}")
    time.sleep(1.0)  # let the HTTP 200 reach the browser

    for name, proc in [("frontend", self.frontend), ("backend", self.backend)]:
        if proc.poll() is not None:
            continue  # already dead

        try:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        except OSError as e:
            log(f"{name}: CTRL_BREAK failed: {e}; will terminate")

        try:
            proc.wait(timeout=5)
            log(f"{name}: exited cleanly")
        except subprocess.TimeoutExpired:
            log(f"{name}: timeout, terminating")
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                log(f"{name}: had to kill")

    self.log_streamers_join()
    sys.exit(0)
```

Frontend goes first so vite isn't screaming about a missing backend during its own teardown. Backend second so any in-flight request (including the `/auth/shutdown` response) finishes before its loop tears down.

## Error & Edge Cases

| Case | Handling |
|------|----------|
| User runs uvicorn directly during dev (no supervisor) | `request_supervisor_shutdown()` catches `ConnectionRefusedError`, logs `"supervisor not running, skipping"`, endpoint still returns 200. Button effectively becomes a logout-only in that mode. |
| Supervisor's child dies unexpectedly | Main loop watches each child's `poll()`. If a child exits first, supervisor logs the exit code, runs the same shutdown sequence for the survivor, exits with non-zero status. Prevents orphans. |
| Control port already in use | Supervisor logs the conflict and exits before spawning anything (no half-started state). |
| User closes the supervisor console manually | `signal.signal(SIGBREAK, ...)` and `atexit` handlers trigger the same shutdown sequence. Children don't survive as orphans. |
| `CTRL_BREAK_EVENT` raises `OSError` | Falls through to `terminate()`. Logged, doesn't abort the rest of the sequence. |
| Browser loses connection mid-request (uvicorn killed too soon) | The 1.0s `time.sleep` before the first signal gives the response time to flush. React's `shutdownApp()` has a 3s timeout and switches to `StoppedView` regardless of whether the response arrived. |
| User clicks Logoff twice | Second `shutdownApp()` call may fail (server gone). React handles by showing `StoppedView` after the first click — second click is a no-op against an already-stopped UI. |
| Endpoint hit without a session | `require_user` returns 401. Even though the supervisor's port is loopback-only, the HTTP endpoint is reachable via the dev proxy, so we keep it auth-gated. |

## Testing

### Backend unit tests (`backend/tests/test_shutdown.py`)

- `test_request_supervisor_shutdown_sends_command` — start a throwaway `socketserver` on `127.0.0.1:0`, point the client at it via monkeypatched port, assert it receives `"shutdown\n"`.
- `test_request_supervisor_shutdown_handles_no_supervisor` — call against a closed port, assert no exception, just a warning logged.
- `test_shutdown_endpoint_requires_auth` — POST `/auth/shutdown` without session → 401.
- `test_shutdown_endpoint_clears_session_and_calls_supervisor` — mock `request_supervisor_shutdown`, POST with a valid session, assert mock called once and session removed from `_sessions`.

### Launcher unit tests (`backend/tests/test_launcher.py`)

- `test_supervisor_spawns_and_signals` — use stand-in commands (`python -c "import time; time.sleep(60)"`) as the two children, drive `Supervisor.shutdown()`, assert both exit within the timeout window.
- `test_supervisor_escalates_on_timeout` — child that masks `SIGBREAK` with `signal.signal`, assert `terminate()` path is hit and exit logged.
- `test_control_server_triggers_shutdown_event` — start `ControlServer`, send `"shutdown\n"`, assert event is set.
- `test_control_server_rejects_unknown_commands` — send `"rm -rf /\n"`, assert event NOT set, message logged.
- `test_unexpected_child_death_triggers_shutdown` — kill one child externally, assert supervisor proceeds to shut down the survivor and exits non-zero.

These run on Windows; `CTRL_BREAK_EVENT` is the realistic signal so we don't fake it.

### Integration smoke (`backend/tests/test_launcher_integration.py`, `@pytest.mark.slow`)

- `test_full_shutdown_flow` — spawn the real `launcher.py` with stub child commands, wait for the control port to bind, send `"shutdown\n"`, assert process tree is empty within 10s.

Tagged slow so it's excluded from the default `pytest tests/ -v` run; opt-in via `pytest -m slow`.

### Frontend manual checklist

The codebase has no React test runner wired up; document a manual checklist alongside the implementation:

1. Click Logoff → server returns 200, view switches to `StoppedView`, supervisor console closes within ~6s.
2. Stop the supervisor (close its window) before clicking Logoff → endpoint returns 200, `StoppedView` still renders.
3. Logoff while a long search request is in flight → response completes before uvicorn dies (1s grace covers it).
4. Run `uvicorn` directly without launcher → Logoff still logs out and renders `StoppedView`; no crash.

## Out of Scope

- Auto-relaunch from the StoppedView (would require keeping *something* alive — defeats the goal).
- Cross-platform support beyond Windows. The design uses Windows-specific creation flags; macOS/Linux equivalents (POSIX process groups + `SIGINT`) are a follow-up.
- Vitest setup for the frontend pieces. If we later add a React test runner, the manual checklist becomes the seed for those tests.
- Encrypting the loopback control protocol. Single-user app, loopback-only, auth-gated endpoint upstream — extra crypto adds nothing.
