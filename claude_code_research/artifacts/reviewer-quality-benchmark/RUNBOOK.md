# Reviewer-Quality Benchmark — Runbook

A method for measuring whether a reviewer configuration variable (model, effort
tier, prompt variant, tool restriction — anything you can express as a distinct
agent definition) changes **real-defect recall** on a document review task,
using a synthetic target with a documented answer key and a blind LLM judge.

This runbook is self-contained. It assumes only: a Claude Code environment
with the `Agent`/`Workflow` tooling, and the two companion files in this
directory (`synthetic-target.md`, `answer-key.md`). Adapt the arm definitions,
rep count, and target document to your own question; the method below is
generic.

---

## 1. Why a synthetic target, not a real document

The obvious design is "take a real plan/PR/design doc with known historical
defects and see who finds them." Don't. A real document leaks its own answer
key through channels a reviewer (especially a capable one) can exploit
without doing the review work the benchmark is supposed to measure:

- **Git history** — `git log`/`git blame` on the file or its later fixes.
- **Linked issues/PRs** — a real defect that got fixed has a paper trail
  (commit messages, issue titles, review comments) referencing it directly.
- **Referenceable code** — a real implementation lets a reviewer verify a
  claim by reading the actual code instead of reasoning about the document's
  internal consistency, which measures something different from what you're
  testing.

Any of these gives a reviewer arm a route to the right answer that has
nothing to do with the variable you're comparing. A **synthetic target** —
authored specifically for the benchmark, describing a fictional system, with
no external repository, no linked issues, no history — has no such leak
channel. Nothing exists outside the document text itself for a reviewer to
consult, so recall differences between arms can only come from how well each
arm reasons over the document it was actually given.

The cost of this choice: findings may not transfer to organically-occurring
defects in real review targets (see Limitations, §9). This is a deliberate
realism-for-control tradeoff, not an oversight.

### Building the target and answer key

- Write a plausible, detailed technical document (a plan, PR, design doc —
  match the shape of what you actually want reviewed) in the target's native
  register: real-looking constraints, a rationale for each design decision,
  a phased rollout, a verification section, worked numeric examples.
- Seed a fixed number of **deliberate defects** into it, each independently
  discoverable from the document's own text — no defect should require
  outside knowledge to spot. A good defect mix covers a few kinds of
  difficulty (each with example loci — a document doesn't need to match this
  exact taxonomy, but distinguishing "loud" from "quiet" defects is the point
  of tracking difficulty at all):
  - **surface-contradiction** — two adjacent or near-adjacent statements of
    the same fact directly disagree (a number restated differently, a
    prose statement contradicting a stated invariant two lines below).
  - **arithmetic-derivation** — a worked example or test fixture doesn't
    match the formula given for it; only surfaces if the reviewer actually
    applies the formula rather than trusting the printed value.
  - **cross-section** — a gap, inconsistency, or underspecification that
    only appears when two sections written far apart in the document are
    read against each other (e.g. a config schema field that a later
    algorithm section says is silently ignored).
- Write an **answer key** as a separate file: one entry per defect, with a
  stable `item_id`, its category (e.g. Showstopper / Inconsistency / Gap /
  Underspecified — pick categories that match your domain), its difficulty
  tag, its location (cite section names, not line numbers — line numbers
  drift if the document is ever edited), and a paragraph explaining the
  defect and why it matters. This becomes the judge's rubric (§6).
- Keep a **clean copy** of the target (pre-defect-injection) alongside the
  seeded copy if you want to re-derive or audit the injected defects later —
  not required to run the benchmark, but cheap insurance.

---

## 2. Define the arms

An "arm" is one reviewer configuration: a temporary Claude Code agent
definition file plus a dispatch prompt. Put each arm's agent file somewhere
your `Agent`/`Workflow` tooling can discover it (e.g. a project's
`.claude/agents/` directory, or wherever your harness resolves custom agent
types).

### 2.1 Agent file frontmatter shape

```markdown
---
name: doc-reviewer
description: Reviews a standalone document for correctness, consistency, and gaps.
model: opus
effort: high
tools: Read, Grep, Glob
---

You are reviewing a document. [... reviewer instructions ...]
```

- `name` and the visible heading/title inside the body — **must be
  identical across every arm being compared.** Never encode the
  manipulated variable into the name or a visible heading (e.g. never
  write `doc-reviewer-high-effort` or a body heading like "Reviewer
  (Experimental — effort:medium)"). A name or heading that reveals which
  variable is being tested contaminates the comparison two ways: it can
  leak into the reviewer's own behavior (an agent that knows it's the
  "medium" arm may reason differently about how much effort to spend),
  and it risks leaking into judge-visible output if the review text or
  agent identity ever gets logged alongside the judged content. Keep the
  arms' identity boundary strictly external to the agent file itself —
  track which physical file belongs to which arm in a separate mapping
  document that neither the review call nor the judge call ever reads.
  **This was a real bug found and fixed during development of this
  method** — an early arm heading exposed the effort tier being tested;
  fixing it meant rewriting every arm's heading to the same neutral
  string before further reps were trustworthy.
