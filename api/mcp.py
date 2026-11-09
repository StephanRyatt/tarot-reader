"""Stateless Streamable HTTP MCP server exposing one tool, draw_tarot_spread.

`handle_http()` is the transport-agnostic core: plain values in, an HttpResponse out.
`serve()` adapts a BaseHTTPRequestHandler to it, and `handler` is the class Vercel
serves for this file.

The server is dual-era (ADR 0008). Legacy clients open with `initialize` and speak
2025-11-25 or earlier. Modern clients (2026-07-28) skip the handshake and send the version
in the `MCP-Protocol-Version` header and in each request's `_meta`.
"""

import base64
import json
import os
import random
import sys
from http.server import BaseHTTPRequestHandler
from io import BufferedIOBase
from typing import Any, NamedTuple
from urllib.parse import urlsplit

# Vercel imports this file as a bare module next to tarot.py; tests import it as api.mcp.
try:
    from api.tarot import (
        MAX_LABEL_LENGTH,
        MAX_POSITION_LENGTH,
        MAX_POSITIONS,
        draw_spread,
        is_authorized,
    )
except ImportError:  # pragma: no cover - exercised in a subprocess by the tests
    from tarot import (  # type: ignore[import-not-found,no-redef]
        MAX_LABEL_LENGTH,
        MAX_POSITION_LENGTH,
        MAX_POSITIONS,
        draw_spread,
        is_authorized,
    )

SERVER_NAME = "tarot-reader"
SERVER_TITLE = "Tarot Reader"
SERVER_VERSION = "1.2.0"
# Modern versions carry the version on every request; legacy ones negotiate it in initialize.
MODERN_PROTOCOL_VERSIONS = ("2026-07-28",)
LEGACY_PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
SUPPORTED_PROTOCOL_VERSIONS = MODERN_PROTOCOL_VERSIONS + LEGACY_PROTOCOL_VERSIONS
LATEST_LEGACY_VERSION = LEGACY_PROTOCOL_VERSIONS[0]
MAX_BODY_BYTES = 64 * 1024
TOOL_NAME = "draw_tarot_spread"

PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR = (
    -32700,
    -32600,
    -32601,
    -32602,
    -32603,
)
# Implementation-defined JSON-RPC server error, used for HTTP-level rejections.
SERVER_ERROR = -32000
# Errors the 2026-07-28 spec defines. A dual-era client reads them as "this server is modern".
HEADER_MISMATCH, UNSUPPORTED_PROTOCOL_VERSION = -32020, -32022

# Modern-era request metadata (2026-07-28).
META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"
META_SERVER_INFO = "io.modelcontextprotocol/serverInfo"
# Methods whose Mcp-Name header mirrors a body field.
NAMED_METHODS = {"tools/call": "name", "prompts/get": "name", "resources/read": "uri"}
MODERN_METHODS = frozenset(
    {"server/discover", "tools/list", "tools/call", "prompts/list", "prompts/get"}
)
# Tool and prompt lists change only on deploy; clients and shared caches may keep them an hour.
LIST_TTL_MS = 60 * 60 * 1000

PUBLIC_ENV_VAR = "TAROT_MCP_PUBLIC"
ALLOWED_ORIGINS_ENV_VAR = "TAROT_MCP_ALLOWED_ORIGINS"
LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1"})

# Kept under 512 characters (tests/test_mcp.py); the skill and tool description carry the rest.
SERVER_INSTRUCTIONS = (
    "Tarot Reader draws real, random cards from a shuffled 78-card Rider-Waite deck. "
    "To draw cards, call draw_tarot_spread first, one position per card; label is the "
    "spread name only. Never invent or alter cards or orientations: interpret only the cards "
    "returned, in order. Draw the spread once per reading; never redraw to change a result. "
    "One clarifier card may follow only if the user asks for or accepts it. Lead with which "
    "way the cards lean; no fixed fate or dates. Not medical, legal, or financial advice."
)

INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "positions": {
            "type": "array",
            "description": (
                "Spread position names in reading order, one per card, "
                'e.g. ["Past", "Present", "Future"]. Each name must be unique.'
            ),
            "items": {"type": "string", "minLength": 1, "maxLength": MAX_POSITION_LENGTH},
            "minItems": 1,
            "maxItems": MAX_POSITIONS,
            "uniqueItems": True,
        },
        "label": {
            "type": "string",
            "description": (
                'Optional spread name, e.g. "Daily Alignment" or "Celtic Cross". '
                "Never the user's question or private details."
            ),
            "maxLength": MAX_LABEL_LENGTH,
        },
    },
    "required": ["positions"],
    "additionalProperties": False,
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "draws": {
            "type": "object",
            "description": "Map of position name to the card drawn for it.",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "card": {"type": "string"},
                    "orientation": {"type": "string", "enum": ["upright", "reversed"]},
                },
                "required": ["card", "orientation"],
                "additionalProperties": False,
            },
        },
        "meta": {
            "type": "object",
            "properties": {"label": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    "required": ["draws", "meta"],
    "additionalProperties": False,
}

TOOL_DEFINITION = {
    "name": TOOL_NAME,
    "title": "Draw tarot spread",
    "description": (
        "Use this when the user wants a tarot reading or wants cards pulled for a spread. "
        "Must NOT be used when the user names cards they already drew "
        "(unless they ask you to pull a clarifier for them) or asks what a named card means. "
        "Shuffles a full 78-card Rider-Waite deck (with reversals) and draws one real random card "
        "per named position. Keep the user's question and private details out of positions and "
        "label. Call once per reading, then interpret only the returned cards. One more call, for "
        "a single clarifier card, is allowed only when the user asks for or accepts one. "
        "Open the reading with which way the cards lean, naming the cards that carry it; "
        "describe direction and what it asks, never fixed fate, events or dates, and never "
        "answer yes or no to whether an event will happen. "
        "The decision stays with the user, and other people's feelings are read as likely "
        "patterns, never verdicts."
    ),
    "inputSchema": INPUT_SCHEMA,
    "outputSchema": OUTPUT_SCHEMA,
    "annotations": {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
    "securitySchemes": [{"type": "noauth"}],
    "_meta": {"securitySchemes": [{"type": "noauth"}]},
}


class Spread(NamedTuple):
    """A named spread, served as an MCP prompt so clients can offer it in their own UI."""

    slug: str
    name: str
    purpose: str
    positions: tuple[tuple[str, str], ...]  # (position name, meaning), in reading order
    note: str = ""


# The spread library. plugin/skills/tarot-reading/references/spreads.md mirrors it, and
# tests/test_consistency.py fails if the two drift apart.
SPREADS = (
    Spread(
        "card-of-the-day",
        "Card of the Day",
        "For a single card that sets the tone of the day.",
        (("Card of the Day", "The quality the day asks you to meet or embody."),),
    ),
    Spread(
        "daily-alignment",
        "Daily Alignment",
        "To support grounded presence and conscious choice through the day.",
        (
            ("Day's Atmosphere", "The overall tone or quality shaping the day."),
            ("Primary Focus", "What most deserves your attention or care today."),
            ("Aligned Approach", "How to meet the day in a way that stays true to yourself."),
        ),
    ),
    Spread(
        "daily-focus",
        "Daily Focus",
        "For workdays or self-directed days, emphasising clarity, momentum and deliberate action.",
        (
            ("Core Focus", "The central theme to align with today."),
            ("Mental Energy", "The mindset that best supports you today."),
            ("Challenge / Distraction", "What could pull you off course or dilute your focus."),
            ("Support / Ally", "A resource, strength or supportive condition available to you."),
            ("Empowered Action", "One concrete action to take today, drawn from this card."),
        ),
    ),
    Spread(
        "weekly-path",
        "Weekly Path",
        "For practical clarity about the outer flow of the week: influences, challenges and "
        "direction.",
        (
            ("Headline Energy", "The dominant outer atmosphere of the week."),
            (
                "Key Event / Influence",
                "The kind of situation or influence likely to ask for your attention: a theme, "
                "not a specific event.",
            ),
            ("Challenge", "The main tension or point of friction to work with."),
            ("Best Response", "The choice, action or stance this week asks of you."),
            (
                "Trajectory",
                "Where the week heads on its current course. It describes a direction you can "
                "still shape, not a fixed outcome.",
            ),
        ),
    ),
    Spread(
        "weekly-evolution",
        "Weekly Evolution",
        "For inner work: lessons, change and integration over the week.",
        (
            ("Core Vibration", "The underlying psychological theme shaping the week."),
            (
                "Shadow / Old Pattern",
                "An inherited habit, belief or reaction that asks to be seen and released.",
            ),
            ("Soul Lesson", "The deeper teaching in the week's experiences."),
            ("Practice / Embodiment", "A grounded practice or habit that supports integration."),
            ("Emerging Self", "The quality or capacity coming into form."),
        ),
    ),
    Spread(
        "past-present-future",
        "Past, Present, Future",
        "The classic three-card spread.",
        (
            ("Past", "What led here and still shapes the situation."),
            ("Present", "The heart of the situation now."),
            ("Future", "Where this heads on its current course. A direction, not a fixed outcome."),
        ),
    ),
    Spread(
        "decision",
        "Decision",
        "For a choice between two options.",
        (
            ("Heart of the Matter", "What this choice is really about."),
            (
                "Option: <A>",
                "What choosing A asks of you, and where it leads on its current course.",
            ),
            (
                "Option: <B>",
                "What choosing B asks of you, and where it leads on its current course.",
            ),
            ("What You're Not Seeing", "The factor missing from how you're weighing it."),
            ("What Matters Most in Choosing", "The value or need that should decide it."),
        ),
        note=(
            'Replace <A> and <B> with short names for the options, such as "Stay" and "Go". '
            "Keep names, places and other private details out. For three or more options, add "
            "one position per option."
        ),
    ),
    Spread(
        "celtic-cross",
        "Celtic Cross",
        "The traditional ten-card spread, for a full view of a complex situation.",
        (
            ("Present", "The heart of the situation now."),
            ("Challenge", "What crosses it: the obstacle or tension."),
            ("Foundation", "The root beneath the situation."),
            ("Recent Past", "What is passing out of the situation."),
            ("Crown", "The best that can be reached, or the conscious aim."),
            ("Near Future", "What is coming into the situation next."),
            ("Self", "How you stand in it."),
            ("Environment", "The people and conditions around you."),
            ("Hopes and Fears", "What you hope for and fear, often the same thing."),
            (
                "Where This Heads",
                "Where the situation heads on its current course. A direction, not a fixed "
                "outcome.",
            ),
        ),
    ),
)
SPREADS_BY_SLUG = {spread.slug: spread for spread in SPREADS}


def _prompt_definition(spread: Spread) -> dict[str, Any]:
    return {"name": spread.slug, "title": spread.name, "description": spread.purpose}


def _prompt_text(spread: Spread) -> str:
    """The user message a client inserts when someone picks this spread from its UI."""
    names = [name for name, _meaning in spread.positions]
    lines = [f"Give me a {spread.name} tarot reading."]
    if spread.slug == "decision":
        lines.append(
            "Before drawing, ask me which options I'm choosing between, unless I've already said."
        )
    lines += [
        "",
        f"Draw it once with {TOOL_NAME}, using these positions and label:",
        f"- positions: {json.dumps(names)}",
        f'- label: "{spread.name}"',
    ]
    if spread.note:
        lines.append(spread.note)
    lines += ["", "What each position means:"]
    lines += [
        f"{i}. {name}: {meaning}" for i, (name, meaning) in enumerate(spread.positions, start=1)
    ]
    return "\n".join(lines)


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS, DELETE",
    "Access-Control-Allow-Headers": (
        "Content-Type, Authorization, Accept, Mcp-Protocol-Version, "
        "Mcp-Session-Id, Last-Event-ID, Mcp-Method, Mcp-Name, traceparent, tracestate, baggage"
    ),
    "Access-Control-Expose-Headers": "Mcp-Session-Id, Mcp-Protocol-Version",
    "Access-Control-Max-Age": "86400",
}


class HttpResponse(NamedTuple):
    status: int
    headers: dict[str, str]
    body: bytes


class _RpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _rpc_result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _rpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _json_response(status: int, payload: dict[str, Any]) -> HttpResponse:
    body = json.dumps(payload).encode("utf-8")
    headers = {**CORS_HEADERS, "Content-Type": "application/json"}
    return HttpResponse(status, headers, body)


def _empty_response(status: int) -> HttpResponse:
    return HttpResponse(status, {**CORS_HEADERS, "Content-Length": "0"}, b"")


def _is_valid_id(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    return isinstance(value, (str, int))


def _echo_id(message: dict[str, Any]) -> Any:
    """The request id to echo in an error, or None when it is missing or invalid."""
    req_id = message.get("id")
    return req_id if _is_valid_id(req_id) else None


def _is_allowed_origin(origin: str | None) -> bool:
    """Guard against DNS rebinding, as the MCP transport spec requires.

    DNS rebinding lets a web page reach a server that trusts its network position, such
    as one on localhost. A public server (TAROT_MCP_PUBLIC=1) trusts nothing about the
    caller, so every origin is valid there; ChatGPT's apps and web views can send origins
    such as https://chatgpt.com or "null" (ADR 0008). Otherwise, requests without an Origin
    (server-side clients) and from local pages (MCP Inspector) are allowed, and other
    browser origins must be listed in TAROT_MCP_ALLOWED_ORIGINS (comma-separated), or that
    variable set to "*".
    """
    if not origin or os.environ.get(PUBLIC_ENV_VAR) == "1":
        return True
    configured = {
        entry.strip().rstrip("/")
        for entry in os.environ.get(ALLOWED_ORIGINS_ENV_VAR, "").split(",")
        if entry.strip()
    }
    if "*" in configured or origin.rstrip("/") in configured:
        return True
    parts = urlsplit(origin)
    return parts.scheme in ("http", "https") and parts.hostname in LOCAL_HOSTNAMES


def format_spread_text(payload: dict[str, Any]) -> str:
    label = (payload.get("meta") or {}).get("label")
    lines = [f"Tarot spread drawn (label: {label}):" if label else "Tarot spread drawn:"]
    draws = payload.get("draws") or {}
    for i, (position, card) in enumerate(draws.items(), start=1):
        lines.append(f"{i}. {position}: {card['card']} ({card['orientation']})")
    return "\n".join(lines)


def _negotiate_version(requested: Any) -> str:
    """The legacy version an initialize request settles on."""
    if isinstance(requested, str) and requested in LEGACY_PROTOCOL_VERSIONS:
        return requested
    return LATEST_LEGACY_VERSION


def _decode_header_value(value: str) -> str | None:
    """Undo the spec's `=?base64?...?=` sentinel; None when the encoding is broken."""
    if not (value.startswith("=?base64?") and value.endswith("?=")):
        return value
    try:
        return base64.b64decode(value[9:-2], validate=True).decode("utf-8")
    except ValueError:  # binascii.Error, non-ASCII input, or bytes that aren't UTF-8
        return None


def _header_mismatch(message: dict[str, Any], headers: dict[str, str]) -> str | None:
    """Why a modern request's headers disagree with its body, or None when they agree."""
    method = message["method"]
    if headers.get("mcp-method") != method:
        return "Mcp-Method header is missing or does not match the body"
    params = message.get("params")
    params = params if isinstance(params, dict) else {}
    meta = params.get("_meta")
    meta = meta if isinstance(meta, dict) else {}
    if meta.get(META_PROTOCOL_VERSION) != headers.get("mcp-protocol-version"):
        return f"MCP-Protocol-Version header does not match _meta {META_PROTOCOL_VERSION}"
    field = NAMED_METHODS.get(method)
    if field is not None:
        raw = headers.get("mcp-name")
        if raw is None or _decode_header_value(raw) != params.get(field):
            return f"Mcp-Name header is missing or does not match params.{field}"
    return None


def _modern_result(method: str, result: dict[str, Any]) -> dict[str, Any]:
    """Add the fields a 2026-07-28 result carries; legacy results stay as they were."""
    server_info = {"name": SERVER_NAME, "title": SERVER_TITLE, "version": SERVER_VERSION}
    extra: dict[str, Any] = {"resultType": "complete"}
    if method in ("server/discover", "tools/list", "prompts/list"):
        extra.update(ttlMs=LIST_TTL_MS, cacheScope="public")
    meta = {**(result.get("_meta") or {}), META_SERVER_INFO: server_info}
    return {**result, **extra, "_meta": meta}


def _tool_error_result(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": True}


def _handle_tools_call(params: Any, rng: random.Random | None) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise _RpcError(INVALID_PARAMS, "params must be an object")
    name = params.get("name")
    if not isinstance(name, str):
        raise _RpcError(INVALID_PARAMS, "params.name must be a string")
    if name != TOOL_NAME:
        raise _RpcError(INVALID_PARAMS, f"Unknown tool: {name}")
    arguments = params.get("arguments", {})
    if not isinstance(arguments, dict):
        return _tool_error_result("arguments must be an object")
    try:
        payload = draw_spread(
            positions=arguments.get("positions"),
            label=arguments.get("label"),
            rng=rng,
        )
    except ValueError as ve:
        return _tool_error_result(f"Invalid arguments: {ve}")
    return {
        "content": [{"type": "text", "text": format_spread_text(payload)}],
        "structuredContent": payload,
        "isError": False,
    }


def _handle_prompts_get(params: Any) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise _RpcError(INVALID_PARAMS, "params must be an object")
    name = params.get("name")
    if not isinstance(name, str):
        raise _RpcError(INVALID_PARAMS, "params.name must be a string")
    spread = SPREADS_BY_SLUG.get(name)
    if spread is None:
        raise _RpcError(INVALID_PARAMS, f"Unknown prompt: {name}")
    return {
        "description": spread.purpose,
        "messages": [{"role": "user", "content": {"type": "text", "text": _prompt_text(spread)}}],
    }


def dispatch(
    message: dict[str, Any], *, rng: random.Random | None = None, modern: bool = False
) -> dict[str, Any]:
    """Route one validated JSON-RPC request (it has an id) to its result or error.

    `modern` serves a 2026-07-28 request: it adds server/discover and the fields modern
    results carry. Legacy results are unchanged, byte for byte.
    """
    req_id = message["id"]
    method = message.get("method")
    try:
        if modern and method == "server/discover":
            result: dict[str, Any] = {
                "supportedVersions": list(SUPPORTED_PROTOCOL_VERSIONS),
                "capabilities": {"tools": {}, "prompts": {}},
                "instructions": SERVER_INSTRUCTIONS,
            }
        elif method == "initialize":
            params = message.get("params") or {}
            if not isinstance(params, dict):
                params = {}
            result = {
                "protocolVersion": _negotiate_version(params.get("protocolVersion")),
                "capabilities": {
                    "tools": {"listChanged": False},
                    "prompts": {"listChanged": False},
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "title": SERVER_TITLE,
                    "version": SERVER_VERSION,
                },
                "instructions": SERVER_INSTRUCTIONS,
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": [TOOL_DEFINITION]}
        elif method == "tools/call":
            result = _handle_tools_call(message.get("params"), rng)
        elif method == "prompts/list":
            result = {"prompts": [_prompt_definition(spread) for spread in SPREADS]}
        elif method == "prompts/get":
            result = _handle_prompts_get(message.get("params"))
        else:
            raise _RpcError(METHOD_NOT_FOUND, f"Method not found: {method}")
        return _rpc_result(req_id, _modern_result(method, result) if modern else result)
    except _RpcError as e:
        return _rpc_error(req_id, e.code, e.message)


def handle_http(
    method: str, headers: dict[str, str], body: bytes, *, rng: random.Random | None = None
) -> HttpResponse:
    """Run one HTTP request through the MCP checks, in order. `headers` keys are lowercase."""
    verb = (method or "").upper()

    # 1. Origin (DNS-rebinding guard; applies to every method, preflight included; any
    #    origin is valid on a public server)
    if not _is_allowed_origin(headers.get("origin")):
        return _json_response(403, _rpc_error(None, SERVER_ERROR, "Forbidden origin"))

    # 2. OPTIONS preflight
    if verb == "OPTIONS":
        return _empty_response(204)

    # 3. GET, DELETE, or any other non-POST: no SSE stream and no sessions here
    if verb != "POST":
        resp = _json_response(405, _rpc_error(None, SERVER_ERROR, "Method not allowed"))
        return resp._replace(headers={**resp.headers, "Allow": "POST, OPTIONS"})

    # 4. Auth (TAROT_MCP_PUBLIC=1 skips the shared key for /mcp only)
    if os.environ.get(PUBLIC_ENV_VAR) != "1" and not is_authorized(headers.get("authorization")):
        return _json_response(401, _rpc_error(None, SERVER_ERROR, "Unauthorized"))

    # 5. Body size
    if len(body) > MAX_BODY_BYTES:
        return _json_response(413, _rpc_error(None, INVALID_REQUEST, "Request body too large"))

    # 6. JSON / UTF-8 parse (an empty body is a parse error)
    try:
        decoded = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _json_response(400, _rpc_error(None, PARSE_ERROR, "Parse error"))

    # 7. Batch
    if isinstance(decoded, list):
        return _json_response(
            400, _rpc_error(None, INVALID_REQUEST, "Batch requests are not supported")
        )

    # 8. Envelope: must be an object; a client response is accepted and ignored
    if not isinstance(decoded, dict):
        return _json_response(400, _rpc_error(None, INVALID_REQUEST, "Invalid Request"))
    if "method" not in decoded and ("result" in decoded or "error" in decoded):
        return _empty_response(202)
    if decoded.get("jsonrpc") != "2.0" or not isinstance(decoded.get("method"), str):
        return _json_response(
            400, _rpc_error(_echo_id(decoded), INVALID_REQUEST, "Invalid Request")
        )

    # 9. id, when present, must be a string or integer
    if "id" in decoded and not _is_valid_id(decoded["id"]):
        return _json_response(400, _rpc_error(None, INVALID_REQUEST, "Invalid Request"))

    # 10. MCP-Protocol-Version header picks the era. initialize always selects legacy
    #     semantics, so its header is ignored; no header means a legacy client from before
    #     2025-06-18. An unknown version gets the modern UnsupportedProtocolVersionError, which
    #     lists every version this server speaks.
    version_header = headers.get("mcp-protocol-version")
    modern = decoded["method"] != "initialize" and version_header in MODERN_PROTOCOL_VERSIONS
    if (
        decoded["method"] != "initialize"
        and version_header is not None
        and version_header not in SUPPORTED_PROTOCOL_VERSIONS
    ):
        error = _rpc_error(
            _echo_id(decoded), UNSUPPORTED_PROTOCOL_VERSION, "Unsupported protocol version"
        )
        error["error"]["data"] = {
            "supported": list(SUPPORTED_PROTOCOL_VERSIONS),
            "requested": version_header,
        }
        return _json_response(400, error)

    # 10a. Modern requests: Mcp-Method, Mcp-Name and _meta's version must match the body
    if modern and "id" in decoded:
        mismatch = _header_mismatch(decoded, headers)
        if mismatch is not None:
            return _json_response(
                400, _rpc_error(_echo_id(decoded), HEADER_MISMATCH, f"Header mismatch: {mismatch}")
            )

    # 11. Notification (no id): accepted, no body
    if "id" not in decoded:
        return _empty_response(202)

    # 12. Dispatch (a modern method this server lacks is a 404, so a dual-era client can
    #     tell it from a legacy server's 404)
    if modern and decoded["method"] not in MODERN_METHODS:
        return _json_response(
            404,
            _rpc_error(decoded["id"], METHOD_NOT_FOUND, f"Method not found: {decoded['method']}"),
        )
    try:
        payload = dispatch(decoded, rng=rng, modern=modern)
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return _json_response(500, _rpc_error(decoded["id"], INTERNAL_ERROR, "Internal error"))
    return _json_response(200, payload)


def _read_chunked_body(rfile: BufferedIOBase, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        size_line = rfile.readline()
        if not size_line:
            break
        try:
            size = int(size_line.split(b";", 1)[0].strip(), 16)
        except ValueError:
            break
        if size <= 0:
            while True:
                trailer = rfile.readline()
                if not trailer or trailer in (b"\r\n", b"\n"):
                    break
            break
        take = min(size, max(limit - total, 0))
        if take == 0:
            break
        data = rfile.read(take)
        chunks.append(data)
        total += len(data)
        if size > take or total > limit:
            break
        rfile.readline()
    return b"".join(chunks)


def serve(req: BaseHTTPRequestHandler, *, rng: random.Random | None = None) -> None:
    transfer_encoding = (req.headers.get("Transfer-Encoding") or "").lower()
    if "chunked" in transfer_encoding:
        body = _read_chunked_body(req.rfile, MAX_BODY_BYTES + 1)
    else:
        raw_length = req.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
            if length < 0:
                length = 0
        except (TypeError, ValueError):
            length = 0
        body = req.rfile.read(min(length, MAX_BODY_BYTES + 1)) if length > 0 else b""
    headers = {k.lower(): v for k, v in req.headers.items()}
    resp = handle_http(req.command, headers, body, rng=rng)
    req.send_response(resp.status)
    out_headers = dict(resp.headers)
    if "Content-Length" not in out_headers:
        out_headers["Content-Length"] = str(len(resp.body))
    for key, value in out_headers.items():
        req.send_header(key, value)
    req.end_headers()
    req.wfile.write(resp.body)


class handler(BaseHTTPRequestHandler):  # noqa: N801 - Vercel requires this name
    def do_POST(self) -> None:
        serve(self)

    def do_GET(self) -> None:
        serve(self)

    def do_OPTIONS(self) -> None:
        serve(self)

    def do_DELETE(self) -> None:
        serve(self)
