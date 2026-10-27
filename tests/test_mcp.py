"""MCP server: handle_http() checks in order, JSON-RPC dispatch, and the socket adapter."""

import http.client
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from api.mcp import (
    INPUT_SCHEMA,
    MAX_BODY_BYTES,
    SERVER_INSTRUCTIONS,
    TOOL_NAME,
    handle_http,
)
from api.mcp import handler as McpHandler
from api.tarot import MAX_LABEL_LENGTH, MAX_POSITION_LENGTH, MAX_POSITIONS, draw_spread

REPO_ROOT = Path(__file__).resolve().parents[1]
JSON = {"Content-Type": "application/json"}


def rpc(method, params=None, req_id=1, include_id=True):
    message = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        message["params"] = params
    if include_id:
        message["id"] = req_id
    return json.dumps(message).encode("utf-8")


def call(body, headers=None, method="POST", rng=None):
    h = {k.lower(): v for k, v in (headers or {}).items()}
    if isinstance(body, str):
        body = body.encode("utf-8")
    return handle_http(method, h, body, rng=rng)


def decode(resp):
    return json.loads(resp.body.decode("utf-8"))


@pytest.fixture
def server(live_server):
    return live_server(McpHandler)


# Protocol


def test_initialize_returns_server_info_and_instructions():
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
def test_initialize_echoes_supported_older_version(version: str):
    resp = call(rpc("initialize", {"protocolVersion": version}))
    assert resp.status == 200
    assert decode(resp)["result"]["protocolVersion"] == version


@pytest.mark.parametrize(
    "params",
    [
        {"protocolVersion": "1999-01-01"},
        {"protocolVersion": None},
        ["not", "an", "object"],
        None,
    ],
)
def test_initialize_unknown_or_missing_version_falls_back_to_latest(params):
    body = rpc("initialize") if params is None else rpc("initialize", params)
    resp = call(body)
    assert resp.status == 200
    assert decode(resp)["result"]["protocolVersion"] == "2025-11-25"


def test_initialized_notification_returns_202_empty():
    body = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}).encode("utf-8")
    resp = call(body)
    assert resp.status == 202
    assert resp.body == b""


def test_ping_returns_empty_result():
    resp = call(rpc("ping"))
    assert resp.status == 200
    assert decode(resp)["result"] == {}


def test_tools_list_single_tool_metadata():
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


def test_tools_call_happy_path_matches_draw_spread():
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


def test_tools_call_without_label_has_empty_meta():
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
        {"positions": [f"P{i}" for i in range(MAX_POSITIONS + 1)]},
        {"positions": ["Past"], "label": 123},
        {"positions": ["x" * (MAX_POSITION_LENGTH + 1)]},
        {"positions": ["Past"], "label": "x" * (MAX_LABEL_LENGTH + 1)},
        [],
    ],
)
def test_tools_call_invalid_arguments_returns_is_error(arguments):
    resp = call(rpc("tools/call", {"name": TOOL_NAME, "arguments": arguments}))
    assert resp.status == 200
    payload = decode(resp)
    assert "result" in payload
    result = payload["result"]
    assert result["isError"] is True
    text = result["content"][0]["text"]
    assert text.startswith("Invalid arguments:") or text.startswith("arguments must be an object")
    assert "structuredContent" not in result


def test_tools_call_unknown_tool_is_jsonrpc_error():
    resp = call(rpc("tools/call", {"name": "not_a_tool", "arguments": {"positions": ["Past"]}}))
    assert resp.status == 200
    error = decode(resp)["error"]
    assert error["code"] == -32602


@pytest.mark.parametrize(
    "params",
    [None, [], {"name": 5}],
)
def test_tools_call_missing_name_or_bad_params(params):
    body = rpc("tools/call") if params is None else rpc("tools/call", params)
    resp = call(body)
    assert resp.status == 200
    assert decode(resp)["error"]["code"] == -32602


def test_unknown_method_returns_method_not_found():
    resp = call(rpc("no/such/method"))
    assert resp.status == 200
    error = decode(resp)["error"]
    assert error["code"] == -32601