- `model` / `effort` (or whatever your platform exposes) — vary exactly
  the one thing you're testing. Hold every other field constant across
  arms except the variable under test and (if intentionally testing model
  choice) the model itself. If comparing effort tiers, the model must be
  identical across all effort arms; if comparing models, effort/config
  should be held as equivalent as the platforms allow, and any inherent
  incomparability (e.g. one model has no effort parameter at all) must be
  flagged and reported as a separate, non-ranked arm — do not force a
  ranking across mechanically different configurations.
- `tools` — restrict to **Read, Grep, Glob only** (no Bash, no Edit, no
  Write, no Agent/Workflow). The review is read-only by construction: the
  reviewer must not be able to modify the target, spawn subagents, or shell
  out to fetch external context. This also enforces the document-only
  scope from §3 mechanically, not just by prompt instruction.

### 2.2 Known gotcha — new agent files are not immediately dispatchable

A newly-created (or newly-edited) agent definition file is **not**
immediately available to the `Agent`/`Workflow` tool in the same session.
The agent-type registry only refreshes after one **failed** dispatch
attempt against the new type. Concretely:

1. Write or edit the arm's agent file.
2. Attempt one throwaway dispatch against that arm's `name` (any prompt —
   its content doesn't matter, it will fail).
3. It fails with a "no such agent type" (or equivalent) error. This failure
   is what triggers the registry refresh.
4. Retry the same dispatch (or, if using a `Workflow` script, resume it) —
   it now resolves correctly.

Budget for exactly one throwaway failed call per newly-created or
newly-edited arm, before treating that arm as usable. Skipping this step
produces a dispatch failure partway through a rep batch, not a silent
misconfiguration — but it wastes a rep slot if not anticipated, and if
you're driving reps from a `Workflow` script, build the throwaway-then-resume
step into the script itself rather than discovering it mid-run.

---

## 3. Dispatch prompt template (review stage)

Use this literal prompt shape for every review call, substituting only the
target file path. Do not vary the prompt across arms — the arm's agent file
is the only thing that should differ.

```
Do NOT use the Agent tool or Workflow tool. Do not spawn subagents. You are
the subagent — do all work directly. If you background any process or
command, you must block on it yourself with an explicit polling loop before
returning — there is no notification mechanism for a subagent's own child
process. Never claim you will "wait for a monitor" or "stand by for a
notification" and then return control.

Review this document: <absolute path to the target document>

Target family: PLAN

This review is document-only. No code exists for this target — do not
attempt to cross-reference implementation, do not look for a repository, do
not read any project CLAUDE.md or docs/CONTEXT.md (none apply to this
target; it is a standalone document with no surrounding project). Review the
document entirely on its own terms, against its own stated goals,
constraints, and internal consistency.
```

Adjust `Target family: PLAN` to match your document's actual genre (e.g.
`PR`, `ARCHITECTURE`, `TEST-PLAN`) if your reviewer instructions branch on
it — the point is to tell the reviewer explicitly what kind of document this
is and that there is nothing outside the document text to consult, so it
doesn't waste turns trying to `find` a repository that doesn't exist.

---

## 4. Running N reps per arm

Recommended pattern: drive reps through a scripted pipeline where each
review call is piped directly to a judge call, with **no barrier** between
review and judging for a given rep — i.e. the judge call for rep *k* starts
as soon as rep *k*'s review finishes, without waiting for all reps in the
arm to complete first. This maximizes parallelism across the whole run
(arms × reps × the review/judge pipeline) rather than serializing arm by
arm or stage by stage.

Concretely, for each arm × rep:

1. Dispatch the review-stage agent call (§3) against that arm's agent type.
2. Take the raw review output text.
3. Immediately dispatch the judge-stage call (§6) with that review text and
   the answer key — do not wait for other reps.
4. Record the judge's structured output keyed by `(armId, rep)`.

Do a **pilot rep** for at least one arm before committing to the full run,
to catch prompt or schema problems early. A pilot rep's result is real data
but is **not** reused as one of that arm's N reps — its purpose is
calibration (does the reviewer produce parseable output? does the judge's
schema actually fit what reviewers produce?), not data collection. Discard
it from the final tally and run all N reps for that arm fresh once the
pilot confirms the pipeline works.

Pick N based on how fine a recall difference you need to detect and how
this benchmark's decision rule works (§7) — recall range overlap at small N
only detects large effects. N=5 per arm is a reasonable floor for a first
pass; it will not detect a small-to-moderate true effect and the run should
say so explicitly (§9), not imply more precision than it has.

