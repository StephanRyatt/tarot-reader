# File: tests/test_mcp.py

import json
import random
import threading
from http.server import HTTPServer
from pathlib import Path
import http.client

import pytest

from api.tarot import draw_spread, MAX_POSITIONS
from api.mcp import (
    handle_http,
    handler as McpHandler,
    MAX_BODY_BYTES,
    SERVER_INSTRUCTIONS,
    TOOL_NAME,
)


def rpc(method, params=None, id=1, include_id=True):
    message = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        message["params"] = params
    if include_id:
        message["id"] = id
    return json.dumps(message).encode("utf-8")


def call(body, headers=None, method="POST", rng=None):
    h = {k.lower(): v for k, v in (headers or {}).items()}
    if isinstance(body, str):
        body = body.encode("utf-8")
    return handle_http(method, h, body, rng=rng)


def decode(resp):
    return json.loads(resp.body.decode("utf-8"))


def _start_server() -> tuple[HTTPServer, threading.Thread, int]:
    server = HTTPServer(("127.0.0.1", 0), McpHandler)
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
) -> tuple[int, dict[str, str], bytes]:
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
        data = resp.read()
        return status, resp_headers, data
    finally:
        conn.close()


# -------------------------
# Protocol tests
# -------------------------

def test_initialize_returns_server_info_and_instructions(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    resp = call(rpc("initialize", {"protocolVersion": "2025-11-25"}))
    assert resp.status == 200
    assert resp.headers.get("Content-Type") == "application/json"
    payload = decode(resp)
    result = payload["result"]
    assert result["protocolVersion"] == "2025-11-25"
    assert "tools" in result["capabilities"]
    assert result["serverInfo"]["name"] == "tarot-reader"
    assert len(result["instructions"]) <= 512
    assert "draw_tarot_spread" in result["instructions"]
    assert "Never invent" in result["instructions"]
    assert result["instructions"] == SERVER_INSTRUCTIONS


@pytest.mark.parametrize(
    "version",
    ["2025-06-18", "2025-03-26", "2024-11-05"],
)
def test_initialize_echoes_supported_older_version(
    monkeypatch: pytest.MonkeyPatch, version: str
):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    resp = call(rpc("initialize", {"protocolVersion": version}))
    assert resp.status == 200
    assert decode(resp)["result"]["protocolVersion"] == version


@pytest.mark.parametrize(
    "params",
    [
        {"protocolVersion": "1999-01-01"},
        {"protocolVersion": None},
        None,
    ],
)
def test_initialize_unknown_or_missing_version_falls_back_to_latest(
    monkeypatch: pytest.MonkeyPatch, params
):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    if params is None:
        body = rpc("initialize")
    else:
        body = rpc("initialize", params)
    resp = call(body)
    assert resp.status == 200
    assert decode(resp)["result"]["protocolVersion"] == "2025-11-25"


def test_initialized_notification_returns_202_empty(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    body = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}).encode("utf-8")
    resp = call(body)
    assert resp.status == 202
    assert resp.body == b""


