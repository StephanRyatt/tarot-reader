# 0003: Standard library only at runtime

**Status:** accepted, January 2026, and kept when MCP was added in October 2026

## Context

The server parses JSON, checks a header, shuffles a list and writes a response. Vercel's Python runtime installs
whatever `requirements.txt` or `pyproject.toml` declares.

## Decision

Use only the Python standard library at runtime. `requirements.txt` is empty on purpose. The MCP protocol layer is
written by hand (about 400 lines) rather than pulled from the MCP SDK. Dev tools (pytest, ruff, mypy) are pinned in
`requirements-dev.txt` and never deployed. There is no `pyproject.toml`, because its presence changes how Vercel
installs the project, so tool config lives in `ruff.toml` and `mypy.ini`.

## Consequences

* There is no dependency supply chain, nothing for Dependabot to patch in production, and cold starts are fast.
* Protocol changes are the project's own job. A focused test file pins every check, and the transport spec is
  followed explicitly (Origin, `MCP-Protocol-Version`, notifications, batches).
* If the tool surface grows (resources, prompts, streaming), moving to the official SDK becomes the better trade.
