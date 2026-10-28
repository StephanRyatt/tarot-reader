# Connecting clients

The public instance is `https://tarot-reader-omega.vercel.app/mcp`. It needs no key. If you run your own copy, use your own host instead.

---

## Claude

The full product is the plugin: the server plus the counseling skill and the spread library. A connector on its own
gives Claude the tool and its description, but not the skill.

* **Plugin, claude.ai or Claude Desktop:** Customize → Plugins → Add → Add marketplace, and enter
  `StephanRyatt/tarot-reader`. Then install Tarot Reader and connect its server on the plugin's **Connectors** tab;
  it needs no authentication. Skills need **Code execution and file creation** on (Settings → Capabilities).
* **Plugin, from a local copy:** zip the `plugin/` folder (`cd plugin && zip -r ../tarot-reader-plugin.zip .`) and
  upload it under Customize → Plugins → Add → Upload plugin. Remove it before installing from the marketplace, so the
  skill and tool aren't loaded twice.
* **Plugin, Claude Code:** `/plugin marketplace add StephanRyatt/tarot-reader`, then
  `/plugin install tarot-reader@tarot-reader`. A plugin installed on claude.ai also syncs to Claude Code.
* **Connector only, Claude Code:** `claude mcp add --transport http tarot-reader https://tarot-reader-omega.vercel.app/mcp`
* **Connector only, claude.ai:** Customize → Connectors → Add custom connector, paste the URL, and leave
  authentication off. Don't add it as well as the plugin.

The named spreads are MCP prompts. In claude.ai and Claude Desktop, pick one under "Add files, connectors, and more"
→ Connectors → Tarot Reader. In Claude Code they are slash commands: type `/` and look for the Tarot Reader entries marked (MCP).

---

## ChatGPT

ChatGPT web **Add custom MCP server** uses only the live `/mcp` server (instructions + tool metadata), so ChatGPT gets the tool but not the counseling skill or the spread library. The `plugin/` skill is for Codex/desktop marketplace packaging, not the web custom-MCP flow.

1. Use the public instance, or deploy your own and confirm `POST https://<project>.vercel.app/mcp` answers `initialize`.
2. If you deploy your own, point `plugin/mcp.json` and `plugin/.mcp.json` at your host instead of `https://tarot-reader-omega.vercel.app/mcp`.
3. In ChatGPT, go to Plugins → **+** → **Add custom MCP server**.
4. Set the URL to `https://tarot-reader-omega.vercel.app/mcp` (or your own host), the name to "Tarot Reader", and Authentication to **None**.
5. Accept the risk warning, then choose **Create as a plugin**.
6. Install it, open a new chat, type `@Tarot Reader`, and enter "Do a three-card reading".
7. Refresh the connection on chatgpt.com/plugins after any change to tools or metadata.
8. Vercel Deployment Protection on Preview URLs blocks ChatGPT, so use the production URL or turn protection off.

To bundle the skill for ChatGPT after creating the custom MCP connection, use `@plugin-creator` with the `plugin_asdk_app…` ID (it produces `.app.json` / apps mapping). Installing both the custom server **and** a desktop package that points at the same `mcp.json` URL registers the server twice — pick one.

---

## Codex and the ChatGPT desktop app

> These steps are documented but have not been tested end to end with the current release.

`plugin/mcp.json` (and `plugin/.mcp.json` for Claude) point at the public instance. If you deploy your own, change the URL in both first.

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
