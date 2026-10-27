"""The dev server routes like vercel.json: /mcp and /api/mcp to MCP, everything else to REST."""

import json

import pytest

from dev_server import DevHandler

JSON = {"Content-Type": "application/json"}
INITIALIZE = json.dumps(
    {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}}
)


@pytest.fixture
def server(live_server):
    return live_server(DevHandler)


@pytest.mark.parametrize("path", ["/mcp", "/api/mcp", "/mcp/"])
def test_mcp_paths_initialize(server, path):
    resp = server.request("POST", path=path, headers=JSON, body=INITIALIZE)
    assert resp.status == 200
    assert json.loads(resp.body)["result"]["serverInfo"]["name"] == "tarot-reader"


@pytest.mark.parametrize("path", ["/", "/api/tarot"])
def test_tarot_paths_keep_old_contract(server, path):
    body = json.dumps({"positions": ["Past"]})
    resp = server.request("POST", path=path, headers=JSON, body=body)
    assert resp.status == 200
    assert set(json.loads(resp.body)) == {"draws", "meta"}


def test_well_known_oauth_returns_404(server):
    resp = server.request("GET", path="/.well-known/oauth-protected-resource")
    assert resp.status == 404
    assert json.loads(resp.body) == {"error": "Not found"}


def test_get_root_returns_405(server):
    resp = server.request("GET", path="/")
    assert resp.status == 405
    assert resp.headers.get("Allow") == "POST"
    assert json.loads(resp.body) == {"error": "Method not allowed"}


def test_mcp_public_does_not_open_tarot_api(monkeypatch, server):
    monkeypatch.setenv("TAROT_API_KEY", "secret")
    monkeypatch.setenv("TAROT_MCP_PUBLIC", "1")
    body = json.dumps({"positions": ["Past"]})
    resp = server.request("POST", path="/api/tarot", headers=JSON, body=body)
    assert resp.status == 401
    assert json.loads(resp.body) == {"error": "Unauthorized"}


def test_options_mcp_returns_204(server):
    resp = server.request("OPTIONS", path="/mcp")
    assert resp.status == 204
    assert resp.body == b""


def test_options_and_delete_on_rest_paths_return_501(server):
    assert server.request("OPTIONS", path="/api/tarot").status == 501
    assert server.request("DELETE", path="/api/tarot").status == 501


def test_dns_rebinding_origin_is_blocked_on_local_mcp(server):
    headers = {**JSON, "Origin": "http://attacker.example"}
    resp = server.request("POST", path="/mcp", headers=headers, body=INITIALIZE)
    assert resp.status == 403