def test_server_discover_returns_method_not_found_with_id():
    resp = call(rpc("server/discover", req_id=17))
    assert resp.status == 200
    payload = decode(resp)
    assert payload["id"] == 17
    assert payload["error"]["code"] == -32601


def test_unknown_method_notification_returns_202_empty():
    body = json.dumps({"jsonrpc": "2.0", "method": "no/such/method"}).encode("utf-8")
    resp = call(body)
    assert resp.status == 202
    assert resp.body == b""


def test_dispatch_unexpected_exception_returns_500(monkeypatch: pytest.MonkeyPatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr("api.mcp.dispatch", boom)
    resp = call(rpc("ping", req_id=42))
    assert resp.status == 500
    payload = decode(resp)
    assert payload["id"] == 42
    assert payload["error"]["code"] == -32603
    assert payload["error"]["message"] == "Internal error"


def test_imports_as_bare_module_like_vercel():
    """Vercel loads api/mcp.py with api/ on sys.path, so `import api.tarot` fails there."""
    code = "import sys; sys.path.insert(0, 'api'); import mcp; print(mcp.MAX_POSITIONS)"
    result = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == str(MAX_POSITIONS)


@pytest.mark.parametrize("body", [b"{not json", b""])
def test_parse_error(body):
    resp = call(body)
    assert resp.status == 400
    payload = decode(resp)
    assert payload["error"]["code"] == -32700
    assert payload["id"] is None


def test_batch_rejected():
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
        5,
        "ping",
    ],
)
def test_invalid_request_shapes(message):
    resp = call(json.dumps(message).encode("utf-8"))
    assert resp.status == 400
    assert decode(resp)["error"]["code"] == -32600


def test_client_response_message_returns_202():
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}).encode("utf-8")
    resp = call(body)
    assert resp.status == 202
    assert resp.body == b""


def test_body_too_large_returns_413():
    resp = call(b"x" * (MAX_BODY_BYTES + 1))
    assert resp.status == 413
    assert decode(resp)["error"]["code"] == -32600


# -------------------------
# HTTP semantics, CORS and auth
# -------------------------


def test_get_returns_405_with_allow():
    resp = call(b"", method="GET")
    assert resp.status == 405
    assert resp.headers.get("Allow") == "POST, OPTIONS"
    assert decode(resp)["error"]["code"] == -32000


def test_delete_returns_405():
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
    ok = call(rpc("initialize", {"protocolVersion": "2025-11-25"}))
    assert ok.status == 200
    assert ok.headers.get("Access-Control-Allow-Origin") == "*"

    monkeypatch.setenv("TAROT_API_KEY", "secret")
    unauthorized = call(rpc("initialize", {"protocolVersion": "2025-11-25"}))
    assert unauthorized.status == 401
    assert unauthorized.headers.get("Access-Control-Allow-Origin") == "*"


def test_auth_disabled_allows_without_header():
    resp = call(rpc("ping"))
    assert resp.status == 200
    assert decode(resp)["result"] == {}


