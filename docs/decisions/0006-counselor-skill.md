# 0006: A counselor that leans, with one clarifier on request

**Status:** accepted, October 2026

## Context

The first skill was procedural: draw, then walk through each card and summarise. The Custom GPT it replaced went the
other way, with a long reading arc that banned advice, steps and resolution. Both produced readings that hedged and
gave little help with an actual decision.

The owner's astrology product, Uranian, already has a counseling voice that works: honest in content, compassionate in
delivery, answer first, every claim tied to evidence, the choice left with the person. A decision council (a blind
solver, a pre-mortem skeptic and a veteran-reader persona, run independently) compared adapting the GPT instructions,
extending the old skill and rebuilding on the Uranian structure. All three chose the rebuild.

## Decision

* **The skill is a counselor.** `plugin/skills/tarot-reading/SKILL.md` follows the Uranian ethos with a method native
  to tarot: positions written for the question, one meaning per card, patterns across the spread (Major Arcana count,
  dominant suit, repeated numbers, court cards), and at most three patterns per reading.
* **Readings lean.** Each reading opens with which way the cards lean, naming the cards that carry it. "Will I" and
  "when" questions are reframed toward direction and what the situation asks, never events or dates. The decision
  stays with the person.
* **Safeguards against misuse** are part of the skill: fatalism, handing over the decision, asking again for a
  different answer, readings used to control others, spiritual bypassing, many readings a day, and medical, legal or
  financial decisions. A crisis sets the cards aside.
* **One clarifier, only with consent.** The spread is still drawn once per reading and never redrawn to change a
  result. A single clarifier card may follow only when the user asks for one or accepts the reader's offer. The
  reader offers one only when the deciding positions split with similar weight; a hard card is never a reason.
  Options in a decision belong in the spread, not in a clarifier. This amends the draw-once rule of
  [0004](0004-tool-metadata-is-product.md), and all three surfaces say so.
* **Only the spread name is sent as `label`.** The user's question and private details stay out of positions and
  label.
* **Named spreads live in `references/spreads.md`**, so the core rules stay short and visible in `SKILL.md`.

## Consequences

* Readings are more decisive, and the risk moves to overconfidence. The behaviour evals on the roadmap need to check
  that leans name their cards, that no events or dates are predicted, and that clarifiers are drawn only with consent.
* The server instructions stay under 512 characters, so the fuller method lives in the tool description, which every
  client shows the model, and in the skill.
* `tests/test_consistency.py` checks that all three surfaces mention the clarifier exception, and that every spread
  in the library is valid input for the tool.
