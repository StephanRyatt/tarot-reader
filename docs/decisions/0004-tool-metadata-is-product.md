# 0004: Tool metadata is product, and it's tested

**Status:** accepted, October 2026

## Context

The engine guarantees a fair draw, but the user only benefits if the model actually calls the tool, calls it once,
and then interprets the returned cards rather than its own. That behaviour is shaped entirely by text the model
reads in three places:

* `SERVER_INSTRUCTIONS`, returned from `initialize`
* the `draw_tarot_spread` tool description and schemas
* the plugin skill, `plugin/skills/tarot-reading/SKILL.md`

If those drift apart, the model gets mixed signals: for example, a limit of 30 cards in one place and a different
number in another.

## Decision

Treat the three as one product surface:

* The rules live in all three: draw once per reading, never invent or change cards, and don't call the tool for
  "what does this card mean?". [0006](0006-counselor-skill.md) adds one exception, also in all three: a single
  clarifier card when the user asks for or accepts one.
* Limits come from engine constants, which the input schema reads.
* `tests/test_consistency.py` fails CI if the stated limit, the tool name or the core rules diverge, or if the
  plugin version and server version disagree.

## Consequences

* Editing one surface means checking the other two, and CI enforces the mechanical part.
* Consistency tests check the wording, not the behaviour. Behaviour evals against real models are on the roadmap.
