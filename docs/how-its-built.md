# How Tarot Reader is built

A one-page account of the architecture, how the model uses the tool, how it's tested, and how coding agents were
used. Numbers are as of October 2026.

## The problem

A chat model asked to "draw three tarot cards" with no tools picks the cards itself, from what it finds likely.
Tarot Reader moves the draw out of the model: a server shuffles a real deck and deals the cards, and the model's job
is reduced to interpreting what it was dealt.

## Architecture

* **One engine.** `draw_spread()` in `api/tarot.py` validates the request, builds the 78-card deck, flips a few
  packets to create reversals (about 26% of cards), shuffles with operating-system randomness, cuts and deals. It is
  pure: tests pass a seeded random generator and get the same cards every time.
* **Two thin interfaces.** An MCP server (`api/mcp.py`) for Claude, ChatGPT and other MCP clients, and a legacy REST
  endpoint for a Custom GPT that retires in December 2026. Both only translate requests into a call to the engine.
* **Stateless on Vercel.** Each request stands alone, with no sessions or streams, which suits a serverless function.
  The runtime uses only Python's standard library. The public instance runs without a key behind a rate limit of
  60 requests a minute per IP.

## How the model uses the tool

Most of the product is text the model reads, so it is treated as product and kept in one place per job:

| Surface | Who sees it | What it carries |
| :--- | :--- | :--- |
| Tool description | Every client, always | When to draw, draw once, lead with the lean, no events or dates |
| Server instructions | Some clients (under 512 characters) | The same core rules, compressed |
| Skill (`SKILL.md`, ~2,000 words) | Claude, through the plugin | The reading method, voice, safeguards and clarifier rule |
| Spread library | Claude (skill file) and every MCP client (as prompts) | Eight named spreads with position meanings |

Two design choices follow from where that text lands. Privacy is handled in the instructions: the tool receives only
position names and a spread name, and the model is told to keep the user's question out of both, which the server
cannot enforce. And because only the draw is guaranteed, behaviour is measured, not assumed (see Testing).

## Testing and CI

* **252 tests** in about 1,850 lines, running in about two seconds. 168 of them test the server (about 900 lines,
  97% line coverage): input validation, deck invariants, a chi-square fairness check over 7,800 seeded draws, the
  frozen REST contract, each MCP check, the plugin package, and the wording the three model-facing surfaces must
  share. The other 84 test the eval harness's grading on fixed example transcripts.
* **CI** (GitHub Actions) runs ruff, strict mypy and the test suite with a 95% coverage floor on every push and pull
  request. Vercel deploys `main`.
* **Behaviour evals** ([docs/evals.md](evals.md)) play 11 scripted conversations through a real model with the
  shipped skill and tool, run the draws locally with fixed seeds, and grade each transcript with code checks:
  draw counts, only returned cards, the lean first, no dates or events, nothing private in the tool call, crisis
  handling, and more. Each check has a passing and a failing example in the test suite. A full run costs about $1 on
  Claude Opus 5.5. The harness was chosen by comparing three designs (code checks, a model as
  grader, an existing framework); code checks won because they can be tested offline and give the same verdict
  every time. Reading quality isn't graded. Three live runs on 28 October 2026 (Claude Opus 5.5, about $1
  each): reading the first by hand showed the model answering "leans yes" to "will" questions, so the skill now
  separates choices from outcomes, and the second run passed 10 of 11 cases as currently graded.
  The one miss, repeated 10 times, stated its lean 8 times out of 10, and a third full run on the final skill
  passed 11 of 11. Each case ran once, so this shows the
  behaviour is achievable, not how reliable it is.

## How coding agents were used

I'm a product manager, not a professional software engineer. The code was written with coding agents; my part was
the direction, the product and design decisions, and the review.

* **A checked-in brief.** `CLAUDE.md` tells any agent the commands, the architecture, the order of checks that must
  not change, and the contracts to keep.
* **Audit, then decide, then build.** An agent audited the repo against best practice. I settled the open decisions
  (licence, public demo, evals, retiring the REST path), and the work landed as seven pull requests, recorded in six
  short [decision records](decisions/).
* **Independent agents for the hard calls.** The counseling skill's shape came from a decision council: three agents
  with different briefs (a blind solver, a pre-mortem skeptic, a veteran reader) that never saw each other's
  answers. A separate agent reviewed the clarifier rule, and two more reviewed the finished change.
* **Review caught real problems.** A test named "chunked" had never sent a chunked body. The privacy text promised
  more than the design could keep. One spread position asked the model to predict an event. A pattern rule in the
  skill would have fired in about 79% of ten-card spreads by chance alone. Each was fixed before release.

## What it doesn't do

* It can't make a model follow the skill. Three eval runs, one sample per case each, can't show how reliably
  the model behaves.
* ChatGPT gets the tool only, not the skill.
* The Codex setup is documented but untested.
* Readings are interpretive reflection: no predictions, and no medical, legal or financial guidance.
