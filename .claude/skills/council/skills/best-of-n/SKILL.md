---
name: best-of-n
description: "Compare n approaches to a problem, then build the best. Distinct solutions are drafted independently; the winner is picked on criteria set up front, tested where possible, then built. It makes the call; you review the result."
when_to_use: "Use when the user asks for best of n or best of 3, to try a few approaches and build the best, or to explore options and then build, or wants something built only after comparing real alternatives. Optional arguments: n (2 to 5), a model, a reasoning level. Not for a costly call the user wants to make themselves (decision-council), one plan's risks (risk-evaluation), or checking finished work (fresh-eyes)."
argument-hint: "[problem] [n] [model] [effort]"
---

# Best of n

Compare n approaches to a problem, then build the best. The user delegates the choice; this skill makes it and builds the result. The value comes from three things:

- **First principles:** solutions derived from what the problem requires, not from the first idea or from convention.
- **A fresh context:** the drafters haven't seen your own preferred answer, so they can't anchor on it.
- **Evidence where it is available:** when checks can separate the finalists, they are built and measured, not judged on paper.

Use a neighbor when the question is different (`/review:fresh-eyes` needs the `review` plugin):

- **A costly call the user will make, with or without options:** `/council:decision-council`: stress-test a costly decision before you commit.
- **One plan, and the question is what could go wrong:** `/council:risk-evaluation`: see what could go wrong with one plan, how likely, how bad.
- **One hard question with a definite answer:** `/council:ask-specialist`: get an independent, deep answer to one hard question.
- **Finished work to check, including a decision already made:** `/review:fresh-eyes`: get an independent check that finished work is correct.

**Who starts it.** If the user invoked `/council:best-of-n` or asked for best of n in words, run it. If you reached it on your own because a problem looks worth comparing, don't launch. Settle n and the drafting first (step 2), then offer it in one line with that path's rough cost, and start only on a yes. For example: "Want me to run best of 3 on this? With one drafter it costs roughly 2–3× a normal answer." or "… with three parallel drafters, roughly 4–5×." Any later step that adds agents beyond what the user agreed to asks again.

## 1. Check that a subagent is available

The work must run in separate agents. If this surface cannot start one (for example, claude.ai chat), say so. Offer to run it in Claude Code or Cowork. Never simulate the subagents in this context and present the result as independent. If the user still wants a same-context attempt, label it as such.

## 2. Settle n, the model, the effort and the drafting

Take any of these the user gave. Choose the rest:

- **n.** From how consequential the problem is:
  - **2** for a contained, easily reversed problem;
  - **3** as the usual default;
  - **4–5** for a problem that is costly to reverse or high-stakes.

  Don't go above 5: past that, the extra solutions are variations, not new approaches.
- **Model.** `opus`, unless the user named another.
- **Effort.** From the problem's difficulty and stakes:
  - **low** or **medium** for a small, well-understood problem;
  - **high** as the usual default;
  - **xhigh** for a hard or costly-to-reverse problem;
  - **max** only for the hardest, highest-stakes problems, or when the user asks.
- **Drafting.** One question decides it: once the problem is understood, could a competent practitioner name the main approaches? Answer it without writing the approaches down; listing them is the drafters' job.
  - **Yes: one drafter** (the default). Most code problems are like this, for example "cache with LRU, TTL or write-through". One subagent drafts all n. Seeing them side by side keeps them distinct, and it costs one agent.
  - **No: parallel drafters.** The problem is open-ended, for example designing a structure, boundaries or a workflow: the approaches aren't known until someone works them out, so how the problem is framed decides the answer, and one drafter would share one framing across all n. Start n subagents instead, each from a different **starting point** (step 3). It costs about n× the drafting. Unless the user asked for parallel drafting, or agreed to its cost in the offer above, ask before taking it, naming the cost.

  A call the user should own, such as a strategy or a vendor, belongs with `/council:decision-council`, not here.

Say what you chose in one line, with the reason for each choice you made yourself and the cost. For example: "n = 3, opus, high effort, one drafter: a contained refactor that touches the public API, with well-known approaches."

## 3. Gather the facts and write the brief

The drafters start with zero context. Anything they need must be in the brief, and anything that would anchor them must stay out.

First gather the facts. If the problem touches a codebase or system, inspect it yourself (read-only) and put what you found in the brief as stated facts. Ask the user only if a missing answer would change the solutions materially; otherwise state your assumption in the brief and mark it as one.

**Put in the brief:**