---

## 5. What "recall" means here, and how to compute it from judge output

Recall for one rep = (number of answer-key items the judge marked `found`)
/ (total answer-key items). Compute this by **counting the judge's own
per-item array directly**, not by trusting a judge-reported summary
integer — judges self-report summary counts inconsistently. Before trusting
any arm's numbers:

- Verify every rep's key-items array has exactly the expected number of
  entries (one per answer-key item) — a short array means the judge
  skipped an item rather than marking it not-found, which is a different
  failure mode and should be treated as a judge error, not a 0 for that
  item.
- Recompute `found_count` as the count of entries with `found: true` and
  compare it against any judge-reported summary count field. Log every
  mismatch found; use the recomputed count everywhere downstream. Do not
  silently accept the judge's self-reported number even when it usually
  matches — check every rep, every run.

---

## 6. Blind judge — prompt template and output schema

The judge call must never see which arm produced the review it's scoring —
no arm name, no model name, no effort tier, nothing that could bias
judgment or let the judge rationalize a score based on identity rather than
content. Pass only: the review text, the target document (or its path), and
the answer key.

### 6.1 Judge prompt template

```
Do NOT use the Agent tool or Workflow tool. Do not spawn subagents. You are
the subagent — do all work directly.

You are a blind judge scoring a document review against a fixed answer key
of known defects. You do not know and must not try to infer which reviewer
configuration produced this review — score the review text on its merits
only.

Target document: <absolute path to the target document>
Answer key: <absolute path to the answer-key file, or its inlined content>
Review under evaluation:
<<<
<the raw review text produced by the review-stage call>>>

For EVERY item in the answer key, decide independently whether the review
identifies that specific defect. Match by MECHANISM, SECTION, and VALUE —
not by line number (line numbers are not stable and the review may cite
different ones) and not by exact wording. A finding counts as matching an
answer-key item if it identifies the same underlying defect: the same two
(or more) facts in tension, the same broken formula, the same missing
mechanism — even if the review's phrasing, framing, or example differs from
the answer key's.

A halt-status "Diagnosis" or "Recommended Action" paragraph at the top of a
review (a summary judgment about whether the document is mergeable/blocked)
also counts as scorable content — if it correctly names a defect from the
answer key even in summary form, credit that item as found from the
diagnosis alone, do not require it to also appear in the itemized findings
list.

For every finding in the review that does NOT match an answer-key item,
classify it as:
- "genuine-novel" — a real, defensible issue with the document that
  happens not to be one of the seeded answer-key defects (documents
  legitimately can have real problems beyond the seeded set).
- some other verdict value indicating the finding is spurious — vague,
  factually wrong about the document, not actually a defect, or invented.
Use your judgment; the point of the two-way split is to separate "the
reviewer found something real we didn't seed" from "the reviewer
hallucinated or padded."

Output ONLY a JSON object with this exact shape:

{
  "pass_status": "<verbatim pass/fail or halt-status token from the review, if present, else your own overall assessment>",
  "key_items": [
    {
      "item_id": "<answer-key item_id, verbatim>",
      "found": true | false,
      "matching_text": "<the exact review text that matches this item, or empty string if not found>"
    },
    ... one entry per answer-key item, same order as the answer key ...
  ],
  "extra_findings": [
    {
      "title": "<short title of the extra finding>",
      "verdict": "genuine-novel" | "<spurious classification>",
      "reasoning": "<why you classified it this way>"
    },
    ...
  ],
  "recall_count": <integer, count of key_items with found:true>,
  "total_key_items": <integer, total number of answer-key items>
}

Emit nothing except this JSON object.
```

### 6.2 Schema notes

- `key_items` must always have exactly `total_key_items` entries, one per
  answer-key item, in a stable order — this is what lets you recompute
  recall directly (§5) instead of trusting `recall_count`.
- `extra_findings[].verdict` is a controlled vocabulary of exactly two
  buckets in practice: `"genuine-novel"` and everything else meaning
  spurious. Don't over-engineer more granularity unless you have a
  specific use for it — a run where every extra finding across every arm
  comes back `"genuine-novel"` (zero spurious findings) is a valid and
  informative result, not evidence the schema is broken; report it as-is.
- Run the judge **once per rep**. A single, unreplicated judge is a stated
  limitation of this method (§9), not something to silently work around —
  if judge-scoring noise matters for your decision, add inter-rater
  replication deliberately and say so in the write-up, don't assume one
  pass is authoritative.

---

## 7. Decision rule

**Pre-register this rule before looking at any results** — decide the
comparison logic in writing before the run, not after seeing which
numbers would make a nicer story.

1. For each arm, compute the recall range across its N reps: `[min recall
   count, max recall count]` (use the recomputed counts from §5).
