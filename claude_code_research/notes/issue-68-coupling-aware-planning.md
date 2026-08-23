# Issue #68 — proactive coupling-aware planning (negative result, abandoned)

## TL;DR for a future reader

Do not re-attempt a proactive "flag coupling at interview/planning time" check in
grill-me/write-a-prd without reading this note first. Two independently-designed
implementations of the idea were killed by stress-test on structural grounds, and a
follow-up empirical audit of two separate stress-test plan corpora found that even a
perfect version of the check would have missed most of the runaway plans it was meant to
catch, and that no proactive coupling catch has ever actually happened in either corpus.
The mechanism was abandoned, not merely deferred.

## Context and what is NOT being retracted

Issue #59 (closed) established, against a corpus of 41 stress-tested plans in one project,
that **coupling — not raw plan size — drives runaway stress-test rerun rounds**. That
finding is not in question here and this session did not re-test it. It was already
operationalized reactively in `stress-test/SKILL.md`: a take-stock threshold (rerun
streak >= 3, tightened to streak >= 2 above an 800-line/3-coupled-phase size-and-coupling
proxy) and "Option D" — cut a runnable slice out of an oversized/over-coupled plan and
resume review against evidence from running it, instead of another prose pass.

Issue #68 started from the observation that everything above is **reactive** — it only
fires once stress-test is already reviewing a drafted plan. Nothing catches deep coupling
**before** a plan is drafted, at interview time. This session's task was to design that
proactive check. It concludes that no version of it is currently supportable.

## Attempt 1 — a `coupling: essential`/`accidental` marker in grill-me

Design: add a new decision step to the grill-me interview skill, inserted between its
existing steps 7 and 8, asking whether the plan's coupling is essential or accidental, and
writing a `coupling: essential` marker into the plan file when judged essential. Theory:
stress-test would read the marker and apply its tightened take-stock threshold in
anticipation, before size/phase counts alone would trigger it.

**Stress-test pass 1 (Opus) killed the mechanism, not just details:**

- **The marker is inert.** Nothing anywhere in the skill ecosystem reads a `coupling:`
  field — stress-test derives its own size/coupled-phase proxy independently, from the
  plan text, not from any interview-time metadata. Writing the marker does nothing.
- **No carrier for the marker on the path that matters most.** grill-me itself writes no
  files. The standalone `/grill-me` -> plan-mode path has nowhere to put the marker at
  all. Only the `write-a-prd` path (which routes through a PRD template) has a file to
  write it into.
- **Renumbering breaks two other skills' control flow.** Inserting a step between grill-me's
  existing 7 and 8 silently breaks `wayfinder` and a self-reference inside `stress-test`
  itself — both branch on "grill-me's step 8" as a control-flow anchor, not just as prose
  describing grill-me. A numbering change is a breaking change to code that isn't grill-me.
- **A `/new-feature` skill would run the live grill-me interview twice back-to-back** —
  an interaction the design hadn't accounted for.
- **essential/accidental had no decision test and an asymmetric cost.** Nothing in the new
  step defined how to actually distinguish essential from accidental coupling, and because
  only the "essential" branch had any associated action, every uncertain case was biased
  toward that branch by construction — a decision step that can't actually decide.

## Attempt 2 — execution-feedback commitment, appended as a new step 9

Redesign, in direct response to pass 1's findings:

