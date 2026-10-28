# API reference

Two interfaces share one engine, `draw_spread()` in [`api/tarot.py`](../api/tarot.py), so both have the same
validation rules and limits.

* **MCP** at `/mcp` (also `/api/mcp`): the main interface. Public instance: `https://tarot-reader-omega.vercel.app/mcp`.
* **REST** at `POST /api/tarot`: the legacy Custom GPT Action. Its contract is frozen until it's removed after
  Custom GPTs retire on 11 Dec 2026 ([decision 0005](decisions/0005-sunset-rest-endpoint.md)).

---

## Request and response (both interfaces)

### Request (REST body, or MCP tool arguments)

`Content-Type: application/json`

```json
{
  "positions": ["Past", "Present", "Future"],
  "label": "3-card"
}
```

Rules:

* `positions` must be a non-empty array of non-empty strings
* `positions` must be unique
* maximum positions: 30
* each position name: maximum 100 characters (after trimming whitespace)
* `label` is optional; maximum length: 200 characters

---

### Response (200)

```json
{
  "draws": {
    "Past": { "card": "Knight of Cups", "orientation": "upright" },
    "Present": { "card": "Justice", "orientation": "reversed" },
    "Future": { "card": "The Fool", "orientation": "upright" }
  },
  "meta": { "label": "3-card" }
}
```

### REST error responses

* `400` — invalid JSON or validation error
* `401` — Unauthorized (when auth is enabled)
* `405` — Method not allowed

---

## MCP server

* **Endpoint:** `POST https://<host>/mcp` (also `POST https://<host>/api/mcp`)
* **Transport:** stateless Streamable HTTP, JSON-response mode (`Content-Type: application/json`)
* **Supported methods:** `initialize`, `ping`, `tools/list`, `tools/call`, `prompts/list`, `prompts/get`
* **Protocol version:** default `2025-11-25`; echo `2025-06-18`, `2025-03-26`, or `2024-11-05` if the client asks for one of those; anything else falls back to `2025-11-25`
* **Tool:** `draw_tarot_spread` — same input as the REST API (`positions`, optional `label`) and the same `draws` / `meta` output as `structuredContent`, plus a readable `content` text block in position order
* **Prompts:** one per named spread (`card-of-the-day`, `daily-alignment`, `daily-focus`, `weekly-path`,
  `weekly-evolution`, `past-present-future`, `decision`, `celtic-cross`). They take no arguments, so nothing about the
  user reaches the server. `prompts/get` returns one user message that asks for that reading and gives the exact
  positions, label and position meanings. Clients show them in their own UI: claude.ai and Claude Desktop under
  "Add files, connectors, and more", Claude Code as slash commands. The same spreads ship in the plugin skill's
  `references/spreads.md`, and a test keeps their positions, labels and meanings identical.

### Status codes

* `200` — JSON-RPC request result or protocol error
* `202` — notification or client response (empty body)
* `204` — CORS preflight (`OPTIONS`)
* `400` — parse error, batch, invalid request, or an unsupported `MCP-Protocol-Version` header
* `401` — Unauthorized (JSON-RPC body, no `WWW-Authenticate`)
* `403` — `Origin` header from a browser origin that is not allowed (see below)
* `405` — `GET` / `DELETE` (`Allow: POST, OPTIONS`)
* `413` — request body larger than 64 KiB
* `500` — unexpected internal error

---

## Authentication

Authentication is optional and controlled via an environment variable.

* Environment variable: `TAROT_API_KEY`
* Header format:

```
Authorization: Bearer <key>
```

### Behavior

* If `TAROT_API_KEY` **is not set** → authentication is disabled (all requests allowed)
* If `TAROT_API_KEY` **is set** → requests must include a matching Bearer token
* `TAROT_API_KEY` protects **both** `/api/tarot` and `/mcp` unless MCP is opted out below

### Shared-key trade-off

ChatGPT web custom MCP servers use Authentication = **None** and cannot send API keys. Set `TAROT_MCP_PUBLIC=1` on the deployment ChatGPT uses so `/mcp` is public while `/api/tarot` can stay keyed. The cards are random public draws, not sensitive data.

OAuth is not implemented.

### Browser origins (`/mcp` only)

The MCP spec requires servers to check the `Origin` header to block DNS-rebinding attacks. `/mcp` allows:

* requests with no `Origin` (server-side clients such as ChatGPT and Claude)
* local pages on `localhost`, `127.0.0.1` or `[::1]` (MCP Inspector)
* origins listed in `TAROT_MCP_ALLOWED_ORIGINS`, comma-separated (for example `https://app.example.com`), or any origin when it is `*`

Any other `Origin` gets `403 Forbidden`.
