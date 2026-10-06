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

Rate `adequate`, `partial` or `inadequate`:

* `adequate`: the tests added or changed exercise each requested behaviour,
  include at least one failure or edge case per behaviour the issue names, and
  would fail if the behaviour regressed.
* `partial`: tests exist but leave a requested behaviour or a named edge case
  untested, or assert too little to catch a regression.
* `inadequate`: the requested behaviour is largely untested, or the tests are
  tautological.

## Grade anchors (1 to 5)

The grade is a deterministic function of the verified facts. After the
verification pass the runner discards every blocker or major finding, and every
`partial` or `not_met` AC, that a separate verifier did not confirm, then
recomputes the grade with the rules below. You also give your own grade using
the same rules, from your own findings, so the two can be compared.

Count only verified or, for your own grade, your own blocker and major
findings. The grade is the minimum of every cap that applies:

| grade | anchor |
| --- | --- |
| 5 | Every assessable AC is `met`; no blocker; no major; test adequacy `adequate`; no `significant` unrequested scope. Minor findings do not lower the grade. |
| 4 | Every assessable AC is `met`; no blocker; at most one major; test adequacy at least `partial`; unrequested scope may be `significant`. |
| 3 | No AC is `not_met`; no blocker; at most two majors; at most one AC is `partial`; test adequacy may be `inadequate`. |
| 2 | No AC is `not_met`; no blocker; three or more majors, or two or more ACs `partial`. |
| 1 | Any AC is `not_met`, or any blocker. |

Equivalent rule set used by the runner, applied in this order, taking the
lowest result:

1. Any `blocker`, or any AC `not_met`: 1.
2. Three or more `major`, or two or more AC `partial`: 2.
3. Exactly two `major`, or exactly one AC `partial`, or test adequacy
   `inadequate`: 3.
4. Exactly one `major`, or test adequacy `partial`, or any `significant`
   unrequested scope: 4.
5. Otherwise: 5.

`not_assessable` ACs never lower the grade. An issue with no assessable ACs is
graded on findings, tests and scope alone.

Reviewers tend to report something even on sound work. The absolute grade is
not meaningful on its own; only differences between groups of changes are.
Calibrate yourself accordingly: do not invent a major finding to justify a
grade below 5, and do not withhold a real blocker to keep the grade high.
