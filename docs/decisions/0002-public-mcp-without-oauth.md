# 0002: Public `/mcp` without OAuth

**Status:** accepted, October 2026

## Context

ChatGPT's custom MCP servers connect with Authentication set to None or OAuth; they can't send a static API key.
The server returns random draws from a public deck. There are no accounts, no user data and nothing to protect
except availability. OAuth would add an authorization server, discovery endpoints and token handling for no gain
to the user.

## Decision

* `TAROT_MCP_PUBLIC=1` opens `/mcp` only. `TAROT_API_KEY` still guards the REST endpoint, and a test checks the
  flag never opens it.
* A `401` carries no `WWW-Authenticate` header, so MCP clients don't start OAuth discovery against a server that
  has none.
* Abuse is bounded at the edge, not in code: a Vercel Firewall rule allows 60 requests per minute per IP and
  answers 429 above that. The free plan's hard usage cap is the backstop, so the worst case is downtime, not a bill.
* The `Origin` check still applies, so a public server can't be used for DNS rebinding from a browser.

## Consequences

* Anyone can connect in seconds, which is the point of a demo.
* ChatGPT and Claude connect from shared data-centre IPs, so the per-IP limit is effectively per client. It's set
  well above one reading's 3–5 requests.
* Revisit this if the server ever stores anything per user.
