# 0008: Speak both MCP eras, and accept any Origin on the public server

**Status:** accepted, November 2026

## Context

The plugin failed to connect from the ChatGPT iOS app. Two gaps could each cause it:

* **Origin.** `/mcp` answered `403` to every browser `Origin` that wasn't localhost, including
  `https://chatgpt.com`, OpenAI's widget sandbox, and `null`, which web views on iOS can send. Requests without an
  `Origin` worked, so server-side clients connected and app clients that set one did not.
* **Protocol version.** MCP 2026-07-28 drops the `initialize` handshake. A modern client sends the version in the
  `MCP-Protocol-Version` header and in each request's `_meta`, and the server must answer `server/discover`. The
  server only knew 2025-11-25 and earlier, so it rejected modern requests with a `400`. Clients that fall back to
  `initialize` still connected; a client that speaks only 2026-07-28 could not. The official Python SDK 2.3 shows
  both: its default mode fell back and worked, and its pinned 2026-07-28 mode failed against production.

The ChatGPT app's own requests aren't visible to us, so we fixed both rather than guess which one it hit.

## Decision

* **Any Origin when `/mcp` is public.** DNS rebinding lets a web page reach a server that trusts its network
  position, such as one on localhost. A server with `TAROT_MCP_PUBLIC=1` trusts nothing about the caller: anyone
  can call it directly, it holds no data and sends `Access-Control-Allow-Origin: *`. On Vercel a rebound request
  can't reach it either, because Vercel routes by `Host`. So the check protects nothing there and only blocks app
  clients. Without the public flag the check is unchanged: no `Origin`, localhost, or `TAROT_MCP_ALLOWED_ORIGINS`.
* **Dual-era server.** `initialize` keeps legacy semantics for 2024-11-05 to 2025-11-25. A request whose
  `MCP-Protocol-Version` header is 2026-07-28 is served as modern:
  * `Mcp-Method`, `Mcp-Name` (for `tools/call` and `prompts/get`, Base64 sentinel decoded) and `_meta`'s
    `io.modelcontextprotocol/protocolVersion` must match the body, or `400` with `HeaderMismatch` (`-32020`).
  * `server/discover`, `tools/list`, `tools/call`, `prompts/list` and `prompts/get` are served. Results carry
    `resultType: "complete"` and `_meta` `io.modelcontextprotocol/serverInfo`; list and discover results add
    `ttlMs` (one hour) and `cacheScope: "public"`. Any other method is `404` with `-32601`.
  * An unknown version gets `400` with `UnsupportedProtocolVersionError` (`-32022`) naming every supported
    version, so any client can pick one. This replaces the earlier `-32600`.
* Legacy results stay byte for byte as they were, so the model-facing text the evals use doesn't change.

## Consequences

* ChatGPT's apps can call the public server whatever `Origin` they send, and modern-only clients connect.
* A self-hosted server run with `TAROT_MCP_PUBLIC=1` on localhost loses rebinding protection. A page could then
  draw cards through it, which exposes nothing. Leave the flag off for local use.
* A modern client that skips `server/discover` never sees `SERVER_INSTRUCTIONS`; the tool description carries the
  same rules (ADR 0004).
* Modern requests are checked strictly, as the spec requires. A client that mislabels its headers gets a modern
  error and won't fall back to `initialize`.
* Revisit when clients drop the legacy era, or if the server ever holds anything per user (ADR 0002).
