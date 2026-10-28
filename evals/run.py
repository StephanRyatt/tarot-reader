"""Live runner: plays each case through a real Claude model with the shipped skill and tool,
executes draws locally through the shipped MCP handler, grades the transcript and writes a
JSON report.

    pip install -r requirements-evals.txt
    python -m evals                          # every case
    python -m evals --case crisis-abuse      # one case (repeatable)
    python -m evals --list                   # list cases, no API calls

A case that did not finish (API error, refusal, cut-off reply) is reported as an error and
is not graded, so the report never shows a result it did not measure.
"""

import argparse
import json
import random
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from api.mcp import SERVER_INSTRUCTIONS, TOOL_DEFINITION, dispatch
from evals.cases import CASES, Case
from evals.grade import CheckResult, Draw, ToolCall, Transcript, Turn, grade

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "plugin" / "skills" / "tarot-reading"
RESULTS_DIR = REPO_ROOT / "evals" / "results"

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "medium"
MAX_TOKENS = 16000
MAX_CALLS_PER_TURN = 6  # a turn needs 1 call, or 2 with a draw; more means a tool loop
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FINISHED = ("end_turn", "stop_sequence")
# USD per million tokens (input, output). A model missing here makes the cost "unknown".
PRICES = {"claude-opus-5-5": (4.00, 20.00)}


def build_system_prompt() -> str:
    """What a Claude client gives the model: server instructions, the skill and its library."""
    skill = (SKILL_DIR / "SKILL.md").read_text("utf-8")
    spreads = (SKILL_DIR / "references" / "spreads.md").read_text("utf-8")
    return (
        f"Instructions from the tarot-reader MCP server:\n{SERVER_INSTRUCTIONS}\n\n"
        f'<skill name="tarot-reading" path="SKILL.md">\n{skill}\n</skill>\n\n'
        f'<skill_file path="references/spreads.md">\n{spreads}\n</skill_file>'
    )


def build_tool() -> dict[str, Any]:
    """The shipped tool definition, in the Messages API's tool format."""
    return {
        "name": TOOL_DEFINITION["name"],
        "description": TOOL_DEFINITION["description"],
        "input_schema": TOOL_DEFINITION["inputSchema"],
    }


def execute_tool(name: str, arguments: Any, rng: random.Random) -> tuple[str, ToolCall]:
    """Run one tool call through the shipped MCP handler and return (text for the model, record).

    Bad arguments come back as an error result, exactly as the live server returns them.
    """
    request = {"name": name, "arguments": arguments}
    reply = dispatch(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": request}, rng=rng
    )
    recorded = arguments if isinstance(arguments, dict) else {"arguments": arguments}
    if "error" in reply:  # unknown tool: a JSON-RPC error, shown to the model as a tool error
        return reply["error"]["message"], ToolCall(recorded, is_error=True)
    result = reply["result"]
    text = result["content"][0]["text"]
    if result["isError"]:
        return text, ToolCall(recorded, is_error=True)
    draws = [
        Draw(position, card["card"], card["orientation"])
        for position, card in result["structuredContent"]["draws"].items()
    ]
    return text, ToolCall(recorded, is_error=False, draws=draws)


@dataclass
class ApiCall:
    model: str  # the model that answered, which a server-side fallback can change
    input_tokens: int
    output_tokens: int


@dataclass
class CaseRun:
    case: Case
    transcript: Transcript
    calls: list[ApiCall] = field(default_factory=list)
    error: str | None = None
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.error:
            return "error"
        return "pass" if all(check.passed for check in self.checks) else "fail"


def run_case(client: Any, case: Case, *, model: str, effort: str, seed: str) -> CaseRun:
    """Play one case turn by turn, then grade it if every turn finished."""
    run = CaseRun(case, Transcript(case.id))
    try:
        _play(client, run, model=model, effort=effort, rng=random.Random(f"{seed}:{case.id}"))
    except Exception as exc:  # any API failure leaves the case unmeasured, not failed
        run.error = f"{type(exc).__name__}: {exc}"
    if not run.error:
        run.checks = grade(case, run.transcript)
    return run


