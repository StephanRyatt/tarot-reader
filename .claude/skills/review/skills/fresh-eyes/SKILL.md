---
name: fresh-eyes
description: "Get an independent check that finished work is correct: code against its spec, a plan, a decision, a document or filing. Findings are verified against the sources, then fixed if the work was made in this session, otherwise reported."
when_to_use: "Use when the user asks for fresh eyes, an independent review or a second look, extra scrutiny, a self-review, or a red team of a plan or other work, and when a workflow calls for review before handing work over. Works on the user's own work or someone else's, including a PR. Not for choosing between options (decision-council), estimating how likely and how bad risks are (risk-evaluation), one question with a definite answer (ask-specialist), or checking a frontend against its Figma design (figma-workflow:verify)."
argument-hint: "[what to review]"
---

# Fresh eyes

Get an independent check that finished work is correct: the `fresh-reviewer` agent challenges one piece of work in a fresh context, then you act on what it confirms. When this skill comes from the `review` plugin, the agent is named `review:fresh-reviewer`.

Review policy lives in that agent: what to look for, the questions for each kind of work, the finding format, and its read-only limits. Do not restate or override it in the handoff.

Use a neighbor when the question is different (the `/council:` skills need the `council` plugin):

- **A costly call the user will make, with or without options:** `/council:decision-council`: stress-test a costly decision before you commit.
- **A problem the user wants solved and built, with the choice delegated:** `/council:best-of-n`: compare n approaches to a problem, then build the best.
- **One plan, and the question is what could go wrong:** `/council:risk-evaluation`: see what could go wrong with one plan, how likely, how bad.
- **One hard question with a definite answer:** `/council:ask-specialist`: get an independent, deep answer to one hard question.

## 1. Check that a fresh context is available

Independence is the point: a reviewer that has not seen the author's reasoning. That needs a subagent.

If this surface cannot start one (for example, claude.ai chat, where plugin agents do not run), say so. Offer to run the review in Claude Code or Cowork. Never review in the same context and call it independent. If the user still wants a same-context check, label it as such.

## 2. Settle three things

**Target.** Name one coherent piece of work, for example:

- the current branch's diff;
- PR #N;
- a plan file;
- a decision or recommendation;
- a document, a letter, a form's answers, an evidence list;
- the files a task changed.

If the user named the target, use it. Otherwise take the work just finished in this session. Review that piece, not the whole project.

**Kind.** Name the kind of work, so the reviewer applies the right questions. Use one of: code against a spec, plan, decision, or document or filing. Name two when a piece is both, such as a plan that contains decisions.

**Mode.**

- **Fix:** the work is yours, from this session. Resolve the confirmed findings here (§5). This is the default for your own just-finished work.
- **Report:** someone else's work, a PR, an existing document, or whenever the user asks only for findings. Deliver the adjudicated findings and change nothing.

## 3. Gather the governing evidence, by reference

- **Requirements:** the task, issue, brief, spec, or acceptance checklist.
- **Governing sources:** the project's own instructions (`CLAUDE.md`, `AGENTS.md`, knowledge files), its canonical documents, and authoritative outside sources the work must conform to (official rules, forms and their instructions, standards, specifications).
- **Approved decisions** that bear on the work.
- **Validation evidence:** commands run and their results, checklists completed, sources consulted.

In fix mode, run any required validation that has not run yet, so the reviewer can inspect the evidence.

## 4. Pick the depth, then invoke

Match the depth to the stakes:

- **Standard:** one `fresh-reviewer`. Use it for most work.
- **Deep:** two `fresh-reviewer` agents, started together in one message, so neither sees the other. Give each the same sources, and a different lens:
  - *conformance:* does the work do what its sources and requirements say?
  - *first principles:* should the work exist in this form at all, and what would make it fail?

  Use deep when the work is costly or slow to reverse, such as a filing, an irreversible migration, a plan for many PRs, or a public release. Use it also when the user asks for extra scrutiny.
- **Hand over to the council** (`/council:decision-council`, when installed) when the real question is choosing between options, not whether this work is correct. Say so, and ask before starting it. A council costs several agent runs.
- **Hand over to risk evaluation** (`/council:risk-evaluation`, when installed) when the real question is how likely and how bad the ways it could go wrong are, rather than whether it is correct. Say so, and offer it.

When you start a reviewer:

- Start a new one each time. Never reuse an authoring subagent or its context.
- Give it the target, the kind, the lens (deep mode only) and the sources from §3.
- Do not brief it with your conclusions, your rationale, or the problems you suspect.
- Do not override its model.

## 5. Adjudicate, then act

Verify each finding against the governing evidence yourself. Do not accept findings mechanically. Reject invalid, subjective, duplicate or out-of-scope findings, each with a brief reason. In deep mode, merge duplicates across the two reviewers. Where the two disagree, settle it from the sources, and say how you did.

- **Fix mode:** fix the confirmed findings, then re-run the validation for what changed. If the fixes materially changed the substance (the design, the core logic, the strategy, or a decision), start one new standard review of the changed part. Otherwise, do not repeat the review.
- **Report mode:** stop after adjudicating. Hand over the confirmed findings, ranked by severity, each with its remedy.

## 6. Report

Report concisely:

- the target, kind, mode and depth you used;
- findings confirmed, and what was fixed or what is recommended;
- findings rejected, and why;
- checks run, and their results;
- any remaining uncertainty, or decisions only the user can make.

Do not merge, push, file, send or publish anything unless the user explicitly asked for it.
