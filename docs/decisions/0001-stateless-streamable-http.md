# 0001: Stateless, JSON-only Streamable HTTP

**Status:** accepted, October 2026

## Context

MCP's Streamable HTTP transport allows sessions (`Mcp-Session-Id`), server-sent event streams, and server-initiated
requests. This server has one tool that answers in milliseconds and keeps no state. It runs as a Vercel Python
function, which handles one request and exits.

## Decision

Serve every `POST /mcp` as a standalone JSON-RPC request with an `application/json` response. Issue no session ids
and open no SSE streams. `GET` and `DELETE` return `405` with `Allow: POST, OPTIONS`. Batches are rejected
(protocol version 2025-06-18 removed JSON-RPC batching).

## Consequences

* Any instance can answer any request, so scaling and cold starts are simple, with nothing to store.
* The server can't push notifications or progress, which one fast tool call doesn't need.
* `handle_http()` is a pure function of method, headers and body, so every status code is unit-tested without a
  socket.
