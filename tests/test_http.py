# File: tests/test_http.py

import json
import os
import threading
import http.client
from http.server import HTTPServer

import pytest

from api.tarot import handler as TarotHandler


def _start_server() -> tuple[HTTPServer, threading.Thread, int]:
    """
    Start an ephemeral local HTTP server with the Tarot handler.
    Returns (server, thread, port).
    """
    server = HTTPServer(("127.0.0.1", 0), TarotHandler)
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
    """
    Make an HTTP request to localhost:<port> and return (status, headers, body_text).
    """
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


def _assert_json_content_type(headers: dict[str, str]) -> None:
    assert headers.get("Content-Type") == "application/json"


# -------------------------
# D) Auth behavior
# -------------------------

def test_auth_disabled_allows_request_without_header(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)

    server, t, port = _start_server()
    try:
        status, headers, body = _request(
            port,
            "POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"positions": ["Past", "Present", "Future"]}),
        )
        assert status == 200
        _assert_json_content_type(headers)

        payload = json.loads(body)
        assert set(payload.keys()) == {"draws", "meta"}
        assert len(payload["draws"]) == 3
    finally:
        _stop_server(server, t)


def test_auth_enabled_missing_header_returns_401(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAROT_API_KEY", "secret")

    server, t, port = _start_server()
    try:
        status, headers, body = _request(
            port,
            "POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"positions": ["Past", "Present", "Future"]}),
        )
        assert status == 401
        _assert_json_content_type(headers)
        assert json.loads(body) == {"error": "Unauthorized"}
    finally:
        _stop_server(server, t)


def test_auth_enabled_wrong_token_returns_401(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAROT_API_KEY", "secret")

    server, t, port = _start_server()
    try:
        status, headers, body = _request(
            port,
            "POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer wrong",
            },
            body=json.dumps({"positions": ["Past", "Present", "Future"]}),
        )
        assert status == 401
        _assert_json_content_type(headers)
        assert json.loads(body) == {"error": "Unauthorized"}
    finally:
        _stop_server(server, t)


def test_auth_enabled_correct_token_returns_200(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAROT_API_KEY", "secret")

    server, t, port = _start_server()
    try:
        status, headers, body = _request(
            port,
            "POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer secret",
            },
            body=json.dumps({"positions": ["Past", "Present", "Future"]}),
        )
        assert status == 200
        _assert_json_content_type(headers)
        payload = json.loads(body)
        assert set(payload.keys()) == {"draws", "meta"}
        assert len(payload["draws"]) == 3
    finally:
        _stop_server(server, t)


# -------------------------
# E) HTTP semantics
# -------------------------

def test_get_returns_405_and_allow_header(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)

    server, t, port = _start_server()
    try:
        status, headers, body = _request(port, "GET")
        assert status == 405
        assert headers.get("Allow") == "POST"
        _assert_json_content_type(headers)
        assert json.loads(body) == {"error": "Method not allowed"}
    finally:
        _stop_server(server, t)


def test_invalid_json_returns_400(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)

    server, t, port = _start_server()
    try:
        status, headers, body = _request(
            port,
            "POST",
            headers={"Content-Type": "application/json"},
            body="{not json",
        )
        assert status == 400
        _assert_json_content_type(headers)
        assert json.loads(body) == {"error": "invalid JSON body"}
    finally:
        _stop_server(server, t)


def test_invalid_body_shape_returns_400(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)

    server, t, port = _start_server()
    try:
        # Body is valid JSON but not an object
        status, headers, body = _request(
            port,
            "POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(["not", "an", "object"]),
        )
        assert status == 400
        _assert_json_content_type(headers)
        assert json.loads(body) == {"error": "body must be a JSON object"}
    finally:
        _stop_server(server, t)


def test_content_type_is_json_on_unauthorized(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAROT_API_KEY", "secret")

    server, t, port = _start_server()
    try:
        status, headers, _ = _request(
            port,
            "POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"positions": ["Past"]}),
        )
        assert status == 401
        _assert_json_content_type(headers)
    finally:
        _stop_server(server, t)


# -------------------------
# F) End-to-end happy path
# -------------------------

def test_valid_post_returns_draws_and_meta(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)

    server, t, port = _start_server()
    try:
        status, headers, body = _request(
            port,
            "POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"positions": ["Past", "Present", "Future"], "label": "3-card"}),
        )
        assert status == 200
        _assert_json_content_type(headers)

        payload = json.loads(body)
        assert "draws" in payload and "meta" in payload
        assert len(payload["draws"]) == 3
        assert payload["meta"] == {"label": "3-card"}
    finally:
        _stop_server(server, t)
