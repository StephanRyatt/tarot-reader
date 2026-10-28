# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

A small Python tarot draw server. It shuffles a 78-card Rider-Waite deck (packet flips, a cut, reversals) and
draws one card per named position. Two interfaces share one engine, `draw_spread()` in `api/tarot.py`:

- `POST /api/tarot`: plain REST, used by a Custom GPT Action.
- `POST /mcp` (rewritten to `/api/mcp` by `vercel.json`): stateless Streamable HTTP MCP server with one tool,
  `draw_tarot_spread`. Handler in `api/mcp.py`.

`plugin/` is the plugin package: `.claude-plugin/plugin.json` and `.mcp.json` (type `http`) for Claude, `plugin.json`
and `mcp.json` (type `streamable-http`) for ChatGPT and Codex, and one skill with `references/spreads.md`.
`.claude-plugin/marketplace.json` at the root makes the repo a Claude marketplace. `tests/test_plugin_package.py`
keeps both manifests and both server files in step. `README.md` is the portfolio front page
(pitch, Try it, architecture, decisions); keep reference material out of it. `docs/API.md` has the full contract and
status codes, `docs/clients.md` the client connection steps, `docs/self-hosting.md` local testing and deployment, and
`docs/decisions/` the decision records. Do not duplicate them here.

## Commands

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt   # pinned dev tools; runtime has no dependencies
pytest                                # whole suite, under 2s (pytest.ini sets pythonpath=.)
pytest tests/test_mcp.py -k initialize   # one file / one test by keyword
pytest tests/test_http.py::test_invalid_json_returns_400   # one test by node id
python dev_server.py                  # http://127.0.0.1:8000, MCP at /mcp
ruff check . && ruff format --check . # lint and format (ruff.toml)
mypy                                  # strict, on api/ and dev_server.py (mypy.ini)
pip install -r requirements-evals.txt && python -m evals   # behaviour evals; needs ANTHROPIC_API_KEY, costs money
```

`evals/` runs scripted conversations through a real model with the shipped skill and tool (`docs/evals.md`). Its
grading is tested offline in `tests/test_evals_*.py`; the live run is never part of CI. When you change the skill or
the tool text, check whether a case or check in `evals/` needs to change too.

CI (`.github/workflows/ci.yml`) runs ruff, mypy and pytest with coverage (fails under 95%) on Python 3.12 for
every push and PR. Deployment is Vercel, git-based; there is no build step. There is no `pyproject.toml` on purpose:
Vercel's Python runtime changes how it installs when one exists, so tool config lives in `ruff.toml` and `mypy.ini`.

## Architecture

- **Engine** (`api/tarot.py`): `draw_spread(positions=, label=, rng=)` is pure. It validates, builds the deck, applies
  packet flips, shuffles, cuts and draws. It raises `ValueError` on bad input. `rng=None` means
  `random.SystemRandom()`; tests pass a seeded `random.Random` for determinism. Both interfaces call it, so
  validation rules and limits (`MAX_POSITIONS`) live only here.
- **REST** (`api/tarot.py`): `handler` is a `BaseHTTPRequestHandler` subclass, which is the shape Vercel's Python
  runtime expects. The class name `handler` and the file path matter for deployment. It only implements `POST` and
  `GET` (405). `ValueError` and every other exception become a 400.
- **MCP** (`api/mcp.py`): `handle_http(method, headers, body)` is the transport-agnostic core. It takes plain values and
  returns an `HttpResponse`, applying a fixed numbered sequence of checks (Origin, OPTIONS, non-POST, auth, size,
  parse, batch, envelope, id, `MCP-Protocol-Version` header, notification, dispatch). Keep that order when editing,
  because `tests/test_mcp.py` pins the status codes. `dispatch()` does the JSON-RPC method routing, and `serve()` adapts a `BaseHTTPRequestHandler` to `handle_http`
  (including chunked bodies and the 64 KiB cap). The `try/except ImportError` at the top lets the module import as
  `api.tarot` or as a bare `tarot`.
- **Dev server** (`dev_server.py`): `DevHandler` subclasses the REST `handler` and sends `/mcp` and `/api/mcp` to
  `serve_mcp`. Any other path, including `/`, hits the REST logic. This mimics Vercel's rewrites locally.
- **Tool metadata is part of the product.** `SERVER_INSTRUCTIONS`, `TOOL_DEFINITION` and
  `plugin/skills/tarot-reading/SKILL.md` tell the model never to invent cards, to draw the spread once per reading,
  and to draw at most one clarifier, only with the user's consent (ADR 0006). Keep the three consistent when changing
  one. `SERVER_INSTRUCTIONS` must stay under 512 characters, so fuller guidance goes in the tool description and the
  skill. Named spreads live in `SPREADS` in `api/mcp.py`, served as MCP prompts, and are mirrored in
  `plugin/skills/tarot-reading/references/spreads.md`; `tests/test_consistency.py` fails if their positions,
  labels or meanings differ.

## Rules

- Keep `POST /api/tarot` behaviour unchanged: bodies, status codes, 401/405, and no CORS or `OPTIONS` handler on the
  REST endpoint. `tests/test_http.py` pins all of it. Error messages must never include exception text.
- Auth is shared via `is_authorized()` in `api/tarot.py`. `TAROT_API_KEY` set means a Bearer token is required.
  `TAROT_MCP_PUBLIC=1` opts only `/mcp` out; `/api/tarot` stays keyed (`test_mcp_public_does_not_open_tarot_api`).
  `.env.local` is gitignored. `TAROT_MCP_ALLOWED_ORIGINS` widens the `/mcp` Origin allowlist (default: no Origin
  or localhost only).
- Limits (`MAX_POSITIONS`, `MAX_POSITION_LENGTH`, `MAX_LABEL_LENGTH`) live in `api/tarot.py`; the MCP input schema
  reads them. `tests/test_consistency.py` checks the skill, instructions and `docs/API.md` still agree.
- `tests/conftest.py` clears the `TAROT_*` env vars before every test and provides `live_server(HandlerClass)`.
- `plugin/mcp.json` points at the public production instance, `https://tarot-reader-omega.vercel.app/mcp`, which runs with
  `TAROT_MCP_PUBLIC=1` behind a Vercel Firewall rate limit (60 requests/min per IP on `/mcp` and `/api/mcp`).
  `test_plugin_package.py` only requires an `https://` URL ending in `/mcp`.
- `vercel.json` must contain only `rewrites`; a test fails if `builds` or `functions` is added.
- Custom GPTs retire on 11 Dec 2026 and Actions do not migrate, so avoid investing in the REST/GPT path.
- Runtime stays dependency-free (stdlib only); `requirements.txt` is empty on purpose.
