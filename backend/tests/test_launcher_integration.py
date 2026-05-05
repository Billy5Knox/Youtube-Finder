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
