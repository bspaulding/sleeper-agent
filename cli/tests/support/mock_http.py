"""A real local HTTP server for tests, per PROJECT_PLAN.md §10.4.

Deliberately not a faked-out transport: tests spin up a small stdlib
http.server instance with a scripted handler and point client code at it via
an explicit base_url parameter, so the real requests/HTTP code path runs
end-to-end.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer


@dataclass(frozen=True)
class Request:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""


Handler = Callable[[Request], Response]


def _handler_class(handler: Handler) -> type[BaseHTTPRequestHandler]:
    class _Adapter(BaseHTTPRequestHandler):
        def _dispatch(self) -> None:
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length) if length else b""
            request = Request(
                method=self.command,
                path=self.path,
                headers={key: value for key, value in self.headers.items()},
                body=body,
            )
            response = handler(request)
            self.send_response(response.status)
            for key, value in response.headers.items():
                self.send_header(key, value)
            if "Content-Length" not in response.headers:
                self.send_header("Content-Length", str(len(response.body)))
            self.end_headers()
            self.wfile.write(response.body)

        def do_GET(self) -> None:
            self._dispatch()

        def do_POST(self) -> None:
            self._dispatch()

        def do_PUT(self) -> None:
            self._dispatch()

        def do_PATCH(self) -> None:
            self._dispatch()

        def do_DELETE(self) -> None:
            self._dispatch()

        def log_message(self, format: str, *args: object) -> None:
            pass  # silence default request logging to stderr during tests

    return _Adapter


@contextmanager
def mock_http_server(handler: Handler) -> Iterator[str]:
    server = HTTPServer(("127.0.0.1", 0), _handler_class(handler))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
