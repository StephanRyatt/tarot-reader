---
name: decision-council
description: "Stress-test a costly decision before you commit. Three to five independent specialists weigh the options, and you get a recommendation with its tradeoffs, what it turns on, and the strongest dissent. You make the call; nothing is built."
when_to_use: "Use when the user asks for a council or a panel, wants a choice stress-tested before committing, or asks for help deciding between credible approaches where a wrong call is costly, hard to reverse or contested: architecture, migrations, backup, security or infrastructure changes, vendor, hiring or tooling bets, strategy. The user makes the call and may bring options or only the problem. Not for trivial, factual or easily reversed questions; one plan's risks (risk-evaluation); a decision already made (fresh-eyes); a problem the user wants solved and built (best-of-n); one question with a definite answer (ask-specialist)."
argument-hint: "[the decision, and options if any]"
---

# Decision council

Stress-test a costly decision before you commit: several independent specialists analyze it, each from a different angle, and you reason over their disagreement to find the best approach. The value comes from two things: **independence** (each specialist reaches its own conclusion without seeing yours or anyone else's) and **comparison** (you work out *why* they differ, not just count votes). If either is compromised, the council is just one opinion repeated five times.

The council advises; it does not act. Do not execute the chosen approach, change files, or run side-effecting commands as part of this skill. Present the recommendation and let the user decide (and, in operational contexts, obtain whatever approval their rules require before acting).

Use a neighbor when the question is different (`/review:fresh-eyes` needs the `review` plugin):

- **A problem the user wants solved and built, with the choice delegated:** `/council:best-of-n`: compare n approaches to a problem, then build the best.
- **One plan, and the question is what could go wrong:** `/council:risk-evaluation`: see what could go wrong with one plan, how likely, how bad.
- **One hard question with a definite answer:** `/council:ask-specialist`: get an independent, deep answer to one hard question.
- **Finished work to check, including a decision already made:** `/review:fresh-eyes`: get an independent check that finished work is correct.

## When to use it (and when not)

Use it when the decision is consequential (costly, slow, or risky to reverse) *and* there are genuinely different credible approaches. A council costs 3 to 5 agent runs plus synthesis, so spend that only where a wrong call is expensive. For a simple, reversible, or factual question, answer directly. Whether to launch depends on how you got here:

- **The user explicitly asked** (invoked `/council:decision-council`, or asked for a council, a panel, or a stress-test of a decision): run it straight away.
- **You reached it on your own** because the decision looks consequential: do not launch. Ask first, in one line, naming the squad size you'd use and the rough cost (for example, "This looks high-stakes and hard to reverse. Want me to run a 5-specialist decision council on it? It costs roughly 5× a normal answer."). Launch only after the user says yes. Spending several agent runs unasked is a surprise the user didn't choose, even when the stakes really are high.

**Check that subagents are available first.** The specialists must run as separate agents. If this surface cannot start subagents (for example, claude.ai chat), say so. Offer to run the council in Claude Code or Cowork. Never role-play several specialists in one context and call it a council.

## Workflow

### 1. Frame the question and build the brief

The specialists start with **zero context**. Anything they need must be in the brief, and anything that would bias them must stay out of it.

First gather facts. If the question touches the user's system, codebase, or environment, inspect it yourself (read-only) *now* and put the findings into the brief as stated facts. Specialists then spend their effort reasoning instead of rediscovering the same facts five times, and they all reason from the same ground truth. Ask the user a question only if a missing answer would change the analysis materially; otherwise state your assumption in the brief and flag it.

Write the brief using the template in `references/brief-and-report.md`. It contains: the decision, context and verified facts, constraints, what success means, reversibility and stakes, known options, and open unknowns. Rules for writing it:

- **Neutral framing.** Describe options in parallel, even-handed language. Do not state your own leaning, do not order options by preference, and do not editorialize. Your framing is the biggest source of correlated error in the whole exercise.
- **Separate fact from assumption.** Mark what you verified and what you're guessing. Specialists should be able to challenge assumptions.
- **Invite new options.** The listed options are a starting point, not a menu. The best answer is sometimes one nobody listed. If the user brought only a problem, list only the options already on the table, or none, and say so in the brief; the specialists generate the rest.
- **No secrets.** Don't put credentials or sensitive data in the brief; specialists don't need them.

### 2. Assemble the squad

Size the squad by stakes. Each extra specialist costs about as much as the first (roughly linear), but the insight per specialist drops quickly: every specialist runs on the same model and brief, so errors are correlated and a fourth or fifth lens mostly repeats the first three. Three is the minimum that triangulates (two can only disagree).

- **Standard: 3 specialists.** The default.
- **High-stakes: 5 specialists from the start.** Use this for one-way doors, costly or slow-to-reverse decisions, or when the user calls the decision critical. When a mistake is irreversible, quick agreement is the least trustworthy signal, so buy the wider spread up front.
- **Escalation: 3, then +2.** After the first wave, step 4 decides whether to add two more specialists, chosen to attack the specific open crux.
- **Hard cap: 5.** Beyond that you pay for reading, not for insight.

Pick from the lens library in `references/lenses.md`, choosing for diversity of *reasoning approach*, not just topic. The standard three are:

- a **Blind Solver**, who receives the question and facts but *not* your list of options, so it can surface alternatives your framing missed;
- a **Skeptic / pre-mortem** specialist, whose job is to find how each leading option fails;
- a **domain expert** written fresh for the question ("senior SRE who has run Borg backups for a decade"), since a generic expert adds little.

For 5, add a reversibility/risk strategist plus the one lens that best fits the question (operator, outside-view analyst, security, cost horizon, and so on).

### 3. Dispatch in parallel, in one message

Launch every specialist in the wave as a separate `Agent` call **in the same message** so they run concurrently and can't influence one another. Use `general-purpose` agents so they can read files and search the web if the question needs it; instruct them that they are advisory and read-only. Give each one only: the brief, its role/lens, and the required output format (from `references/brief-and-report.md`). Do not tell them what the other specialists are, and do not pass one specialist's output to another in this round.

Don't set a model or effort override unless the user asked; the default inherits a strong model, which is what a reasoning council should use. A weaker model on some seats saves tokens but adds noise to the comparison, so offer that as a knob to the user rather than doing it silently. Tell each specialist to reason carefully and to label claims as **evidence**, **inference**, or **guess**, because you need that labeling to weigh them later.

Keep the cost down where it is cheap to do so: the brief already holds the verified facts, so tell specialists to treat it as ground truth and to read or search only to check a specific claim that their conclusion depends on. Cap each report at about 600 words (the format in `references/brief-and-report.md` does this). Re-researching shared facts is the biggest avoidable cost, not squad size.

### 4. Compare and synthesize

When the reports come back, resist the pull to just tally votes. Work through these in order:

0. **Decide whether to escalate** (only after a 3-specialist first wave; skip if you started at 5). Add two more specialists, launched together in one message with the same neutral brief and no knowledge of the first wave's views, if any of these hold: a crux between the first three can't be settled from evidence; confidence across them is low; or the Blind Solver or Skeptic raised a new option or a serious flaw that the others never addressed. Pick the two lenses that bear directly on that crux (for example, a cost-horizon economist if the dispute is about time horizon). If the first wave agrees, is confident, and the Skeptic found no fatal flaw, stop at 3 and say in the report that the stakes didn't warrant more.
1. **Normalize.** Extract each specialist's pick, confidence, and the assumptions it rests on into a comparison table (options × specialists, with each cell's verdict and key reason). Include any new options surfaced, especially by the Blind Solver.
2. **Find the cruxes.** For each disagreement, ask *what would have to be true for each side to be right?* Disagreements almost always trace back to a small number of differing assumptions (risk tolerance, a factual claim, a time horizon, a weighting of reversibility). Name them. A crux is the real unit of analysis.
3. **Check what's checkable.** If a crux is a factual claim you can verify cheaply (read a config, run a read-only command, look up a doc), verify it now and let the result settle that dispute. A fact beats an opinion.
4. **Weigh by evidence, not by headcount.** Rank arguments by evidence quality, whether they engage with the actual constraints, and whether the specialist considered the strongest counterargument. A well-evidenced minority view can outrank a lazy majority. Conversely, treat unanimity with suspicion: all specialists share the same underlying model and brief, so agreement can mean a shared blind spot. Say so when consensus is easy, and spend extra effort on what the Skeptic and Blind Solver found.
5. **Compare tradeoffs, not just winners.** For each serious option, note what you give up by choosing it, what it protects against, how reversible it is, and how it fails. The best approach is usually the one whose failure modes are cheapest and most recoverable given the user's actual constraints, not the one with the highest upside.
6. **Consider hybrids carefully.** A combined or staged approach (do the reversible part first, defer the commitment until a key unknown resolves) is often better than any pure option. But a hybrid that merely averages two opinions is a trap; only propose one if it follows from the cruxes.
7. **Optional second round.** If one or two cruxes remain open, the specialists are split on something decisive, and more reasoning could plausibly resolve it, run **one** targeted follow-up: send the relevant specialists (via `SendMessage` to the same agents) the opposing argument and ask them to concede, rebut, or revise. Do this only when it's likely to change the answer; independence has already done its job and extra rounds mostly cost tokens and drift toward groupthink.

