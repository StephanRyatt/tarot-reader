"""Shared fixtures: a clean environment for every test and a throwaway local HTTP server."""

import http.client
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import NamedTuple

import pytest

ENV_VARS = ("TAROT_API_KEY", "TAROT_MCP_PUBLIC", "TAROT_MCP_ALLOWED_ORIGINS")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test with auth off, so a sourced .env.local can't leak in."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


class Response(NamedTuple):
    status: int
    headers: dict[str, str]
    body: bytes


class LiveServer:
    def __init__(self, handler_cls: type[BaseHTTPRequestHandler]) -> None:
        self._server = HTTPServer(("127.0.0.1", 0), handler_cls)
        self.port = self._server.server_address[1]
        # A short poll interval keeps shutdown() fast; the default of 0.5s adds up.
        self._thread = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        self._thread.start()

    def request(
        self,
        method: str,
        path: str = "/",
        headers: dict[str, str] | None = None,
        body: str | bytes | None = None,
    ) -> Response:
        if isinstance(body, str):
            body = body.encode("utf-8")
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            return Response(resp.status, dict(resp.getheaders()), resp.read())
        finally:
            conn.close()

    def raw_request(self, method: str, path: str, headers: dict[str, str]) -> Response:
        """Send headers exactly as given (no automatic Content-Length) and no body."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        try:
            conn.putrequest(method, path)
            for key, value in headers.items():
                conn.putheader(key, value)
            conn.endheaders()
            resp = conn.getresponse()
            return Response(resp.status, dict(resp.getheaders()), resp.read())
        finally:
            conn.close()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)


@pytest.fixture
def live_server() -> Iterator[Callable[[type[BaseHTTPRequestHandler]], LiveServer]]:
    """Factory: live_server(HandlerClass) starts a server on a free port, stopped after the test."""
    servers: list[LiveServer] = []

    def start(handler_cls: type[BaseHTTPRequestHandler]) -> LiveServer:
        server = LiveServer(handler_cls)
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.stop()
