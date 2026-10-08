# Tarot Reader

A lightweight Tarot draw server with two interfaces over the same draw engine:

* `POST /api/tarot` — Custom GPT Action / plain REST (unchanged)
* `https://<host>/mcp` — MCP server for ChatGPT Plugins, Codex, and other MCP clients

Both shuffle a full 78-card Rider-Waite deck (with packet flips, a cut, and reversals) and draw one real random card per named position.

---

## What changed

This repo now exposes the existing `draw_spread()` function as one MCP tool, `draw_tarot_spread`, over stateless Streamable HTTP.

New and updated pieces:

* `api/mcp.py` — MCP JSON-RPC handler (`POST /api/mcp`, rewritten from `/mcp`)
* `vercel.json` — rewrite `/mcp` and `/mcp/` → `/api/mcp`
* `plugin/` — portable plugin package (`plugin.json`, `mcp.json`, skill)
* `dev_server.py` — routes `/mcp` and `/api/mcp` to the MCP handler; every other POST still draws cards
* `is_authorized()` in `api/tarot.py` — shared Bearer check used by both handlers

There are no breaking changes to `POST /api/tarot` (same bodies, status codes, and 401/405 behaviour; no CORS or OPTIONS added on the REST endpoint).

---

## Platform status (as of Oct 2026)

