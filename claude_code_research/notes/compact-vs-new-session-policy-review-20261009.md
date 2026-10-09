# Compact vs new session: three-model policy review (2026-10-09)

Question: is the `new-session` policy too quick to recommend a new session and too strict about `/compact`? Should relatedness of the next task replace the "same issue" test? Reviewed independently by Sonnet, Opus and Fable from the same brief; full reports are in `.scratch/compaction-policy-{sonnet,opus,fable}.md` (local only). Outcome shipped as kaybenleroll/dotfiles#294 (PR #296) and #295 (PR #297).

## Agreed by all three
- "Same issue" is the wrong gate. 44% of 217 titled sessions have no referent for it (Sonnet); 172 of 241 sessions at 300k+ touch six or more issues (Fable). The next issue does share more files with earlier work (31%, against 7% for random pairs in a project; Opus), so relatedness is real evidence, but not the test.
- The deciding question is whether the next step needs state that exists only in the conversation or live session, not in an issue, PR, commit or `.scratch` file.
- Cost barely separates compaction from a new session; a new session is cheaper by roughly $0.10-0.25 per seam (Opus, Fable). Both beat continuing at 300k+ when real work remains.
- Compaction loses identifiers: about 54% kept (Opus), 6% of once-mentioned anchors (Sonnet); a second compaction keeps 20-30% of the first's. 24 of 26 historical compactions had no focus text (Sonnet); 2 of 26 produced no summary (Fable).
- The flat `turns_remaining_min = 5` was wrong: break-even falls as context grows, and it blocked 73% of compactions at 300k (Opus).

## Disagreed, left unchanged
- `seam` rung: Opus suggested about 250k. `strong` rung: Sonnet suggested 400k. Fable kept both. The 600k window and the cap of one compaction per session were kept by all three.
- Revisit when five measured compactions exist (dotfiles#275 AC7). Corpus compaction counts differed across reports (16, 26, 27), so fidelity evidence is thin.

## Changes made
- #294: `compact.turns_required_by_reclaimable` replaces the flat value (Fable's table; Opus's lower figures noted as the outlier). Policy stays `provisional`.
- #295: Compact branch of `new-session/SKILL.md` keyed on unrecorded conversation state; relatedness a tie-break; every compact recommendation needs a facts file and a focus string.
- Deferred: failed-summary detection (revisit if a second no-summary compaction occurs).

Confidence from the reviews: axis 75-80%; exact turn numbers medium (about +-40%); that compacting into a related issue is a net gain, 40% (Sonnet).