def _play(client: Any, run: CaseRun, *, model: str, effort: str, rng: random.Random) -> None:
    system, tools = build_system_prompt(), [build_tool()]
    messages: list[dict[str, Any]] = []
    for number, user_text in enumerate(run.case.turns, start=1):
        turn = Turn(user=user_text)
        run.transcript.turns.append(turn)
        messages.append({"role": "user", "content": user_text})
        for _ in range(MAX_CALLS_PER_TURN):
            response = client.beta.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=system,
                tools=tools,
                messages=messages,
                output_config={"effort": effort},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
            usage = response.usage
            run.calls.append(ApiCall(response.model, usage.input_tokens, usage.output_tokens))
            turn.stop_reason = response.stop_reason
            if response.stop_reason == "refusal":
                run.error = f"turn {number} refused: {response.stop_details}"
                return
            # Passed back unchanged: thinking blocks must reach the next request as they came.
            messages.append({"role": "assistant", "content": response.content})
            texts = [block.text for block in response.content if block.type == "text"]
            turn.final_text = "\n\n".join(texts)
            turn.text = "\n\n".join(part for part in (turn.text, turn.final_text) if part)
            if response.stop_reason == "tool_use":
                results = []
                for block in response.content:
                    if block.type == "tool_use":
                        text, call = execute_tool(block.name, block.input, rng)
                        turn.tool_calls.append(call)
                        results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": text,
                                "is_error": call.is_error,
                            }
                        )
                messages.append({"role": "user", "content": results})
            elif response.stop_reason != "pause_turn":
                break
        if turn.stop_reason not in FINISHED:
            run.error = f"turn {number} did not finish (stop_reason {turn.stop_reason!r})"
            return


def estimate_cost(calls: list[ApiCall]) -> float | None:
    """List-price cost of the calls in USD, or None if any call used a model with no price."""
    total = 0.0
    for call in calls:
        price = next((p for name, p in PRICES.items() if call.model.startswith(name)), None)
        if price is None:
            return None
        total += (call.input_tokens * price[0] + call.output_tokens * price[1]) / 1_000_000
    return total


def build_report(runs: list[CaseRun], *, model: str, effort: str, seed: str) -> dict[str, Any]:
    calls = [call for run in runs for call in run.calls]
    cost = estimate_cost(calls)
    return {
        "model": model,
        "effort": effort,
        "seed": seed,
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "summary": {
            "cases": len(runs),
            "passed": sum(run.status == "pass" for run in runs),
            "failed": sum(run.status == "fail" for run in runs),
            "errors": sum(run.status == "error" for run in runs),
            "api_calls": len(calls),
            "input_tokens": sum(call.input_tokens for call in calls),
            "output_tokens": sum(call.output_tokens for call in calls),
            "estimated_cost_usd": None if cost is None else round(cost, 4),
            "models_used": sorted({call.model for call in calls}),
        },
        "cases": [
            {
                "id": run.case.id,
                "behaviour": run.case.behaviour,
                "status": run.status,
                "error": run.error,
                "checks": [asdict(check) for check in run.checks],
                "api_calls": [asdict(call) for call in run.calls],
                "transcript": asdict(run.transcript),
            }
            for run in runs
        ],
    }


def print_run(run: CaseRun) -> None:
    print(f"{run.status.upper():5} {run.case.id}", flush=True)
    if run.error:
        print(f"      not graded: {run.error}")
    for check in run.checks:
        mark = "ok  " if check.passed else "FAIL"
        print(f"      {mark} {check.name}" + ("" if check.passed else f": {check.detail}"))


def print_summary(report: dict[str, Any], path: Path) -> None:
    s = report["summary"]
    cost = s["estimated_cost_usd"]
    cost_text = (
        "unknown (a model with no listed price answered)" if cost is None else f"${cost:.2f}"
    )
    print(
        f"\n{s['passed']} passed, {s['failed']} failed, {s['errors']} not graded "
        f"(of {s['cases']} cases)\n"
        f"{s['api_calls']} API calls, {s['input_tokens']:,} input + {s['output_tokens']:,} "
        f"output tokens, estimated cost {cost_text} at list prices\n"
        f"Report: {path}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals", description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--effort", default=DEFAULT_EFFORT, help="output_config effort level")
    parser.add_argument("--case", action="append", help="run only this case id (repeatable)")
    parser.add_argument("--seed", default="1", help="seed for the local card draws")
    parser.add_argument("--out", type=Path, help="report path (default: evals/results/)")
    parser.add_argument("--list", action="store_true", help="list the cases and exit")
    args = parser.parse_args(argv)

    cases = [case for case in CASES if not args.case or case.id in args.case]
    unknown = set(args.case or ()) - {case.id for case in CASES}
    if unknown:
        parser.error(f"unknown case id(s): {', '.join(sorted(unknown))}")
    if args.list:
        for case in cases:
            print(f"{case.id:24} {case.behaviour}")
        return 0

    try:
        import anthropic  # here, so the grader and its tests never need the SDK
    except ImportError:
        print(
            "The Anthropic SDK is missing: pip install -r requirements-evals.txt", file=sys.stderr
        )
        return 2

    client = anthropic.Anthropic()
    runs = []
    for case in cases:
        run = run_case(client, case, model=args.model, effort=args.effort, seed=args.seed)
        print_run(run)
        runs.append(run)

    report = build_report(runs, model=args.model, effort=args.effort, seed=args.seed)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = args.out or RESULTS_DIR / f"run-{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print_summary(report, path)
    return 0 if report["summary"]["passed"] == len(runs) else 1