- **The problem**, stated as what must be achieved, not as a solution.
- **Constraints**: what must hold, what must not change, and the limits on time, cost, dependencies and compatibility.
- **Success criteria**, split in two:
  - **checkable:** a command, test or measurement whose result can be read off (tests pass, latency, bundle size, accuracy on a fixture set);
  - **judged:** criteria that need reasoning (clarity, maintainability, fit with the architecture).

  Write down the checks now, before any solution exists, so they can't be bent to fit a favorite: the exact command or measurement, and what counts as better. If a check needs a script that doesn't exist yet, write it outside the repository (for example in a scratch directory) and make it take the build's path as an argument, so it can run against any build.

  Rank the criteria too: mark the must-haves, then order the rest by weight. The comparison is judged in that order, so the weights can't shift after the solutions are seen.
- **Sources**: the relevant files, docs, specs, and the project's own instructions (`CLAUDE.md`, `AGENTS.md`), by path or link.
- **Scope of the build**: what the deliverable is (code changes, a document, a plan) and where it may change files.
- The instructions and output format below that match the drafting you chose.

**Keep out of the brief:** your own preferred solution, your leaning, and any ranking of approaches. Don't list candidate solutions. If the user proposed one, include it as a constraint only if they require it; otherwise leave it out, so it competes on equal terms (you can check in step 5 whether it was covered).

### One drafter

**Instructions:**

1. Work out the best n solutions from first principles: start from what the problem requires and its constraints, not from the first idea or the usual pattern.
2. Make them genuinely distinct: different approaches, not variations of one. Reject strawmen: each solution must be one a competent person could defend.
3. Compare them against the success criteria and the constraints, including their tradeoffs, cost, risk and reversibility. Judge by the criteria, not by preference. For each checkable criterion, predict each solution's result and your confidence in it.
4. Name the winner, or a hybrid that takes the strongest parts of several if the comparison supports it. A hybrid that merely averages two solutions doesn't count. Name any close contenders too: the solutions whose check results are close enough to the winner's that only building them could separate them.
5. Build nothing yet. Return the comparison and wait.

**Output format:**

- the n solutions, one or two lines each;
- a comparison table: solutions against the success criteria and the main tradeoffs, with predicted check results;
- the winner (or hybrid) and why, briefly; the close contenders, if any;
- any tradeoff the choice turns on that only the user can weigh (a preference, a one-way door, a commitment such as a vendor, a schema or a public API).

### Parallel drafters

Every drafter gets the same brief plus one starting point of its own. A starting point is a way of reasoning, never an approach or a hint of one: it must be able to lead to any answer, including keeping things as they are. Pick the n that differ most for this problem from:

- **From the need:** start from who uses the result and what they are trying to do at the moment they use it.
- **From the constraints:** start from the hard limits and what they rule out, then design the simplest thing that fits.
- **Clean slate:** set the current solution aside and design from the success criteria alone; only then map the design onto what exists and say where each is better.
- **From the failure:** start from how solutions to this kind of problem usually fail, and design against that.
- **From the mechanism:** start from what each available building block buys and costs, and keep only those that earn their cost.

If none fits, write one in the same form. Never write one that names a solution. "From the constraints" and "From the mechanism" both lean toward lean designs; with n = 2 or 3, don't pick both.

**Instructions:**

1. You are one of several independent drafters; you don't know the others' starting points or views. Reason from your starting point and from first principles to your single best solution.
2. Judge it against the success criteria and constraints, with its tradeoffs, cost, risk and reversibility. For each checkable criterion, predict its result and your confidence.
3. Give the strongest objection to your own solution, and why you still prefer it.
4. Build nothing yet. Return your draft and wait.

**Output format:**

- the solution, with enough detail to build it from;
- how it meets each success criterion, with predicted check results;
- its main tradeoffs;
- the strongest objection, and the answer to it;
- any tradeoff it turns on that only the user can weigh.

## 4. Launch

Pass the model through the Agent tool's `model` parameter and the effort through its `effort` parameter. Start new agents each time; never reuse one that has seen your reasoning.

- **One drafter:** start one `general-purpose` agent with the brief.
- **Parallel drafters:** start n `general-purpose` agents in one message, each with the brief and its own starting point, so none sees another's draft.

Don't run parallel drafters on the same brief without distinct starting points: they converge on the same typical answer. And don't assign each one an approach to pursue: that means you listed the approaches yourself, which is the anchoring this skill exists to avoid.

## 5. Compare, then choose the build path

**With one drafter,** read its comparison before anything is built. Check:

- **The solutions are genuinely distinct**, and none is a strawman.
- **The winner was judged on the ranked criteria**, not on preference.
- **A solution the user proposed was covered**, if there was one.

