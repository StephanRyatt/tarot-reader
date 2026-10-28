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


def test_license_is_declared():
    data = json.loads((REPO_ROOT / "plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert data["license"] == "MIT"
    assert (REPO_ROOT / "LICENSE").read_text(encoding="utf-8").startswith("MIT License")


# Claude package: .claude-plugin/plugin.json and .mcp.json beside the ChatGPT files


def _load(*parts: str) -> dict:
    return json.loads((REPO_ROOT.joinpath(*parts)).read_text(encoding="utf-8"))


def test_claude_manifest_matches_the_portable_one():
    claude = _load("plugin", ".claude-plugin", "plugin.json")
    portable = _load("plugin", "plugin.json")
    for key in ("name", "version", "description", "license", "homepage", "repository"):
        assert claude[key] == portable[key]
    assert claude["displayName"] == "Tarot Reader"
    for key in ("documentationUrl", "privacyPolicyUrl"):
        assert claude[key].startswith("https://github.com/StephanRyatt/tarot-reader")


def test_claude_icon_is_an_svg_inside_the_plugin():
    icon = _load("plugin", ".claude-plugin", "plugin.json")["icon"]
    path = (REPO_ROOT / "plugin" / icon).resolve()
    assert path.is_relative_to(REPO_ROOT / "plugin")
    assert path.suffix == ".svg"
    assert path.read_text(encoding="utf-8").startswith("<svg")


def test_claude_mcp_json_uses_http_and_the_same_server():
    claude = _load("plugin", ".mcp.json")["mcpServers"]["tarot-reader"]
    portable = _load("plugin", "mcp.json")["mcpServers"]["tarot-reader"]
    assert claude == {"type": "http", "url": portable["url"]}


def test_marketplace_lists_the_plugin_by_its_manifest_name():
    market = _load(".claude-plugin", "marketplace.json")
    assert market["owner"]["name"]
    [entry] = market["plugins"]
    assert entry["name"] == _load("plugin", ".claude-plugin", "plugin.json")["name"]
    assert not entry["source"].startswith("..")
    assert (REPO_ROOT / entry["source"] / ".claude-plugin" / "plugin.json").is_file()


def test_plugin_readme_meets_the_directory_minimum():
    text = (REPO_ROOT / "plugin" / "README.md").read_text(encoding="utf-8")
    assert len(re.sub(r"```.*?```", "", text, flags=re.S).split()) >= 40
    assert "## Data" in text


def test_privacy_policy_exists_where_the_manifest_points():
    url = _load("plugin", ".claude-plugin", "plugin.json")["privacyPolicyUrl"]
    assert url.endswith("/blob/main/docs/PRIVACY.md")
    assert (REPO_ROOT / "docs" / "PRIVACY.md").is_file()
