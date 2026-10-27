"""Plugin package files and vercel.json have the shape their consumers expect."""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

ALLOWED_PLUGIN_KEYS = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}

PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def test_plugin_json():
    data = json.loads((REPO_ROOT / "plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert data["$schema"] == PLUGIN_SCHEMA
    assert NAME_RE.fullmatch(data["name"])
    assert len(data["name"]) <= 64
    assert data["version"]
    assert data["description"]
    assert set(data) <= ALLOWED_PLUGIN_KEYS
    assert data["extensions"]["com.openai"]["interface"]["displayName"] == "Tarot Reader"


def test_mcp_json():
    data = json.loads((REPO_ROOT / "plugin" / "mcp.json").read_text(encoding="utf-8"))
    assert data["$schema"] == MCP_SCHEMA
    server = data["mcpServers"]["tarot-reader"]
    assert set(server) == {"type", "url"}
    assert server["type"] == "streamable-http"
    assert server["url"].startswith("https://")
    assert server["url"].endswith("/mcp")


def test_skill_md():
    skill_path = REPO_ROOT / "plugin" / "skills" / "tarot-reading" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    assert text.startswith("---")
    parts = text.split("---", 2)
    assert len(parts) >= 3
    frontmatter = {}
    for line in parts[1].strip().splitlines():
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip()
    assert frontmatter["name"] == "tarot-reading"
    assert frontmatter["name"] == skill_path.parent.name
    assert frontmatter["description"]
    assert "draw_tarot_spread" in frontmatter["description"]
    assert "draw_tarot_spread" in parts[2]


def test_vercel_json():
    data = json.loads((REPO_ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert {"source": "/mcp", "destination": "/api/mcp"} in data["rewrites"]
    assert {"source": "/mcp/", "destination": "/api/mcp"} in data["rewrites"]
    assert "builds" not in data
    assert "functions" not in data
