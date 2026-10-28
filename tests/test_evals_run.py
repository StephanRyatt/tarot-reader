"""The eval runner, against a scripted fake client: no SDK, no API key, no network."""

import json
import random
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from api.mcp import SERVER_INSTRUCTIONS, TOOL_DEFINITION, format_spread_text
from api.tarot import draw_spread
from evals import run as runner
from evals.cases import CASES
from evals.grade import ToolCall

SKILL_DIR = Path(__file__).resolve().parents[1] / "plugin" / "skills" / "tarot-reading"
NAMED_SPREAD = next(c for c in CASES if c.id == "named-spread")
CARD_MEANING = next(c for c in CASES if c.id == "card-meaning")


def text(value: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=value)


def tool_use(block_id: str, arguments: Any, name: str = "draw_tarot_spread") -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=arguments)


def response(stop_reason: str, *content: SimpleNamespace, model: str = "claude-opus-5-5") -> Any:
    usage = SimpleNamespace(input_tokens=1000, output_tokens=500)
    return SimpleNamespace(
        stop_reason=stop_reason, content=list(content), usage=usage, model=model, stop_details=None
    )


class FakeClient:
    """Answers each request with script(messages) and records every request."""

    def __init__(self, script: Callable[[list[dict[str, Any]]], Any]) -> None:
        self.script = script
        self.requests: list[dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs: Any) -> Any:
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.script(kwargs["messages"])


def daily_reader(messages: list[dict[str, Any]]) -> Any:
    """A well-behaved model for the named-spread case: draw once, then read with a lean."""
    last = messages[-1]["content"]
    if isinstance(last, str):
        positions = ["Day's Atmosphere", "Primary Focus", "Aligned Approach"]
        thinking = SimpleNamespace(type="thinking", thinking="Draw first.", signature="sig")
        arguments = {"positions": positions, "label": "Daily Alignment"}
        return response("tool_use", thinking, text("Drawing now."), tool_use("t1", arguments))
    lines = last[0]["content"].splitlines()[1:]  # "1. Day's Atmosphere: The Sun (upright)"
    cards = [line.split(": ", 1)[1] for line in lines]
    first = cards[0].rsplit(" (", 1)[0]
    reading = f"The day leans clearly toward steady effort, carried by {first}.\n\n"
    reading += "\n".join(f"**{line[3:].replace(': ', ' — ')}**" for line in lines)
    return response("end_turn", text(reading))


def run_one(script: Callable[[list[dict[str, Any]]], Any], case: Any = NAMED_SPREAD) -> Any:
    client = FakeClient(script)
    result = runner.run_case(client, case, model="claude-opus-5-5", effort="medium", seed="1")
    return client, result


def test_system_prompt_is_the_shipped_skill_and_spread_library() -> None:
    prompt = runner.build_system_prompt()
    assert SERVER_INSTRUCTIONS in prompt
    assert (SKILL_DIR / "SKILL.md").read_text("utf-8") in prompt
    assert (SKILL_DIR / "references" / "spreads.md").read_text("utf-8") in prompt


def test_tool_is_the_shipped_definition() -> None:
    tool = runner.build_tool()
    assert tool["name"] == TOOL_DEFINITION["name"]
    assert tool["description"] is TOOL_DEFINITION["description"]
    assert tool["input_schema"] is TOOL_DEFINITION["inputSchema"]


def test_execute_tool_draws_like_the_server_and_reproducibly() -> None:
    arguments = {"positions": ["Past", "Present"], "label": "Test"}
    result_text, call = runner.execute_tool("draw_tarot_spread", arguments, random.Random("s"))
    expected = draw_spread(positions=["Past", "Present"], label="Test", rng=random.Random("s"))
    assert result_text == format_spread_text(expected)
    assert not call.is_error
    assert [(d.position, d.card, d.orientation) for d in call.draws] == [
        (position, card["card"], card["orientation"])
        for position, card in expected["draws"].items()
    ]


@pytest.mark.parametrize(
    ("name", "arguments", "message"),
    [
        ("draw_tarot_spread", {"positions": []}, "Invalid arguments"),
        ("draw_tarot_spread", {"positions": ["A", "A"]}, "unique"),
        ("draw_tarot_spread", "not an object", "arguments must be an object"),
        ("draw_tarot_spread", {"positions": ["A"], "label": 7}, "label must be a string"),
        ("some_other_tool", {"positions": ["A"]}, "Unknown tool"),
    ],
)
def test_execute_tool_returns_errors_instead_of_raising(
    name: str, arguments: Any, message: str
) -> None:
    result_text, call = runner.execute_tool(name, arguments, random.Random(1))
    assert message in result_text
    assert call.is_error
    assert call.draws == []


def test_run_case_plays_the_tool_loop_and_grades_a_good_reading() -> None:
    _client, result = run_one(daily_reader)
    assert result.status == "pass", [c for c in result.checks if not c.passed]
    assert [c.name for c in result.checks] == list(NAMED_SPREAD.checks)
    turn = result.transcript.turns[0]
    assert turn.text.startswith("Drawing now.")
    assert turn.final_text.startswith("The day leans")
    assert len(turn.tool_calls) == 1
    assert len(result.calls) == 2


def test_requests_use_the_documented_parameters() -> None:
    client, _result = run_one(daily_reader)
    for request in client.requests:
        assert request["model"] == "claude-opus-5-5"
        assert request["max_tokens"] == 16000
        assert request["output_config"] == {"effort": "medium"}
        assert request["betas"] == ["server-side-fallback-2026-07-01"]
        assert request["fallbacks"] == "default"
        assert request["tools"] == [runner.build_tool()]
        for forbidden in ("thinking", "temperature", "top_p", "top_k", "tool_choice"):
            assert forbidden not in request


