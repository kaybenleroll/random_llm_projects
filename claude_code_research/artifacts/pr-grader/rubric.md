# Review rubric and grade anchors

This file is inserted verbatim into the reviewer and verifier system prompts and
is also the specification for the grade function in `pr_grader.py`. Change one,
change the other, and re-run the unit tests.

## What you assess

You are given an issue (title and body), the diff that was merged to close it,
and the full source tree after the merge. You judge only the merged change
against that issue.

### 1. Acceptance criteria

Extract every acceptance criterion (AC) from the issue. Where the issue has an
explicit "Acceptance criteria" list, use one entry per bullet, in order, with ids
`AC1`, `AC2`, ... If the issue has no explicit list, derive ACs from the
requirements stated in its scope and problem sections and say so in the
`evidence` of the first entry.

Give each AC exactly one status:

| status | meaning |
| --- | --- |
| `met` | The code and tests in the tree demonstrably satisfy it. You can point at the lines. |
| `partial` | Some of what the AC demands is present, but a stated part is missing or wrong. |
| `not_met` | The AC is not satisfied, or the code contradicts it. |
| `not_assessable` | It cannot be judged from source alone: it demands running a container, a live service, a build, a measurement, a PR description or any other artefact you were not given. |

Do not guess. Use `not_assessable` rather than `met` when satisfaction depends
on something you cannot read. Use `not_met` or `partial` only when you can cite
the missing or wrong behaviour. An AC that requires a test to exist is
assessable: check that the test exists and exercises the behaviour.

**"Demonstrated by", "verified by", "measured", "shown" ACs.** When the wording
of an AC requires the behaviour to be demonstrated, `met` needs both:

* a cited code location (`file:line`) that implements it, and
* either a test in the tree you can trace to an assertion that would fail if the
  behaviour were removed or inverted (cite `file:line` of the assertion), or
  executed evidence that is present in the inputs (a committed output, log,
  recording or report that was produced by running it: cite file and line).

Implementation present but neither a traceable test nor executed evidence:
`not_assessable` if the demonstration is by its nature an execution (a run
against a service or container, a build, a measurement, a performance figure, a
manual or visual check), and `partial` if the demonstration is a test that
should exist in the tree and does not. Code alone never makes a "demonstrated
by" AC `met`.

### 2. Findings

Report defects in the merged change. Each finding needs:

* `file` and `line`: a path relative to the root of the source tree and a line
  number in the post-merge file. If the defect is an absence, cite the nearest
  line where the code should have acted.
* `severity`, exactly one of:
  * `blocker`: the change does not do what the issue requires on a main path,
    corrupts or loses data, breaks existing behaviour, opens a security hole,
    or cannot work as written (wrong API, wrong type, unreachable code on the
    required path).
  * `major`: a real defect that will produce wrong results or failures in
    realistic use, or a required behaviour that fails on a stated edge case,
    but the main path works.
  * `minor`: style, naming, small inefficiency, unclear message, a missing
    secondary test, or a defect on a path the issue does not require.

  "Realistic use" means an input or sequence of calls of a kind that occurs in
  the repository's own tests, fixtures, documentation or the issue's examples,
  reached through a public entry point. Malformed internal state, or adversarial
  input when the issue is not about robustness, is not realistic use.

  * Two `major` examples. (1) A totals function drops the last row when the
    input list holds more than one currency, and the issue's own example has two
    currencies: wrong results in ordinary use. (2) A validator rejects a value
    that appears in the repository's own fixtures, so a user entering ordinary
    data gets an error, although the rest of the flow works.
  * Two `minor` examples. (1) An error message names the wrong field but the
    failure path itself is correct and the request is rejected as required.
    (2) A helper recomputes a value twice, or a secondary path the issue does not
    require lacks a test; results are unaffected.
  * Boundary: if the wrong result needs input the repository never produces and
    the issue never mentions, it is `minor`; if it affects the path the issue
    exists to fix, it is `blocker`.

* `evidence`: a concrete chain a second reader can follow by reading code:
  quote or cite the exact lines, state the input, trace the control flow, and
  state the wrong output or failure. "Looks risky" is not evidence. You cannot
  run code, so do not claim a test fails unless you can trace why from source.
