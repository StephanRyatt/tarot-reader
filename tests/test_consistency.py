"""The model sees the same rules in three places (server instructions, tool definition and
the plugin skill), and people read them in docs/API.md. These tests keep them in step."""

import json
import re
from pathlib import Path

from api.mcp import SERVER_INSTRUCTIONS, SERVER_VERSION, TOOL_DEFINITION, TOOL_NAME
from api.tarot import MAX_POSITIONS

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = (REPO_ROOT / "plugin" / "skills" / "tarot-reading" / "SKILL.md").read_text("utf-8")
API_DOCS = (REPO_ROOT / "docs" / "API.md").read_text("utf-8")
PLUGIN = json.loads((REPO_ROOT / "plugin" / "plugin.json").read_text("utf-8"))


def test_plugin_version_matches_server_version():
    assert PLUGIN["version"] == SERVER_VERSION


def test_tool_name_is_used_everywhere():
    assert TOOL_DEFINITION["name"] == TOOL_NAME
    assert TOOL_NAME in SERVER_INSTRUCTIONS
    assert TOOL_NAME in SKILL


def test_max_positions_is_stated_correctly():
    assert re.search(rf"Maximum {MAX_POSITIONS}\b", SKILL)
    assert re.search(rf"maximum positions: {MAX_POSITIONS}\b", API_DOCS)


def test_draw_once_and_never_invent_rules_are_everywhere():
    for text in (SERVER_INSTRUCTIONS, TOOL_DEFINITION["description"], SKILL):
        assert "once" in text.lower()
    for text in (SERVER_INSTRUCTIONS, SKILL):
        assert "never invent" in text.lower()
