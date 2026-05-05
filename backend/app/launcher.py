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
