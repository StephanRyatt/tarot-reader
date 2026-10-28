"""The model sees the same rules in three places (server instructions, tool definition and
the plugin skill), and people read them in docs/API.md. These tests keep them in step."""

import json
import re
from pathlib import Path

from api.mcp import SERVER_INSTRUCTIONS, SERVER_VERSION, SPREADS, TOOL_DEFINITION, TOOL_NAME
from api.tarot import MAX_POSITIONS, draw_spread

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = (REPO_ROOT / "plugin" / "skills" / "tarot-reading" / "SKILL.md").read_text("utf-8")
API_DOCS = (REPO_ROOT / "docs" / "API.md").read_text("utf-8")
PLUGIN = json.loads((REPO_ROOT / "plugin" / "plugin.json").read_text("utf-8"))


def test_plugin_version_matches_server_version():
    claude_manifest = REPO_ROOT / "plugin" / ".claude-plugin" / "plugin.json"
    claude = json.loads(claude_manifest.read_text("utf-8"))
    assert PLUGIN["version"] == claude["version"] == SERVER_VERSION


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


def test_clarifier_exception_is_everywhere_and_needs_consent():
    for text in (SERVER_INSTRUCTIONS, TOOL_DEFINITION["description"], SKILL):
        assert "clarifier" in text.lower()
        assert "asks for" in text
        assert "accepts" in text


def test_tool_description_carries_the_core_method():
    # The tool description is the one text every client shows the model, skill or not.
    description = TOOL_DEFINITION["description"]
    for phrase in (
        "lean",
        "naming the cards",
        "never fixed fate, events or dates",
        "never answer yes or no to whether an event will happen",
    ):
        assert phrase in description
    assert "decision stays with the user" in description
    assert "likely patterns, never verdicts" in description


def test_label_carries_no_private_details():
    label_doc = TOOL_DEFINITION["inputSchema"]["properties"]["label"]["description"]
    assert "question" in label_doc
    assert "spread name only" in SERVER_INSTRUCTIONS
    assert "private details out" in SKILL


SPREADS_PATH = REPO_ROOT / "plugin" / "skills" / "tarot-reading" / "references" / "spreads.md"
SECTION_RE = re.compile(r"^## (.+)$", re.M)
POSITIONS_RE = re.compile(r"^- positions: `(\[.*\])`$", re.M)
LABEL_RE = re.compile(r"^- label: `([^`]+)`$", re.M)
MEANING_RE = re.compile(r"^\d+\. \*\*(.+?)\*\* — (.+)$", re.M)


def _library() -> list[tuple[str, list[str], str, list[tuple[str, str]]]]:
    """Parse references/spreads.md into (heading, positions, label, [(position, meaning)])."""
    text = SPREADS_PATH.read_text("utf-8")
    sections = SECTION_RE.split(text)[1:]
    parsed = []
    for heading, body in zip(sections[::2], sections[1::2], strict=True):
        positions = json.loads(POSITIONS_RE.search(body)[1])
        label = LABEL_RE.search(body)[1]
        meanings = [
            (name.replace("\\<", "<").replace("\\>", ">"), meaning)
            for name, meaning in MEANING_RE.findall(body)
        ]
        parsed.append((heading, positions, label, meanings))
    return parsed


def test_skill_points_to_the_spread_library():
    assert "references/spreads.md" in SKILL
    assert SPREADS_PATH.is_file()


def test_spread_library_matches_the_server_prompts():
    library = _library()
    assert [heading for heading, *_ in library] == [s.name for s in SPREADS]
    for (heading, positions, label, meanings), spread in zip(library, SPREADS, strict=True):
        assert label == heading == spread.name
        assert positions == [name for name, _ in spread.positions]
        assert meanings == list(spread.positions)


def test_every_spread_is_valid_tool_input():
    for spread in SPREADS:
        draw_spread(positions=[name for name, _ in spread.positions], label=spread.name)


def test_spreads_have_no_outcome_position():
    for spread in SPREADS:
        assert "Outcome" not in [name for name, _ in spread.positions]
