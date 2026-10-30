---
name: ask-specialist
description: "Get an independent, deep answer to one hard question, such as whether a formula, algorithm or rule holds. A reasoning specialist works it out from your sources; you get the conclusion, the edge cases and how to verify it."
when_to_use: "Use when the user asks to ask the specialist, or wants an independent answer to one question with a definite answer: is this formula or algorithm right, does this break an invariant, what does this rule imply. Also when a workflow step names the reasoning specialist, for example a stuck builder escalating one question. Don't start it unasked for questions this session can answer. Not for choosing between options (decision-council) or reviewing finished work (fresh-eyes)."
argument-hint: "[one question]"
---

# Ask the specialist

Get an independent, deep answer to one hard question: put it to the `reasoning-specialist` agent, then check its answer before you rely on it. When this skill comes from the `council` plugin, the agent is named `council:reasoning-specialist`.

Use a neighbor when the question is different (`/review:fresh-eyes` needs the `review` plugin):

- **A costly call the user will make, with or without options:** `/council:decision-council`: stress-test a costly decision before you commit.
- **A problem the user wants solved and built, with the choice delegated:** `/council:best-of-n`: compare n approaches to a problem, then build the best.
- **One plan, and the question is what could go wrong:** `/council:risk-evaluation`: see what could go wrong with one plan, how likely, how bad.
- **Finished work to check, including a decision already made:** `/review:fresh-eyes`: get an independent check that finished work is correct.

**Who starts it:** the user, or a workflow step that names the reasoning specialist. Don't start it on your own initiative for ordinary questions this session can answer.

## 1. Check that a subagent is available

The value is a fresh context that hasn't seen your reasoning. If this surface cannot start a subagent (for example, claude.ai chat), say so, and offer Claude Code or Cowork. Never answer in this context and present it as the specialist's view.

## 2. Make the question bounded

Write the question in one or two sentences, with a clear answer shape: yes or no, which one, what value, what it implies. If it is really several questions, or a choice between options, split it, or use the neighbor that fits. If the question is too vague to answer, sharpen it with the user first.

## 3. Write the brief

The specialist starts with zero context.

**Put in:**

- the question;
- the facts you have verified, stated as facts;
- the sources that govern the answer (specs, canonical docs, contracts, code paths), by path or link;
- what is already known to be true or ruled out.

**Keep out:** your own answer, your leaning, and the conclusion you hope for. It must reach its own.

## 4. Invoke

Start a new `reasoning-specialist` each time. Do not override its model. Its own definition sets the output: conclusion, reasoning with sources, constraints and invariants, edge cases, how to verify, and open uncertainty.

## 5. Check, then report

Check the load-bearing claims against the sources it cites. Separate what the sources establish from what it inferred.

Then report briefly:

- the conclusion;
- the reasons that carry it;
- what you checked;
- what remains uncertain, and any decision only the user can make.

If the answer conflicts with the canonical documents, surface the conflict. Don't resolve it silently.