def test_assistant_content_goes_back_unchanged_with_all_results_in_one_message() -> None:
    first: list[Any] = []

    def two_draws(messages: list[dict[str, Any]]) -> Any:
        if isinstance(messages[-1]["content"], str):
            first.append(
                response(
                    "tool_use",
                    tool_use("a", {"positions": ["One"]}),
                    tool_use("b", {"positions": []}),
                )
            )
            return first[0]
        return response("end_turn", text("Done."))

    client, result = run_one(two_draws)
    messages = client.requests[1]["messages"]
    assert messages[1] == {"role": "assistant", "content": first[0].content}
    assert messages[1]["content"] is first[0].content
    results = messages[2]["content"]
    assert messages[2]["role"] == "user"
    assert [(r["type"], r["tool_use_id"], r["is_error"]) for r in results] == [
        ("tool_result", "a", False),
        ("tool_result", "b", True),
    ]
    assert result.status == "fail"  # graded: the case expected a lean and orientation


def test_multi_turn_cases_keep_the_conversation() -> None:
    case = next(c for c in CASES if c.id == "follow-up-no-redraw")
    client, result = run_one(lambda messages: response("end_turn", text("Answer.")), case)
    assert len(result.transcript.turns) == 2
    assert client.requests[-1]["messages"][-1] == {"role": "user", "content": case.turns[1]}
    assert len(client.requests[-1]["messages"]) == 3


@pytest.mark.parametrize(
    ("script", "error"),
    [
        (lambda m: response("refusal"), "turn 1 refused"),
        (lambda m: response("max_tokens", text("Cut off")), "did not finish"),
        (lambda m: response("tool_use", tool_use("x", {"positions": ["A"]})), "did not finish"),
    ],
)
def test_unfinished_cases_are_errors_and_not_graded(
    script: Callable[[list[dict[str, Any]]], Any], error: str
) -> None:
    _client, result = run_one(script)
    assert result.status == "error"
    assert error in str(result.error)
    assert result.checks == []


def test_api_exceptions_are_errors_and_not_graded() -> None:
    def broken(messages: list[dict[str, Any]]) -> Any:
        raise ConnectionError("network down")

    _client, result = run_one(broken)
    assert result.status == "error"
    assert result.error == "ConnectionError: network down"
    assert result.checks == []


def test_pause_turn_continues_the_turn() -> None:
    replies = iter([response("pause_turn"), response("end_turn", text("Answer."))])
    _client, result = run_one(lambda messages: next(replies), CARD_MEANING)
    assert result.status == "pass"
    assert len(result.calls) == 2


def test_estimate_cost_uses_list_prices_and_admits_unknown_models() -> None:
    calls = [runner.ApiCall("claude-opus-5-5", 1_000_000, 100_000)]
    assert runner.estimate_cost(calls) == pytest.approx(4.0 + 2.0)
    assert runner.estimate_cost([*calls, runner.ApiCall("some-fallback", 10, 10)]) is None
    assert runner.estimate_cost([]) == 0.0


def test_report_summarises_what_was_measured() -> None:
    _c, good = run_one(daily_reader)
    _c, bad = run_one(lambda m: response("refusal"))
    report = runner.build_report([good, bad], model="claude-opus-5-5", effort="medium", seed="1")
    summary = report["summary"]
    assert (summary["passed"], summary["failed"], summary["errors"]) == (1, 0, 1)
    assert summary["api_calls"] == 3
    assert summary["input_tokens"] == 3000
    assert summary["estimated_cost_usd"] == pytest.approx(3 * (0.004 + 0.01))
    assert report["cases"][1]["checks"] == []
    json.dumps(report)  # serialisable as written


def test_main_lists_cases_without_the_sdk(capsys: pytest.CaptureFixture[str]) -> None:
    assert runner.main(["--list"]) == 0
    out = capsys.readouterr().out
    assert all(c.id in out for c in CASES)


def test_main_explains_a_missing_sdk(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setitem(sys.modules, "anthropic", None)  # makes `import anthropic` fail
    assert runner.main(["--case", "card-meaning"]) == 2
    assert "requirements-evals.txt" in capsys.readouterr().err


def test_main_rejects_unknown_cases() -> None:
    with pytest.raises(SystemExit):
        runner.main(["--case", "nope"])


@pytest.mark.parametrize(("reply", "exit_code"), [("It means grief.", 0), ("", 0)])
def test_main_runs_cases_and_writes_the_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, reply: str, exit_code: int
) -> None:
    client = FakeClient(lambda messages: response("end_turn", text(reply)))
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=lambda: client))
    out = tmp_path / "report.json"
    assert runner.main(["--case", "card-meaning", "--out", str(out)]) == exit_code
    report = json.loads(out.read_text("utf-8"))
    assert report["cases"][0]["status"] == "pass"
    assert report["cases"][0]["transcript"]["turns"][0]["final_text"] == reply


def test_main_exits_non_zero_when_a_case_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = FakeClient(lambda m: response("tool_use", tool_use("x", {"positions": ["A"]})))
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=lambda: client))
    assert runner.main(["--case", "card-meaning", "--out", str(tmp_path / "r.json")]) == 1
    assert "not graded" in capsys.readouterr().out


def test_tool_call_record_reads_arguments_safely() -> None:
    call = ToolCall({"positions": "not a list", "label": None}, is_error=True)
    assert call.positions == []
    assert call.label == ""
    assert not call.is_clarifier