If the council is genuinely split and the cruxes can't be resolved from evidence, say that plainly and name the one thing the user must decide or learn to break the tie. Manufacturing a confident answer from an honest tie is the worst failure of this skill.

### 5. Report

Give the user a decision-ready report (template in `references/brief-and-report.md`). Keep it tight enough to read in a couple of minutes, with the detail available below it. It must contain:

- the **recommendation** and your confidence in it;
- the **comparison** of the options and where specialists agreed and disagreed;
- the **cruxes** and how you resolved them (or that you couldn't);
- the **tradeoffs the user accepts** by choosing this approach;
- **switch conditions**: what evidence would make a different option better;
- a **first move** that is cheap, reversible, and de-risks the decision;
- **dissent worth keeping**: the strongest case against your recommendation.

Present it in the chat. Save a copy to a file only if the user asks, and never write it into a location that the user's instructions say must stay clean.

End by saying that once the user has decided, you can build the chosen option here. Don't start building until they say so.

## Failure modes to guard against

- **Leaky brief.** If the brief hints at your preference, every specialist anchors on it. Re-read it for loaded wording before dispatch.
- **Sequential dispatch.** Launching specialists one after another lets earlier outputs leak into later reasoning, and wastes time. One message, all calls.
- **Persona theater.** A role name alone changes little. Each specialist needs a concrete reasoning task (what to optimize, what to attack, what to ignore), as the lens library provides.
- **False consensus.** Agreement among agents with the same base model is weaker evidence than agreement among independent humans. Verify the load-bearing claims.
- **Overspending.** Don't convene a council to answer something you could settle by reading one file. Don't add specialists past 5, and don't let specialists re-research facts already in the brief.