* `verifiable_by_inspection`: `true` if the claim can be confirmed or refuted by
  reading the code; `false` if confirming it would require executing something.

Report a finding only if you would defend it to the author. Do not pad. A change
that is sound has few or no findings; an empty list is a valid answer. Do not
report anything about commit hygiene, process, documentation of the process, or
who or what wrote the change: you have no information about those.

### 3. Unrequested scope

List changes in the diff that the issue neither asks for nor needs
(`significance`: `minor` for a small, harmless addition; `significant` for a
feature, behaviour change or refactor that a reviewer would reasonably have
asked to be split out). Renames, formatting, and tests that serve the requested
change are not unrequested scope.

### 4. Test adequacy

You cannot execute tests, so adequacy is judged by tracing. Rate `adequate`,
`partial` or `inadequate`:

* `adequate`: for each requested behaviour you can name a specific test
  (`file:line`) whose assertion you traced against the implementation and that
  would fail if the behaviour were removed or inverted, and there is at least
  one failure or edge case per behaviour or edge case the issue names.
* `partial`: tests exist but leave a requested behaviour or a named edge case
  untested, assert too little to catch a regression, or you cannot trace an
  assertion (generated tests, tests that depend on an environment you were not
  given). Say which in the rationale.
* `inadequate`: the requested behaviour is largely untested, or the tests are
  tautological.

Evidence that does not suffice for `adequate`: a test that calls the code
without asserting an outcome; a snapshot or "does not throw" check alone; a mock
that replaces the unit under test; an assertion on a constant; a test name that
claims coverage the body does not deliver.

## Grade anchors (1 to 5)

The grade is a deterministic function of the verified facts. After the
verification pass the runner discards every blocker or major finding, and every
`partial` or `not_met` AC, that a separate verifier did not confirm, then
recomputes the grade with the rules below. You also give your own grade using
the same rules, from your own findings, so the two can be compared.

Count only verified or, for your own grade, your own blocker and major
findings. Let `B` be the blockers, `M` the majors, `N` the `not_met` ACs, `P`
the `partial` ACs. The grade is the minimum of every cap that applies:

| cap | applies when |
| --- | --- |
| 1 | `B >= 2`, or `B >= 1` and `N >= 1`, or `N >= 3` |
| 2 | `B == 1` (no `not_met` AC), or `N == 2` (no blocker), or `M >= 3`, or `P >= 2` |
| 3 | `N == 1` (no blocker), or `M == 2`, or `P == 1`, or test adequacy `inadequate` |
| 4 | `M == 1`, or test adequacy `partial`, or any `significant` unrequested scope, or `assessable_fraction < 0.8`, or any unresolved blocker/major claim |
| 5 | none of the above |

Notes on the caps:

* One blocker with no `not_met` AC caps at 2: the change fails a main path but
  the issue's other requirements are met. A blocker together with a `not_met` AC
  means the issue is not delivered: 1. One `not_met` AC with no blocker caps at
  3: a stated requirement is missing and nothing is broken.
* `assessable_fraction` is the number of ACs with status `met`, `partial` or
  `not_met` divided by the total number of ACs (`not_assessable` ACs are the
  rest). Report it as a number between 0 and 1 in your output. A change whose
  ACs mostly cannot be judged from source cannot earn a 5: when it is below 0.8,
  or when there are no ACs at all (fraction 0), the grade is capped at 4 and the
  result is flagged low confidence. `not_assessable` ACs themselves never count
  as defects.
* A claim the verifier could not settle (`unverifiable`, or not verified at
  all) is not counted as a defect, but it is counted and reported as unresolved.
  An unresolved blocker or major finding caps the grade at 4 and flags low
  confidence; an unresolved `partial`/`not_met` AC becomes `not_assessable` and
  so lowers `assessable_fraction`. An unverified claim therefore never lifts a
  grade to 5.
* Minor findings never lower the grade.

Reviewers tend to report something even on sound work. The absolute grade is
not meaningful on its own; only differences between groups of changes are.
Calibrate yourself accordingly: do not invent a major finding to justify a
grade below 5, and do not withhold a real blocker to keep the grade high.
