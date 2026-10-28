# 0005: Freeze, then retire, the REST endpoint

**Status:** accepted, October 2026

## Context

`POST /api/tarot` was built for a Custom GPT Action. OpenAI retires Custom GPTs on 11 December 2026, and Actions
don't migrate to the MCP-based replacement.

## Decision

* Freeze the REST contract (bodies, status codes, `401`/`405`, no CORS or `OPTIONS`) and pin it in
  `tests/test_http.py`.
* Allow only safety fixes, such as no longer echoing exception text in error bodies.
* Put new work into `/mcp` only.
* Remove the endpoint and its tests after the retirement date.

## Consequences

* The existing GPT keeps working until OpenAI turns it off, at no ongoing cost.
* Both interfaces share `draw_spread()`, so removing REST deletes a thin adapter, not logic.
