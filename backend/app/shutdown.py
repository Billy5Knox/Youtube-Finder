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
