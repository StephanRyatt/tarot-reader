# File: tests/test_dev_server.py

import json
import threading
from http.server import HTTPServer
import http.client

import pytest

from dev_server import DevHandler


def _start_server() -> tuple[HTTPServer, threading.Thread, int]:
    server = HTTPServer(("127.0.0.1", 0), DevHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, t, port


def _stop_server(server: HTTPServer, t: threading.Thread) -> None:
    server.shutdown()
    server.server_close()
    t.join(timeout=2)


def _request(
    port: int,
    method: str,
    path: str = "/",
    headers: dict | None = None,
    body: str | bytes | None = None,
) -> tuple[int, dict[str, str], str]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        h = headers or {}
        b = body
        if isinstance(b, str):
            b = b.encode("utf-8")
        conn.request(method, path, body=b, headers=h)
        resp = conn.getresponse()
        status = resp.status
        resp_headers = {k: v for (k, v) in resp.getheaders()}
        data = resp.read().decode("utf-8", errors="replace")
        return status, resp_headers, data
    finally:
        conn.close()


def _initialize_body() -> str:
    return json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-11-25"},
    })


@pytest.mark.parametrize("path", ["/mcp", "/api/mcp"])
def test_mcp_paths_initialize(monkeypatch: pytest.MonkeyPatch, path: str):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    server, t, port = _start_server()
    try:
        status, headers, body = _request(
            port,
            "POST",
            path=path,
            headers={"Content-Type": "application/json"},
            body=_initialize_body(),
        )
        assert status == 200
        payload = json.loads(body)
        assert payload["result"]["serverInfo"]["name"] == "tarot-reader"
        assert "jsonrpc" in payload
    finally:
        _stop_server(server, t)


@pytest.mark.parametrize("path", ["/", "/api/tarot"])
def test_tarot_paths_keep_old_contract(monkeypatch: pytest.MonkeyPatch, path: str):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    server, t, port = _start_server()
    try:
        status, headers, body = _request(
            port,
            "POST",
            path=path,
            headers={"Content-Type": "application/json"},
            body=json.dumps({"positions": ["Past"]}),
        )
        assert status == 200
        payload = json.loads(body)
        assert set(payload.keys()) == {"draws", "meta"}
    finally:
        _stop_server(server, t)


def test_well_known_oauth_returns_404(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    server, t, port = _start_server()
    try:
        status, headers, body = _request(port, "GET", path="/.well-known/oauth-protected-resource")
        assert status == 404
        assert json.loads(body) == {"error": "Not found"}
    finally:
        _stop_server(server, t)


def test_get_root_returns_405(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    server, t, port = _start_server()
    try:
        status, headers, body = _request(port, "GET", path="/")
        assert status == 405
        assert headers.get("Allow") == "POST"
        assert json.loads(body) == {"error": "Method not allowed"}
    finally:
        _stop_server(server, t)


def test_mcp_public_does_not_open_tarot_api(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAROT_API_KEY", "secret")
    monkeypatch.setenv("TAROT_MCP_PUBLIC", "1")
    server, t, port = _start_server()
    try:
        status, headers, body = _request(
            port,
            "POST",
            path="/api/tarot",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"positions": ["Past"]}),
        )
        assert status == 401
        assert json.loads(body) == {"error": "Unauthorized"}
    finally:
        _stop_server(server, t)


def test_options_mcp_returns_204(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    server, t, port = _start_server()
    try:
        status, headers, body = _request(port, "OPTIONS", path="/mcp")
        assert status == 204
        assert body == ""
    finally:
        _stop_server(server, t)