def test_ping_returns_empty_result(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    resp = call(rpc("ping"))
    assert resp.status == 200
    assert decode(resp)["result"] == {}


def test_tools_list_single_tool_metadata(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    resp = call(rpc("tools/list"))
    assert resp.status == 200
    tools = decode(resp)["result"]["tools"]
    assert len(tools) == 1
    tool = tools[0]
    assert tool["name"] == "draw_tarot_spread"
    assert tool["title"]
    assert tool["inputSchema"]["required"] == ["positions"]
    assert tool["inputSchema"]["properties"]["positions"]["maxItems"] == MAX_POSITIONS
    assert tool["outputSchema"]["required"] == ["draws", "meta"]
    assert tool["annotations"] == {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
    assert tool["securitySchemes"] == [{"type": "noauth"}]


def test_tools_call_happy_path_matches_draw_spread(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    positions = ["Past", "Present", "Future"]
    expected = draw_spread(positions=positions, label="3-card", rng=random.Random(7))
    resp = call(
        rpc(
            "tools/call",
            {
                "name": TOOL_NAME,
                "arguments": {"positions": positions, "label": "3-card"},
            },
        ),
        rng=random.Random(7),
    )
    assert resp.status == 200
    result = decode(resp)["result"]
    assert result["isError"] is False
    assert result["structuredContent"] == expected
    assert result["content"][0]["type"] == "text"
    text = result["content"][0]["text"]
    assert "label: 3-card" in text
    assert "1. Past:" in text
    assert "2. Present:" in text
    assert "3. Future:" in text
    past_idx = text.index("1. Past:")
    present_idx = text.index("2. Present:")
    future_idx = text.index("3. Future:")
    assert past_idx < present_idx < future_idx


def test_tools_call_without_label_has_empty_meta(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    resp = call(
        rpc("tools/call", {"name": TOOL_NAME, "arguments": {"positions": ["Past"]}}),
        rng=random.Random(1),
    )
    assert resp.status == 200
    result = decode(resp)["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["meta"] == {}
    assert result["content"][0]["text"].startswith("Tarot spread drawn:")


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"positions": "Past"},
        {"positions": []},
        {"positions": ["Past", "Past"]},
        {"positions": ["Past", "  "]},
        {"positions": [f"P{i}" for i in range(31)]},
        {"positions": ["Past"], "label": 123},
        {"positions": ["Past"], "label": "x" * 201},
        [],
    ],
)
def test_tools_call_invalid_arguments_returns_isError(monkeypatch: pytest.MonkeyPatch, arguments):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    resp = call(rpc("tools/call", {"name": TOOL_NAME, "arguments": arguments}))
    assert resp.status == 200
    payload = decode(resp)
    assert "result" in payload
    result = payload["result"]
    assert result["isError"] is True
    text = result["content"][0]["text"]
    assert text.startswith("Invalid arguments:") or text.startswith("arguments must be an object")
    assert "structuredContent" not in result


def test_tools_call_unknown_tool_is_jsonrpc_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    resp = call(rpc("tools/call", {"name": "not_a_tool", "arguments": {"positions": ["Past"]}}))
    assert resp.status == 200
    error = decode(resp)["error"]
    assert error["code"] == -32602


@pytest.mark.parametrize(
    "params",
    [None, [], {"name": 5}],
)
def test_tools_call_missing_name_or_bad_params(monkeypatch: pytest.MonkeyPatch, params):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    if params is None:
        body = rpc("tools/call")
    else:
        body = rpc("tools/call", params)
    resp = call(body)
    assert resp.status == 200
    assert decode(resp)["error"]["code"] == -32602


def test_unknown_method_returns_method_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    resp = call(rpc("no/such/method"))
    assert resp.status == 200
    error = decode(resp)["error"]
    assert error["code"] == -32601


def test_server_discover_returns_method_not_found_with_id(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    resp = call(rpc("server/discover", id=17))
    assert resp.status == 200
    payload = decode(resp)
    assert payload["id"] == 17
    assert payload["error"]["code"] == -32601


def test_unknown_method_notification_returns_202_empty(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    body = json.dumps({"jsonrpc": "2.0", "method": "no/such/method"}).encode("utf-8")
    resp = call(body)
    assert resp.status == 202
    assert resp.body == b""


def test_dispatch_unexpected_exception_returns_500(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)

    def boom(*_args, **_kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr("api.mcp.dispatch", boom)
    resp = call(rpc("ping", id=42))
    assert resp.status == 500
    payload = decode(resp)
    assert payload["id"] == 42
    assert payload["error"]["code"] == -32603
    assert payload["error"]["message"] == "Internal error"


def test_importerror_fallback_import_path_present():
    source = (Path(__file__).resolve().parents[1] / "api" / "mcp.py").read_text(
        encoding="utf-8"
    )
    assert "from tarot import draw_spread, is_authorized, MAX_POSITIONS" in source


@pytest.mark.parametrize("body", [b"{not json", b""])
def test_parse_error(monkeypatch: pytest.MonkeyPatch, body):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    resp = call(body)
    assert resp.status == 400
    payload = decode(resp)
    assert payload["error"]["code"] == -32700
    assert payload["id"] is None


def test_batch_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    body = json.dumps([{"jsonrpc": "2.0", "id": 1, "method": "ping"}]).encode("utf-8")
    resp = call(body)
    assert resp.status == 400
    assert decode(resp)["error"]["code"] == -32600


@pytest.mark.parametrize(
    "message",
    [
        {"method": "ping", "id": 1},
        {"jsonrpc": "1.0", "method": "ping", "id": 1},
        {"jsonrpc": "2.0", "method": 5, "id": 1},
        {"jsonrpc": "2.0", "method": "ping", "id": None},
        {"jsonrpc": "2.0", "method": "ping", "id": True},
    ],
)
def test_invalid_request_shapes(monkeypatch: pytest.MonkeyPatch, message):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    resp = call(json.dumps(message).encode("utf-8"))
    assert resp.status == 400
    assert decode(resp)["error"]["code"] == -32600


def test_client_response_message_returns_202(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}).encode("utf-8")
    resp = call(body)
    assert resp.status == 202
    assert resp.body == b""


def test_body_too_large_returns_413(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    resp = call(b"x" * (MAX_BODY_BYTES + 1))
    assert resp.status == 413
    assert decode(resp)["error"]["code"] == -32600


# -------------------------
# HTTP semantics, CORS and auth
# -------------------------

def test_get_returns_405_with_allow(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    resp = call(b"", method="GET")
    assert resp.status == 405
    assert resp.headers.get("Allow") == "POST, OPTIONS"
    assert decode(resp)["error"]["code"] == -32000


def test_delete_returns_405(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    resp = call(b"", method="DELETE")
    assert resp.status == 405
    assert resp.headers.get("Allow") == "POST, OPTIONS"
    assert decode(resp)["error"]["code"] == -32000


def test_options_returns_204_with_cors_even_when_auth_enabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAROT_API_KEY", "secret")
    resp = call(b"", method="OPTIONS")
    assert resp.status == 204
    assert resp.body == b""
    assert resp.headers.get("Access-Control-Allow-Origin") == "*"
    allowed = resp.headers.get("Access-Control-Allow-Headers", "")
    assert "Authorization" in allowed
    assert "Mcp-Protocol-Version" in allowed
    assert "Mcp-Method" in allowed
    assert "Mcp-Name" in allowed
    exposed = resp.headers.get("Access-Control-Expose-Headers", "")
    assert "Mcp-Session-Id" in exposed
    assert "Mcp-Protocol-Version" in exposed


def test_cors_header_present_on_post_200_and_401(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    ok = call(rpc("initialize", {"protocolVersion": "2025-11-25"}))
    assert ok.status == 200
    assert ok.headers.get("Access-Control-Allow-Origin") == "*"

    monkeypatch.setenv("TAROT_API_KEY", "secret")
    monkeypatch.delenv("TAROT_MCP_PUBLIC", raising=False)
    unauthorized = call(rpc("initialize", {"protocolVersion": "2025-11-25"}))
    assert unauthorized.status == 401
    assert unauthorized.headers.get("Access-Control-Allow-Origin") == "*"


def test_auth_disabled_allows_without_header(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    resp = call(rpc("ping"))
    assert resp.status == 200
    assert decode(resp)["result"] == {}


def test_auth_enabled_missing_header_401(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAROT_API_KEY", "secret")
    monkeypatch.delenv("TAROT_MCP_PUBLIC", raising=False)
    resp = call(rpc("ping"))
    assert resp.status == 401
    payload = decode(resp)
    assert payload["error"]["code"] == -32000
    assert payload["error"]["message"] == "Unauthorized"
    assert "WWW-Authenticate" not in resp.headers
    assert "www-authenticate" not in {k.lower() for k in resp.headers}


def test_auth_enabled_wrong_token_401(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAROT_API_KEY", "secret")
    monkeypatch.delenv("TAROT_MCP_PUBLIC", raising=False)
    resp = call(rpc("ping"), headers={"Authorization": "Bearer wrong"})
    assert resp.status == 401
    payload = decode(resp)
    assert payload["error"]["code"] == -32000
    assert payload["error"]["message"] == "Unauthorized"
    assert "WWW-Authenticate" not in resp.headers


def test_mcp_public_skips_auth_when_flag_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAROT_API_KEY", "secret")
    monkeypatch.setenv("TAROT_MCP_PUBLIC", "1")
    resp = call(rpc("initialize", {"protocolVersion": "2025-11-25"}))
    assert resp.status == 200
    assert decode(resp)["result"]["serverInfo"]["name"] == "tarot-reader"


def test_auth_enabled_correct_token_200(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAROT_API_KEY", "secret")
    resp = call(rpc("ping"), headers={"Authorization": "Bearer secret"})
    assert resp.status == 200
    assert decode(resp)["result"] == {}


# -------------------------
# Socket tests
# -------------------------

def test_socket_initialize(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    server, t, port = _start_server()
    try:
        status, headers, body = _request(
            port,
            "POST",
            headers={"Content-Type": "application/json"},
            body=rpc("initialize", {"protocolVersion": "2025-11-25"}),
        )
        assert status == 200
        assert headers.get("Content-Type") == "application/json"
        payload = json.loads(body.decode("utf-8"))
        assert payload["result"]["serverInfo"]["name"] == "tarot-reader"
    finally:
        _stop_server(server, t)


def test_socket_tools_call(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    server, t, port = _start_server()
    try:
        status, headers, body = _request(
            port,
            "POST",
            headers={"Content-Type": "application/json"},
            body=rpc(
                "tools/call",
                {
                    "name": TOOL_NAME,
                    "arguments": {"positions": ["Past", "Present", "Future"]},
                },
            ),
        )
        assert status == 200
        payload = json.loads(body.decode("utf-8"))
        assert len(payload["result"]["structuredContent"]["draws"]) == 3
    finally:
        _stop_server(server, t)


def test_socket_options_preflight(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    server, t, port = _start_server()
    try:
        status, headers, body = _request(port, "OPTIONS")
        assert status == 204
        assert body == b""
        assert headers.get("Access-Control-Allow-Origin") == "*"
    finally:
        _stop_server(server, t)


@pytest.mark.parametrize("content_length", ["not-a-number", "-5"])
def test_serve_invalid_or_negative_content_length(
    monkeypatch: pytest.MonkeyPatch, content_length: str
):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    server, t, port = _start_server()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            conn.putrequest("POST", "/")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", content_length)
            conn.endheaders()
            resp = conn.getresponse()
            status = resp.status
            body = resp.read()
        finally:
            conn.close()
        assert status == 400
        payload = json.loads(body.decode("utf-8"))
        assert payload["error"]["code"] == -32700
    finally:
        _stop_server(server, t)


def test_socket_chunked_initialize(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TAROT_API_KEY", raising=False)
    server, t, port = _start_server()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            conn.request(
                "POST",
                "/",
                body=rpc("initialize", {"protocolVersion": "2025-11-25"}),
                headers={"Content-Type": "application/json"},
                encode_chunked=True,
            )
            resp = conn.getresponse()
            status = resp.status
            body = resp.read()
        finally:
            conn.close()
        assert status == 200
        payload = json.loads(body.decode("utf-8"))
        assert payload["result"]["serverInfo"]["name"] == "tarot-reader"
    finally:
        _stop_server(server, t)