* Legacy ChatGPT plugins (`/.well-known/ai-plugin.json`) shut down in April 2024. This repo deliberately does not ship one.
* Custom GPTs retire on **[11 Dec 2026](https://help.openai.com/en/articles/20001519-custom-gpt-retirement-and-migration-faq)**, and Actions do not migrate automatically.
* Today's "ChatGPT Plugins" are MCP servers plus an optional `plugin.json` package.
* The Custom GPT Action on `POST /api/tarot` keeps working until retirement.

---

## Project structure

```
tarot-reader/
├─ api/
│  ├─ tarot.py          # REST: POST /api/tarot
│  └─ mcp.py            # MCP:  POST /api/mcp  (rewritten from /mcp)
├─ plugin/
│  ├─ plugin.json
│  ├─ mcp.json
│  └─ skills/tarot-reading/SKILL.md
├─ tests/
│  ├─ test_logic.py
│  ├─ test_http.py
│  ├─ test_mcp.py
│  ├─ test_dev_server.py
│  └─ test_plugin_package.py
├─ dev_server.py
├─ vercel.json
├─ requirements-dev.txt
└─ .gitignore
```

---

## API contract

### Request (POST)

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

### Error responses

* `400` — invalid JSON or validation error
* `401` — Unauthorized (when auth is enabled)
* `405` — Method not allowed

---

## MCP server

* **Endpoint:** `POST https://<host>/mcp` (also `POST https://<host>/api/mcp`)
* **Transport:** stateless Streamable HTTP, JSON-response mode (`Content-Type: application/json`)
* **Supported methods:** `initialize`, `ping`, `tools/list`, `tools/call`
* **Protocol version:** default `2025-11-25`; echo `2025-06-18`, `2025-03-26`, or `2024-11-05` if the client asks for one of those; anything else falls back to `2025-11-25`
* **Tool:** `draw_tarot_spread` — same input as the REST API (`positions`, optional `label`) and the same `draws` / `meta` output as `structuredContent`, plus a readable `content` text block in position order

### Status codes

* `200` — JSON-RPC request result or protocol error
* `202` — notification or client response (empty body)
* `204` — CORS preflight (`OPTIONS`)
* `400` — parse error, batch, or invalid request
* `401` — Unauthorized (JSON-RPC body, no `WWW-Authenticate`)
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

---

## Local development setup

### Local secret file (recommended)

Create `.env.local` (do **not** commit):

```bash
export TAROT_API_KEY='your-long-secret'
```

Ensure `.env.local` is listed in `.gitignore`.

---

## Local testing (no Vercel CLI required)

### 1) Run the dev server

`dev_server.py` serves the REST API on any non-MCP path and MCP at `/mcp` and `/api/mcp`.

Start the server (Terminal 1):

```bash
source .env.local   # optional, only if auth should be enabled locally
python3 dev_server.py
```

---

### 2) Test the REST API with curl (Terminal 2)

#### When authentication is enabled

**No Authorization header (expected: 401):**

```bash
curl -i -X POST "http://127.0.0.1:8000" \
  -H "Content-Type: application/json" \
  -d '{"positions":["Past","Present","Future"]}'
```

**Wrong token (expected: 401):**

```bash
curl -i -X POST "http://127.0.0.1:8000" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer wrong" \
  -d '{"positions":["Past","Present","Future"]}'
```

**Correct token (expected: 200):**

```bash
source .env.local
curl -i -X POST "http://127.0.0.1:8000" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TAROT_API_KEY" \
  -d '{"positions":["Past","Present","Future"],"label":"3-card"}'
```

> Note: If you do not `source .env.local` in the curl terminal, `$TAROT_API_KEY` expands to an empty string and authentication will fail.

#### When authentication is disabled

```bash
curl -i -X POST "http://127.0.0.1:8000" \
  -H "Content-Type: application/json" \
  -d '{"positions":["Past","Present","Future"]}'
```

---

### 3) Test the MCP server with curl

Leave `TAROT_API_KEY` unset in the server process (or omit the header only if auth is disabled).

**initialize:**

```bash
curl -s -X POST "http://127.0.0.1:8000/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
```

**tools/list:**

```bash
curl -s -X POST "http://127.0.0.1:8000/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
```

**tools/call:**

```bash
curl -s -X POST "http://127.0.0.1:8000/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"draw_tarot_spread","arguments":{"positions":["Past","Present","Future"],"label":"3-card"}}}'
```

---

### 4) MCP Inspector

```bash
npx @modelcontextprotocol/inspector
```

Choose Streamable HTTP and enter `http://127.0.0.1:8000/mcp`. You should see `initialize` instructions, one tool (`draw_tarot_spread`), and both a good and a bad tool call.

To expose the local server to ChatGPT or a remote Inspector:

```bash
ngrok http 8000
```

Then use `https://<id>.ngrok.app/mcp`.

---

## Connecting in ChatGPT

ChatGPT web **Add custom MCP server** uses only the live `/mcp` server (instructions + tool metadata). The `plugin/` skill is for Codex/desktop marketplace packaging, not the web custom-MCP flow.

1. Deploy and confirm `POST https://<project>.vercel.app/mcp` answers `initialize`.
2. Replace `YOUR-PROJECT` in `plugin/mcp.json` with your real Vercel host.
3. In ChatGPT, go to Plugins → **+** → **Add custom MCP server**.
4. Set the URL to `https://<project>.vercel.app/mcp`, the name to "Tarot Reader", and Authentication to **None**.
5. Accept the risk warning, then choose **Create as a plugin**.
6. Install it, open a new chat, type `@Tarot Reader`, and enter "Do a three-card reading".
7. Refresh the connection on chatgpt.com/plugins after any change to tools or metadata.
8. Vercel Deployment Protection on Preview URLs blocks ChatGPT, so use the production URL or turn protection off.

To bundle the skill for ChatGPT after creating the custom MCP connection, use `@plugin-creator` with the `plugin_asdk_app…` ID (it produces `.app.json` / apps mapping). Installing both the custom server **and** a desktop package that points at the same `mcp.json` URL registers the server twice — pick one.

---

## Codex / desktop

Replace `YOUR-PROJECT` in `plugin/mcp.json` with your real Vercel host before pointing clients at that URL.

For a bearer token, Codex `~/.codex/config.toml` can take (check against current Codex docs):

```toml
[mcp_servers.tarot-reader]
url = "https://<project>.vercel.app/mcp"
bearer_token_env_var = "TAROT_API_KEY"
```

Alternatively, a local, uncommitted copy of `mcp.json` can add `"headers": {"Authorization": "Bearer <key>"}`. The schema allows `headers`, but environment-variable expansion is not specified, so do not commit it.

Local install through a personal marketplace: `~/.agents/plugins/marketplace.json` with an entry whose `source.path` points at a copy of `plugin/`, plus `policy` and `category` (see the Agent Plugins docs). Then restart the ChatGPT desktop app.

---

## Deployment to Vercel

### Git-based deployment (recommended)

1. Push the repository to GitHub
2. In Vercel: **New Project → Import Git Repository → Deploy**

`vercel.json` rewrites `/mcp` and `/mcp/` to `/api/mcp`. Both URLs work:

```
POST https://<project>.vercel.app/api/tarot
POST https://<project>.vercel.app/mcp
POST https://<project>.vercel.app/api/mcp
```

---

### Enable authentication in production

In the Vercel dashboard:

* Project → Settings → Environment Variables
* Add `TAROT_API_KEY` with your secret value
* Apply to **Production** (and optionally **Preview**)
* Redeploy the project

Set `TAROT_MCP_PUBLIC=1` on the deployment ChatGPT web will use (Auth = None) so `/mcp` is public while `/api/tarot` can keep `TAROT_API_KEY`.

---

## Production test

REST:

```bash
curl -i -X POST "https://<project>.vercel.app/api/tarot" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <YOUR_PROD_KEY>" \
  -d '{"positions":["Past","Present","Future"]}'
```

MCP initialize:

```bash
curl -s -X POST "https://<project>.vercel.app/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
```