2. For every pair of arms you're comparing, check whether their ranges
   overlap.
3. Arms are only reported as **separated** — i.e. the manipulated variable
   plausibly moved recall — if their ranges do **not** overlap.
4. If ranges overlap, report the result as **"no detectable difference at
   n=N"** — explicitly, in those words or equivalent. Do not force a
   ranking of point estimates (means) when the ranges overlap; a mean
   ordering under overlapping ranges is noise, not evidence, and reporting
   it as if it were a finding (even hedged) misrepresents what a small-N
   range-overlap test can support.
5. If some arms are inherently incomparable to others (e.g. one arm uses a
   model or config with no equivalent axis to vary — no effort parameter,
   a fundamentally different architecture), report that arm's numbers
   separately and do not include it in the pairwise decision-rule table at
   all. Say explicitly why it's excluded from ranking.

This is intentionally a blunt instrument. At small N (5-10 per arm) it can
only detect large effects; it is not a substitute for a proper statistical
test if you need to detect a small-to-moderate true effect size. State that
limitation plainly in your write-up rather than implying more precision
than the method has.

---

## 8. Sanity threshold (pre-registered floor)

Before trusting a null result (arms don't separate), verify the harness
itself is actually working — otherwise "no detectable difference" could
mean "the pipeline is broken and every arm scores near zero for reasons
unrelated to the variable under test."

Pre-register a numeric floor for the arm you expect to be the
**strongest** (highest capability, most effort, or whatever your prior
predicts should perform best) before running anything:

```
Requirement: <presumed-strongest arm>'s mean recall >= <floor>% of total answer-key items.
```

A reasonable default floor is **~30% mean recall** for the presumed-
strongest arm — low enough that it doesn't presuppose the answer you're
testing for, high enough that scoring below it would indicate a broken
prompt, a broken judge schema, or a target document that's unreviewable
rather than a genuine null result.

- If the presumed-strongest arm clears the floor: read the run's null
  result (if any) as **genuine** — the harness works, and the variable
  under test genuinely didn't move recall in this range.
- If the presumed-strongest arm falls below the floor: do not report a
  null result. Diagnose the pipeline (prompt clarity, judge schema
  mismatch, target document defects that are too obscure to be findable
  at all) before drawing any conclusion about the variable under test.

### Spurious-zero handling rule

A rep that scores 0 recall counts **as-is** in the arm's range and mean —
never exclude it as an outlier, never re-run it hoping for a better
number, and never treat it as evidence the pipeline is broken unless
*multiple* reps in the same arm, or the presumed-strongest arm specifically,
score nowhere near the sanity floor. One bad rep in an otherwise reasonable
arm is data, not noise to be cleaned up. Re-running to replace an
inconvenient result post hoc breaks the pre-registration and invalidates
the decision rule in §7.

---

## 9. Known limitations to carry forward

State these explicitly in any write-up of a run using this method — they
are structural to the method, not specific to any one execution of it:

- **Single, unreplicated judge.** Each rep is scored once by one LLM judge
  call with no inter-rater or repeated-judging check. Judge-scoring noise
  (self-reporting errors in summary fields, borderline match/no-match
  calls) is not distinguished from genuine reviewer-quality noise in the
  reported numbers. If you find judge self-reporting errors during the
  data-quality check (§5), that's evidence this is a real, if usually
  small, effect — not a reason to distrust the whole run, but a reason not
  to over-read small recall differences between arms.
- **Per-pass cost is not separable if your orchestration tool only reports
  an aggregate total.** If you drive reps through a scripting/orchestration
  layer whose API doesn't expose per-call token usage or wall-clock time
  back to the script — only an aggregate total across the entire run — you
  cannot produce a per-arm or per-rep cost comparison from that data alone.
  If cost-per-configuration is part of what you need to answer, you need a
  different capture mechanism (e.g. calling each review/judge stage as a
  directly-observed top-level call instead of from inside an opaque
  orchestration script, or whatever your platform's lower-level API
  exposes) — plan for this before the run, not after, since it usually
  can't be recovered retroactively from an aggregate-only total.
- **Realism-vs-control tradeoff of a synthetic target (§1).** Findings
  from a synthetic, defect-injected document may not transfer to
  organically-occurring defects in real review targets. This method
  answers "does variable X change recall on a controlled, leak-proof
  target," not "does variable X change recall on real documents your
  team actually produces." Say which question your run answers.
- **Small N is a range-overlap test, not a power-calculated study
  (§7).** It can rule out large effects and it can fail to separate arms
  that genuinely differ by a small-to-moderate amount. Don't claim more.
- **An arm using a fundamentally different configuration axis (e.g. a
  model with no effort parameter) is not a controlled comparison against
  arms that vary a shared axis.** Report it, don't rank it.
