"""REST endpoint, POST /api/tarot, over a real socket. This contract is frozen."""

import json

import pytest

from api.tarot import handler as TarotHandler

JSON = {"Content-Type": "application/json"}
THREE_CARD = json.dumps({"positions": ["Past", "Present", "Future"]})


@pytest.fixture
def server(live_server):
    return live_server(TarotHandler)


def _assert_json(resp) -> dict:
    assert resp.headers.get("Content-Type") == "application/json"
    return json.loads(resp.body)


# Auth


def test_auth_disabled_allows_request_without_header(server):
    resp = server.request("POST", headers=JSON, body=THREE_CARD)
    assert resp.status == 200
    payload = _assert_json(resp)
    assert set(payload) == {"draws", "meta"}
    assert len(payload["draws"]) == 3


@pytest.mark.parametrize(
    "authorization",
    [None, "Bearer wrong", "Basic secret", "Bearer", "secret"],
)
def test_auth_enabled_rejects_missing_or_wrong_token(monkeypatch, server, authorization):
    monkeypatch.setenv("TAROT_API_KEY", "secret")
    headers = dict(JSON)
    if authorization is not None:
        headers["Authorization"] = authorization
    resp = server.request("POST", headers=headers, body=THREE_CARD)
    assert resp.status == 401
    assert _assert_json(resp) == {"error": "Unauthorized"}


def test_auth_enabled_correct_token_returns_200(monkeypatch, server):
    monkeypatch.setenv("TAROT_API_KEY", "secret")
    resp = server.request(
        "POST", headers={**JSON, "Authorization": "Bearer secret"}, body=THREE_CARD
    )
    assert resp.status == 200
    assert len(_assert_json(resp)["draws"]) == 3


# HTTP semantics


def test_get_returns_405_and_allow_header(server):
    resp = server.request("GET")
    assert resp.status == 405
    assert resp.headers.get("Allow") == "POST"
    assert _assert_json(resp) == {"error": "Method not allowed"}


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ("{not json", "invalid JSON body"),
        (b"\xff\xfe", "invalid JSON body"),
        (json.dumps(["not", "an", "object"]), "body must be a JSON object"),
        (json.dumps({"positions": ["Past", "Past"]}), "positions must be unique"),
    ],
)
def test_bad_body_returns_400_with_safe_message(server, body, error):
    resp = server.request("POST", headers=JSON, body=body)
    assert resp.status == 400
    assert _assert_json(resp) == {"error": error}


def test_invalid_content_length_returns_400(server):
    resp = server.raw_request("POST", "/", {"Content-Length": "abc"})
    assert resp.status == 400
    assert _assert_json(resp) == {"error": "invalid Content-Length header"}


def test_unexpected_error_is_400_without_internal_detail(monkeypatch, server):
    def boom(**_kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr("api.tarot.draw_spread", boom)
    resp = server.request("POST", headers=JSON, body=THREE_CARD)
    assert resp.status == 400
    assert _assert_json(resp) == {"error": "bad request"}


def test_rest_endpoint_has_no_cors_and_no_options(server):
    ok = server.request("POST", headers={**JSON, "Origin": "https://example.com"}, body=THREE_CARD)
    assert ok.status == 200
    assert not any(k.lower().startswith("access-control-") for k in ok.headers)
    assert server.request("OPTIONS").status == 501


# End to end


def test_valid_post_returns_draws_and_meta(server):
    body = json.dumps({"positions": ["Past", "Present", "Future"], "label": "3-card"})
    resp = server.request("POST", headers=JSON, body=body)
    assert resp.status == 200
    payload = _assert_json(resp)
    assert len(payload["draws"]) == 3
    assert payload["meta"] == {"label": "3-card"}