If the comparison is weak, say so. If the n turned out to be variations of one framing, the problem was more open-ended than it looked: offer to switch to parallel drafters, naming the cost. Otherwise run again with a sharper brief. Don't build on a weak comparison.

**With parallel drafters,** you build the comparison yourself: a table of the drafts against the ranked success criteria and the main tradeoffs. Judge the criteria in the order the brief set, not by which draft fits your own view. Each drafter predicted check results only for its own solution, as its advocate, so treat those numbers as rough. When two drafts are close on them, treat both as close contenders rather than declare a clear lead. Name the winner, or a hybrid that takes the strongest parts of several if the comparison supports it, and any close contenders. Also check that a solution the user proposed was covered, if there was one.

If the drafts converged despite different starting points, say so and carry on: that is some evidence the answer is clear, but weak evidence, because all the drafters share one model. Don't rerun to force variety.

You judged the drafts yourself, so you are not independent of the pick. When the stakes are high, offer, before building, an independent check of the comparison: `/review:fresh-eyes` (when the `review` plugin is installed), with the decision as its kind and the drafts and ranked criteria as its sources.

**Ownership guard.** If the choice turns on a tradeoff only the user can weigh, stop. Show the user the comparison and ask them to choose. If the choice is consequential enough to deserve independent challenge, offer `/council:decision-council` instead. Build only after they answer.

Then choose one of two paths:

**Build the winner** (the usual path). Use it when the winner leads clearly, when no checkable criterion separates it from a contender, or when building more than one costs more than the stakes justify. Send the go-ahead with `SendMessage` (load the tool first if it is deferred), naming the chosen solution:

- with one drafter, to that drafter, which already holds the brief and the comparison;
- with parallel drafters, to the drafter of the winner, which already holds the brief and its own draft. For a hybrid, send it to the drafter whose solution forms the core, with the parts to take from the other drafts.

Ask it to:

- build it within the scope given;
- check it against the success criteria (for code, run the relevant tests and checks);
- not commit, push, publish, send or merge;
- report what it built and where.

If the drafter can't be resumed on this surface, start one new `general-purpose` agent with the same `model` and `effort`, and give it the build brief (below) plus the chosen solution's draft.

The **build brief** is the problem, constraints, ranked success criteria and checks, sources and scope from step 3, without the drafting instructions, the output format or any starting point.

**Build and measure the finalists.** The finalists are the winner plus one close contender, or two for high stakes: 2 or 3 builds in total. Use this path only when all of these hold:

- a checkable criterion could separate the finalists, and the paper prediction is unreliable (performance, behavior under real data, integration with a flaky dependency);
- the work is in a git repository with runnable checks;
- the stakes justify 2–3 full builds.

Worktrees start from the last commit, so the user's uncommitted changes are not in them. If the working tree has uncommitted changes the build depends on, ask the user before taking this path, or build the winner instead.

Unless the user asked for best of n explicitly, ask before taking this path, naming its cost. Otherwise say in one line that you are taking it, and its cost. Then:

1. Start one new `general-purpose` agent per finalist, all in one message. Give each `isolation: "worktree"`, plus the same `model` and `effort` as in step 4.
2. Give each builder only the build brief and the description of the one solution it must build. Withhold the comparison, the predicted winner and the predicted results: a builder that knows it is building the expected loser, or the number it is meant to hit, distorts the measurement.
3. Tell each builder not to commit, push, publish, send or merge, and to report its worktree path.
4. Run the same checks on every build yourself, and pick by the results. A hybrid is allowed only if it is itself built and measured: one more builder in its own worktree, on the same terms. Count it in the cost before you start it.
5. Bring the winner's changes into the user's working tree, including new files. For example: `git -C <worktree> add -A`, then `git -C <worktree> diff --cached HEAD | git apply`.
6. Remove every finalist worktree (`git worktree remove --force <path>`) and delete the branches they were created on.

## 6. Check the build

Don't accept the report as given. Check:

- **It built what it said.** Read the changed files or the deliverable.
- **It meets the success criteria.** Re-run the checks it ran, and any it skipped.
- **It stayed in scope.** It changed only what the user asked for. Undo anything outside that scope, and say so.

Fix small gaps yourself. If the build fails the success criteria in substance, say so, and ask whether to fix it here or run again with a sharper brief.

## 7. Report

Report briefly:

- n, model, effort, the drafting and the build path, and why;
- the n solutions in a line each, and the winner and why it won;
- for parallel drafters: where the drafts agreed and where they differed;
- for the measured path: the predicted against the measured results, which shows how far the paper comparison could be trusted;
- what was built and where;
- checks run and their results;
- what remains unverified, and any decisions only the user can make.

Nothing gets committed, pushed, published, sent or merged unless the user asked.
