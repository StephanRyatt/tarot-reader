# Running your own copy

Everything here is for running or deploying your own instance. To just use the server, see
[Try it](../README.md#try-it).

---

## Project structure

```
tarot-reader/
├─ api/
│  ├─ tarot.py          # REST: POST /api/tarot
│  └─ mcp.py            # MCP:  POST /api/mcp  (rewritten from /mcp)
├─ .claude-plugin/marketplace.json   # lets Claude install plugin/ from this repo
├─ plugin/                   # plugin package for Claude, ChatGPT and Codex
│  ├─ .claude-plugin/plugin.json     # Claude manifest
│  ├─ .mcp.json              # Claude: points at the public instance (type http)
│  ├─ plugin.json            # ChatGPT/Codex manifest
│  ├─ mcp.json               # ChatGPT/Codex: same server (type streamable-http)
│  ├─ README.md / icon.svg
│  └─ skills/tarot-reading/  # SKILL.md and references/spreads.md
├─ tests/
│  ├─ conftest.py           # clean env per test, throwaway local server
│  ├─ test_logic.py         # engine: validation, invariants, fairness
│  ├─ test_http.py          # REST contract
│  ├─ test_mcp.py           # MCP checks, dispatch, socket adapter
│  ├─ test_dev_server.py    # local routing mirrors vercel.json
│  ├─ test_consistency.py   # instructions, tool, skill and docs agree
│  └─ test_plugin_package.py
├─ docs/                     # API reference, clients, self-hosting, decisions
├─ dev_server.py             # local server that routes like vercel.json
├─ vercel.json               # rewrites only
├─ ruff.toml / mypy.ini     # lint, format and type-check config
├─ requirements-dev.txt     # pinned dev tools; runtime is stdlib-only
├─ CLAUDE.md                 # brief for coding agents
└─ LICENSE                   # MIT
```

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

## Deployment to Vercel

### Git-based deployment (recommended)

1. Fork or push the repository to GitHub.
2. In Vercel: **New Project → Import Git Repository → Deploy**. There is no build step.
3. If ChatGPT or Claude will connect, set **Deployment Protection** to Standard, so production is reachable and
   previews stay private.
4. Optionally add a Firewall rate-limit rule on paths starting with `/mcp` and `/api/mcp`. The public instance
   allows 60 requests per minute per IP and answers 429 above that.

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
