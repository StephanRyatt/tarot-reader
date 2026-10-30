# Templates

## 1. Decision brief (goes to every specialist)

Keep it neutral and self-contained. The specialists have not seen this conversation.

```
# Decision brief

## The decision
<One or two sentences: what must be decided, by when, and by whom.>

## Context and verified facts
<Facts you checked, each stated plainly, with where they came from.
Current state of the system/project, relevant numbers, versions, prior decisions.>

## Assumptions (unverified)
<Things you are taking as true but did not confirm. Specialists may challenge these.>

## Constraints
<Hard limits: budget, time, tooling, compliance, skills, things that cannot change.>

## What success looks like
<Outcomes that matter and how the requester would judge the result.>

## Stakes and reversibility
<What a wrong call costs, how hard it is to undo, who is affected.>

## Candidate options (starting points, not a closed list)
<Each option described in parallel, even-handed terms. Same level of detail and tone.
Omit this section entirely for the Blind Solver.>

## Open unknowns
<What nobody knows yet that could change the answer.>
```

Self-check before dispatch: does any sentence hint at a preferred option? Does one option get more words, a nicer name, or first position? Fix that.

## 2. Specialist prompt

```
You are one member of an independent advisory council. You have no knowledge of the other
members or their views, and you must reach your own conclusion. You are advisory and read-only:
do not modify files, change system state, or run side-effecting commands. You may read files
and search the web if it helps, and only if the brief makes that useful.

Your role and reasoning task:
<lens text>

<the decision brief>

Think carefully before answering. Treat the facts in the brief as ground truth; read or search
only to check a specific claim your conclusion depends on, not to re-survey the situation. Label
each important claim as EVIDENCE (verified or cited), INFERENCE (follows from evidence), or
GUESS (plausible but unverified). Do not hedge to avoid committing: pick a recommendation.

Respond in exactly this format, in about 600 words or fewer:

## Recommendation
<The approach you recommend, one or two sentences. It may be an option not in the brief.>

## Confidence
<Low / Medium / High, plus one sentence on what would change your mind.>

## Options assessed
For each option, including any you added:
- **Option:** <name>
- **For:** <strongest reasons>
- **Against:** <strongest reasons>
- **Tradeoff accepted:** <what you give up by choosing it>
- **Failure mode:** <how it most plausibly goes wrong, and how recoverable that is>
- **Reversibility:** <easy / costly / one-way>

## Load-bearing assumptions
<The 2-4 assumptions your recommendation depends on most. If any are false, what changes?>

## What I would verify first
<Cheap checks that would most reduce uncertainty.>

## Strongest case against my own recommendation
<Steelman the best alternative.>
```

## 3. Comparison table (your working artifact)

| | Specialist A | Specialist B | Specialist C | Specialist D (if 5) | Specialist E (if 5) |
|---|---|---|---|---|---|
| Pick | | | | | |
| Confidence | | | | | |
| Key reason | | | | | |
| Load-bearing assumption | | | | | |
| New option raised | | | | | |

Then list the cruxes: each as "X is right if <assumption>; Y is right if <assumption>", with the evidence you found on it.

## 4. Final report to the user

```
# Council verdict: <decision, short>

**Recommendation:** <the approach> — **confidence:** <low/medium/high>
<Two or three sentences: why this one, and the main thing you give up.>

## How the council split
<A line per specialist: pick and one-line reason. Note unanimity or a split, and whether
unanimity is suspicious (shared blind spot).>

## Options compared
| Option | Strengths | Tradeoffs / failure mode | Reversibility | Council support |
|---|---|---|---|---|

## Cruxes
<Each disagreement reduced to the assumption it turns on, and how you resolved it:
verified fact, weighed evidence, or left open.>

## Why this wins
<The reasoning from cruxes and tradeoffs to the pick, including any hybrid or staging logic.>

## Switch conditions
<If you learn X, prefer option Y.>

## Suggested first move
<A cheap, reversible step that de-risks the decision or buys the key missing information.>

## Strongest dissent
<The best argument against the recommendation, attributed to whoever made it.>

## Caveats
<Assumptions left unverified, claims you could not check, anything the council could not resolve.>
```

Report outcomes honestly: if the council could not separate two options, say that and name the single question the user needs to answer.