- Replaced the inert marker with an **execution-feedback commitment**: on the essential
  branch, commit up front to naming a walking skeleton or one executable test *before* the
  prose plan is allowed to grow past ~800 lines. This is the proactive mirror of Option D
  (the evidence-backed reactive remedy from #59/take-stock), not a new untested idea.
- Appended the check as a **new step 9** rather than inserting between 7 and 8, specifically
  to avoid the wayfinder/stress-test cross-reference breakage found in pass 1.
- Added supporting fixes: reuse-detection to stop the double-interview under
  `/new-feature`, an explicit non-skippable carve-out, and an explicit prohibition on
  Agent-tool dispatch inside the new step.

**Stress-test pass 2 (Opus), reviewing the whole revised document, found the central fix
was incomplete — not a new problem, the same one wearing a different shape:**

- **"No carrier" was logged as resolved but wasn't.** The execution-feedback commitment
  still has no reader and no persistence mechanism on the standalone plan-mode path (no
  file, nothing downstream consumes it). Same defect as the marker in attempt 1, disguised
  by moving it to step 9 instead of fixing where it's written.
- **essential/accidental still had no real decision test** — just a default, unchanged from
  pass 1's finding.
- **No success criterion was ever proposed.** Nothing in either attempt specified how you'd
  measure whether the intervention actually helps — a direct violation of this project's
  own "measure, don't read" rule for plans that assert a causal mechanism.
- **The new step fires unconditionally inside a skill it wasn't designed for.** wayfinder's
  deliberately narrow single-question escalations have no valid referent for a "before the
  plan grows past 800 lines" commitment — the step doesn't know it's being invoked from a
  context where its own premise doesn't apply.
- **A new abandonment-timing edge case** between step 8 and the new step 9 was introduced
  by the redesign itself, uncovered by two *other* skills' control-flow assumptions — the
  same category of collateral damage as pass 1, in a different place.
- **Inconsistent with grill-me's own ADR-candidate mechanism.** Asserting "essential"
  coupling was treated as automatically qualifying for grill-me's separate ADR-candidate
  flag, but that mechanism has its own conjunctive, discretionary criteria that this
  shortcut bypassed.

## Turning point: measure before a third redesign

At this point the session had two structurally distinct implementations of the same idea,
each killed by an independent adversarial pass, for overlapping-but-different reasons. The
next step was **not** a third prose redesign — the session paused instead to measure
whether the underlying premise (a proactive check would meaningfully help) was even true,
before spending more design effort on how to encode it.

Ran an empirical audit of two independent stress-test plan corpora — one local (~167
plans), one on a remote machine (`s3rbase`, a different project, ~175-238 plans depending
on dedup pass). Methodology is written up separately and reusably at
[`../artifacts/stress-test-corpus-audit.md`](../artifacts/stress-test-corpus-audit.md) —
not repeated here.

Findings:

- **Coverage ceiling: 30-43%.** Across both corpora, classifying each runaway plan's root
  coupling as "apparent at interview time" (a proactive check could plausibly have caught
  it) versus "only emerged during drafting/review" gave roughly 30-43% apparent, the
  remainder emergent. Even a **perfect** proactive check would have missed more than half
  of the cases it was designed to catch.
- **Zero observed instances of proactive coupling detection, on either machine.** Across
  the combined corpus, every real instance of a plan being split due to coupling was
  reactive — discovered during stress-test review, then split via a COUNTER RESET or a
  follow-up issue. Nothing resembling a proactive catch appears in either corpus's history.
- **Option D vs Option A does not generalize across projects.** A follow-up measurement —
  checking whether take-stock's reactive Option D (cut a slice, resume against evidence)
  was simply underused relative to Option A (just run another review pass) — found the two
  options' relative performance differs by corpus: one showed Option D dramatically
  outperforming Option A, the other showed them roughly comparable. Confirmed via a
  dedicated reconciliation pass as a genuine cross-project difference, not a measurement
  artifact.

## Conclusion

Abandoned the grill-me/write-a-prd proactive-coupling mechanism entirely, rather than
attempting a third redesign. Reasoning:

1. **Structural soundness is unresolved twice over.** Two independently-designed
   implementations were both broken on structural grounds — not edge cases, not
   polish — by independent adversarial review. Nothing suggests a third design would
   fare differently without first fixing the underlying "no carrier on the standalone
   path" problem, which neither attempt actually solved.
2. **Even a working version has a low ceiling.** The corpus audit caps proactive coverage
   at 30-43% of the cases it targets, with zero historical evidence it has ever fired in
   practice. The expected value of getting the mechanism right is bounded by that ceiling
   regardless of how well it's built.

This does **not** retract #59's original finding (coupling, not size, drives runaway
reruns) — that stands, and the reactive take-stock/Option D machinery it produced remains
in place and evidence-backed. What's retracted is the follow-on assumption that this
diagnosis is *actionable proactively*, at planning/interview time, via a simple check. It
isn't, at least not in any form tried here.

## Durable output

One small, low-risk addition landed in `stress-test/SKILL.md`'s learnings file:

- At a take-stock decision, weigh the diagnosis of *recurring findings* over raw streak
  count or an optimistic read of "the next pass will converge."
- Don't trust a specific historical Option-D-vs-Option-A performance percentage to
  transfer between projects — the cross-project audit found a genuine difference, not
  noise, between the two corpora measured here.

## Process lesson

Two stress-test passes broke two structurally different implementations of the same idea
before the switch from design iteration to measurement happened. The lesson is in the
sequencing, not just the conclusion: the corpus audit could have been run *before* attempt
1, and would have surfaced the 30-43% coverage ceiling immediately — cheaper than two full
design/review cycles. Measure a causal-mechanism plan's premise before iterating on its
design, not after two failed iterations force the question.

## References

- Issue #59 (closed) — original coupling-vs-size finding, corpus of 41 plans, one project.
  Not retracted by this note.
- Issue #68 — this session's investigation; closed with a link to this note.
- [`../artifacts/stress-test-corpus-audit.md`](../artifacts/stress-test-corpus-audit.md) —
  reusable methodology for the two-corpus empirical audit referenced above.
