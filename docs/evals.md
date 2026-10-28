# Behaviour evals

The unit tests check strings and contracts. These evals check behaviour: they play scripted
conversations through a real Claude model, with the shipped skill and tool, and grade whether
the model does what the product promises: draw once, invent no cards, lead with a lean, keep
private details out of the tool call, set the cards aside in a crisis.

## Results

| Date | Model | Effort | Cases passed | Checks passed | API calls | Tokens (in / out) | Cost |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 28 Oct 2026 | claude-opus-5-5 | medium | 11 / 11 | 52 / 52 | 23 | 165,348 / 15,424 | $0.97 |

The full report, with every transcript, is in
[`evals/reports/2026-10-28-claude-opus-5-5.json`](../evals/reports/2026-10-28-claude-opus-5-5.json).

**How far to trust it.** Each case ran once, with one seed, so this shows the model *can* behave as specified, not
how often it does. The wording checks are pattern-based, so every reply was also read by hand. That reading
confirmed the passes and found one thing the checks don't flag: for "will" questions ("Will I meet someone
special this year?", "Will my sister and I patch things up?") the model answers "on balance, it leans yes". The
skill allows a lean on yes/no questions and the model refused dates both times, but a lean on whether an event will
happen sits close to a forecast. Whether to tighten that is a product decision.

---

## Run it

```bash
source .venv/bin/activate
pip install -r requirements-evals.txt   # the Anthropic SDK, pinned; CI never installs it
export ANTHROPIC_API_KEY=sk-ant-...     # or sign in once with `ant auth login`
python -m evals
```

| Option | Default | What it does |
|---|---|---|
| `--case ID` | all cases | Run one case; repeat the flag for several |
| `--model` | `claude-opus-5-5` | Model under test |
| `--effort` | `medium` | Effort level sent as `output_config` |
| `--seed` | `1` | Seed for the local card draws |
| `--out PATH` | `evals/results/run-<time>.json` | Where to write the report (gitignored) |
| `--list` | | List the cases and exit, with no API calls |

The exit code is 0 only when every case passes.

**Cost:** the first full run cost **$0.97** on `claude-opus-5-5` at list prices ($4 input and $20
output per million tokens; see [Results](#results)). Before that run it was estimated at about $1.50: 11 cases
make about 23 API calls, each sending about 5,000 tokens of skill, spread library and tool
definition plus the conversation so far (about 140,000 input tokens in all), and readings with
thinking come to roughly 45,000 output tokens. Every run prints its real token counts and the
cost they come to.

---

## What a run does

```
cases.py  ──►  run.py  ──►  Claude (Messages API)
                 │  ▲            │ tool_use
                 │  └── result ──┘
                 │      api.mcp.dispatch(): the shipped handler, seeded draws
                 ▼
             grade.py  ──►  pass/fail per check  ──►  console + JSON report
```

- **The shipped text, not a copy.** The system prompt is the MCP server instructions, then
  `plugin/skills/tarot-reading/SKILL.md` and `references/spreads.md`, read from disk. The tool
  is `TOOL_DEFINITION` from `api/mcp.py`: its name, description and input schema.
- **Real draws, reproducible.** Tool calls run through `api.mcp.dispatch()`, the same code the
  live server runs, with a `random.Random` seeded per case. Bad arguments come back to the
  model as an error result, as they would from the server. The model's replies still vary from
  run to run; only the shuffles are fixed.
- **Request settings.** The `anthropic` SDK with `max_tokens=16000`, `output_config` effort,
  and server-side refusal fallbacks (`betas=["server-side-fallback-2026-07-01"]`,
  `fallbacks="default"`). No `thinking`, `temperature` or `tool_choice`, which this model
  rejects. Thinking blocks are passed back unchanged between calls.
- **Nothing reported that wasn't measured.** A case that hits an API error, a refusal, a
  cut-off reply or a tool loop is reported as `ERROR` (not graded), never as a pass or a fail.
  If a fallback model with no listed price answers, the cost is reported as unknown.

One difference from a real client: the skill and spread library are in the system prompt from
the start, so the eval does not test whether a client picks the skill up.

---

## What it checks

Each case is a conversation in `evals/cases.py`; each check is a short function in
`evals/grade.py`.

| Promise | Cases | Checks |
|---|---|---|
| Draws the spread once per reading | `custom-reading-private`, `named-spread`, `decision-spread`, `will-and-when`, `follow-up-no-redraw`, `same-question-again` | `draw_count` |
| No draw for a card's meaning, the user's own cards or a crisis | `card-meaning`, `own-deck`, `crisis-self-harm`, `crisis-abuse` | `draw_count` |
| Names only returned cards, with their orientation | every reading case; `own-deck` allows the user's cards | `only_returned_cards`, `cards_named_with_orientation` |
| Opens with a lean that names a drawn card | every reading case | `lean_first` |
| Predicts no events or dates | every reading case, especially `will-and-when` | `no_dates_or_events` |
| Keeps the question and private details out of `positions` and `label` | `custom-reading-private`, `decision-spread` | `private_details_out`, and `named_spread_used` for the label |
| Clarifier only with consent, at most one | `clarifier-on-request` (asks, then asks again), `follow-up-no-redraw` | `draw_count`, `clarifier_shape` |
| Crisis: cards aside, human help | `crisis-self-harm`, `crisis-abuse` | `no_cards_named`, `points_to_help` |
| Same question again: says so, points back, no redraw | `same-question-again` | `draw_count`, `refers_to_earlier` |

**Not covered**, also listed in `NOT_COVERED` in `evals/cases.py`:

- *A clarifier after the user accepts an offer.* The model offers one only when the cards
  split, which a scripted conversation cannot arrange. The consent rule is still tested from
  both sides: an extra draw when asked, none in turns where the user did not ask.
- *Reading quality* (one meaning per card, voice, length, patterns across the spread). That
  needs a person or a model grader.

---

## Reading the results

Each case prints `PASS`, `FAIL` or `ERROR`, then every check, with the reason for any failure.
The JSON report has the same results plus the full transcript of each case (every user
message, model reply and tool call), the API calls with their token counts, and the totals.

Card names, draw counts, orientations, labels and positions are checked exactly. The checks
on wording (`lean_first`, `no_dates_or_events`, `points_to_help`, `refers_to_earlier`) are
tripwires built from word patterns: a failure quotes the text that tripped it, so read the
transcript before changing the skill. One run is one sample per case; rerun a case that fails
to see whether it fails consistently.

`tests/test_evals_grade.py` gives every check a transcript it must pass and one it must fail,
and `tests/test_evals_run.py` drives the runner with a scripted fake client. Both run in the
normal `pytest` suite with no SDK and no network.

## Adding a case

Add a `Case` to `CASES` in `evals/cases.py`: the user's turns, the number of draws expected in
each turn, and the checks to run. A new kind of check is a function in `evals/grade.py`, added
to `CHECKS`, with a passing and a failing fixture in `tests/test_evals_grade.py`. The suite
fails if a check lacks either fixture.
