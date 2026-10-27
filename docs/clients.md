# Connecting clients

The public instance is `https://tarot-reader-omega.vercel.app/mcp`. It needs no key. If you run your own copy, use your own host instead.

---

## Claude

* **Claude Code:** `claude mcp add --transport http tarot-reader https://tarot-reader-omega.vercel.app/mcp`
* **claude.ai:** Settings → Connectors → Add custom connector, paste the URL, and leave authentication off.

---

## ChatGPT

ChatGPT web **Add custom MCP server** uses only the live `/mcp` server (instructions + tool metadata). The `plugin/` skill is for Codex/desktop marketplace packaging, not the web custom-MCP flow.

1. Use the public instance, or deploy your own and confirm `POST https://<project>.vercel.app/mcp` answers `initialize`.
2. If you deploy your own, point `plugin/mcp.json` at your host instead of `https://tarot-reader-omega.vercel.app/mcp`.
3. In ChatGPT, go to Plugins → **+** → **Add custom MCP server**.
4. Set the URL to `https://tarot-reader-omega.vercel.app/mcp` (or your own host), the name to "Tarot Reader", and Authentication to **None**.
5. Accept the risk warning, then choose **Create as a plugin**.
6. Install it, open a new chat, type `@Tarot Reader`, and enter "Do a three-card reading".
7. Refresh the connection on chatgpt.com/plugins after any change to tools or metadata.
8. Vercel Deployment Protection on Preview URLs blocks ChatGPT, so use the production URL or turn protection off.

To bundle the skill for ChatGPT after creating the custom MCP connection, use `@plugin-creator` with the `plugin_asdk_app…` ID (it produces `.app.json` / apps mapping). Installing both the custom server **and** a desktop package that points at the same `mcp.json` URL registers the server twice — pick one.

---

## Codex and the ChatGPT desktop app

`plugin/mcp.json` points at the public instance. If you deploy your own, change the URL there first.

For a bearer token, Codex `~/.codex/config.toml` can take (check against current Codex docs):

```toml
[mcp_servers.tarot-reader]
url = "https://<project>.vercel.app/mcp"  # your own deployment, if it requires a key
bearer_token_env_var = "TAROT_API_KEY"
```

Alternatively, a local, uncommitted copy of `mcp.json` can add `"headers": {"Authorization": "Bearer <key>"}`. The schema allows `headers`, but environment-variable expansion is not specified, so do not commit it.

Local install through a personal marketplace: `~/.agents/plugins/marketplace.json` with an entry whose `source.path` points at a copy of `plugin/`, plus `policy` and `category` (see the Agent Plugins docs). Then restart the ChatGPT desktop app.

---

## OpenAI platform status (as of Oct 2026)

* Legacy ChatGPT plugins (`/.well-known/ai-plugin.json`) shut down in April 2024. This repo deliberately does not ship one.
* Custom GPTs retire on **[11 Dec 2026](https://help.openai.com/en/articles/20001519-custom-gpt-retirement-and-migration-faq)**, and Actions do not migrate automatically.
* Today's "ChatGPT Plugins" are MCP servers plus an optional `plugin.json` package.
* The Custom GPT Action on `POST /api/tarot` keeps working until retirement.