def test_auth_enabled_missing_header_401(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAROT_API_KEY", "secret")
    resp = call(rpc("ping"))
    assert resp.status == 401
    payload = decode(resp)
    assert payload["error"]["code"] == -32000
    assert payload["error"]["message"] == "Unauthorized"
    assert "WWW-Authenticate" not in resp.headers
    assert "www-authenticate" not in {k.lower() for k in resp.headers}


def test_auth_enabled_wrong_token_401(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TAROT_API_KEY", "secret")
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


# Origin and protocol-version headers (MCP transport spec)


@pytest.mark.parametrize(
    "origin",
    [None, "", "http://localhost:6274", "http://127.0.0.1:8000", "http://[::1]:3000"],
)
def test_missing_or_local_origin_is_allowed(origin):
    headers = {} if origin is None else {"Origin": origin}
    assert call(rpc("ping"), headers=headers).status == 200


@pytest.mark.parametrize(
    "origin",
    ["https://attacker.example", "http://localhost.attacker.example", "null", "file://"],
)
@pytest.mark.parametrize("method", ["POST", "OPTIONS"])
def test_foreign_origin_is_forbidden(origin, method):
    resp = call(rpc("ping"), headers={"Origin": origin}, method=method)
    assert resp.status == 403
    payload = decode(resp)
    assert payload["id"] is None
    assert payload["error"]["message"] == "Forbidden origin"


def test_origin_check_runs_before_auth(monkeypatch):
    monkeypatch.setenv("TAROT_API_KEY", "secret")
    assert call(rpc("ping"), headers={"Origin": "https://attacker.example"}).status == 403


@pytest.mark.parametrize(
    ("configured", "origin"),
    [
        ("https://app.example", "https://app.example"),
        ("https://other.example, https://app.example/", "https://app.example"),
        ("*", "https://anything.example"),
    ],
)
def test_allowed_origins_env_var(monkeypatch, configured, origin):
    monkeypatch.setenv("TAROT_MCP_ALLOWED_ORIGINS", configured)
    assert call(rpc("ping"), headers={"Origin": origin}).status == 200


def test_supported_protocol_version_header_is_accepted():
    resp = call(rpc("ping"), headers={"MCP-Protocol-Version": "2025-06-18"})
    assert resp.status == 200


def test_unsupported_protocol_version_header_returns_400():
    resp = call(rpc("ping", req_id=9), headers={"MCP-Protocol-Version": "1999-01-01"})
    assert resp.status == 400
    payload = decode(resp)
    assert payload["id"] == 9
    assert payload["error"]["code"] == -32600


def test_initialize_ignores_protocol_version_header():
    """Version negotiation happens in the initialize body, so the header can't block it."""
    resp = call(
        rpc("initialize", {"protocolVersion": "2025-11-25"}),
        headers={"MCP-Protocol-Version": "2099-01-01"},
    )
    assert resp.status == 200
    assert decode(resp)["result"]["protocolVersion"] == "2025-11-25"


def test_input_schema_limits_match_engine():
    positions = INPUT_SCHEMA["properties"]["positions"]
    assert positions["maxItems"] == MAX_POSITIONS
    assert positions["items"]["maxLength"] == MAX_POSITION_LENGTH
    assert INPUT_SCHEMA["properties"]["label"]["maxLength"] == MAX_LABEL_LENGTH


# Socket adapter (serve)


def test_socket_initialize(server):
    resp = server.request(
        "POST", headers=JSON, body=rpc("initialize", {"protocolVersion": "2025-11-25"})
    )
    assert resp.status == 200
    assert resp.headers.get("Content-Type") == "application/json"
    assert json.loads(resp.body)["result"]["serverInfo"]["name"] == "tarot-reader"


def test_socket_tools_call(server):
    body = rpc(
        "tools/call",
        {"name": TOOL_NAME, "arguments": {"positions": ["Past", "Present", "Future"]}},
    )
    resp = server.request("POST", headers=JSON, body=body)
    assert resp.status == 200
    assert len(json.loads(resp.body)["result"]["structuredContent"]["draws"]) == 3


def test_socket_options_preflight(server):
    resp = server.request("OPTIONS")
    assert resp.status == 204
    assert resp.body == b""
    assert resp.headers.get("Access-Control-Allow-Origin") == "*"


@pytest.mark.parametrize("content_length", ["not-a-number", "-5"])
def test_serve_invalid_or_negative_content_length(server, content_length):
    resp = server.raw_request("POST", "/", {**JSON, "Content-Length": content_length})
    assert resp.status == 400
    assert json.loads(resp.body)["error"]["code"] == -32700


def test_socket_oversized_body_returns_413(server):
    resp = server.request("POST", headers=JSON, body=b"x" * (MAX_BODY_BYTES + 10))
    assert resp.status == 413


def _post_chunked(port, chunks):
    """http.client sends Transfer-Encoding: chunked when the body is an iterable."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        conn.request("POST", "/", body=iter(chunks), headers=JSON)
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def test_socket_chunked_initialize(server):
    body = rpc("initialize", {"protocolVersion": "2025-11-25"})
    status, data = _post_chunked(server.port, [body[:10], body[10:]])
    assert status == 200
    assert json.loads(data)["result"]["serverInfo"]["name"] == "tarot-reader"


def test_socket_chunked_oversized_body_returns_413(server):
    status, _ = _post_chunked(server.port, [b"x" * 40_000, b"x" * 40_000])
    assert status == 413
