# Stress-Test Corpus Audit Playbook

**What this is:** a self-contained, runnable methodology for empirically auditing a corpus of plan files that carry a `## Stress-Test Log` section (the format written by the `/stress-test` skill's plan-family logging — see `~/.claude/skills/stress-test/SKILL.md` if you have it; the method below only assumes the log shape documented in Step 1, not the skill itself). It answers questions like: how many passes do plans typically take to converge, whether plan size predicts pass count, how often the take-stock mechanism fires and how well each of its options (A/B/C/D) performs, and whether coupling/complexity was detectable before drafting or only discovered during review.

**How to invoke:** drop this file anywhere in the target repo/workspace and run each numbered step's command in order. Requires only `bash`, `grep`, `find`; `python3` or `awk` optional for the heavier extraction/aggregation steps. No network access needed.

**Ground rule:** this is read-only analysis. Nothing here modifies any plan file.

---

## Step 1 — Discover the corpus

**Goal:** find every file containing a `## Stress-Test Log` section, across every location plans might live (`~/.claude/plans/`, `docs/plans/`, `.scratch/`, or wherever the target project stores them).

**Command:**
```bash
find . ~/.claude/plans -type f -name '*.md' 2>/dev/null \
  | xargs grep -l '## Stress-Test Log' 2>/dev/null \
  | sort -u > corpus_files.txt
wc -l corpus_files.txt
```

**Pitfall — corpus discovery must be case-insensitive, and must not key off the take-stock keyword.**
A tempting shortcut is to grep for the take-stock trigger word instead of the log section header, e.g. `grep -rl 'TAKE-STOCK'`. Don't. Two failure modes stack here:
- Case sensitivity: real log entries mostly write `Take-stock` or `take-stock` in prose (e.g. inside a `Resolution:` line or an `Action:` line); only the sanctioned marker line (`### <timestamp> — TAKE-STOCK RESOLVED — ...`) uses the literal uppercase form. A case-sensitive grep for the uppercase string alone can miss the large majority of real hits — in one real audit it missed 35 of 38.
- Wrong anchor entirely: take-stock is a *conditional* mechanism (fires only past a streak threshold) — most plans in a corpus never trigger it at all, so grepping for it as the corpus membership test silently excludes every plan that converged cleanly. The `## Stress-Test Log` heading, by contrast, is written into every reviewed plan regardless of whether take-stock ever fired. Always use the section heading as the corpus test; only grep for take-stock (case-insensitively, `-i`) when you specifically get to Step 4.

**Sanity-check before trusting this list:** open 2-3 files at random from `corpus_files.txt` and manually confirm each has a real `## Stress-Test Log` heading followed by at least one `### ` entry — a bare grep hit could in principle come from a file merely *quoting* the heading text in prose (rare, but check). Also run the case-insensitive take-stock grep across the same corpus and confirm its hit count is a plausible subset, not near-zero or near-100% (either extreme suggests the case-sensitivity bug above).

---

## Step 2 — Deduplicate the corpus

**Goal:** collapse duplicate and near-duplicate files so each real plan is counted exactly once.

**Pass A — exact duplicates (byte-identical):**
```bash
while read -r f; do md5sum "$f"; done < corpus_files.txt \
  | sort | awk '{print $1}' | uniq -c | sort -rn | awk '$1>1{print}'
```
Any hash with count >1 is a byte-identical duplicate — e.g. a plan mirrored verbatim into two directories (a common cause: a file copied into `.scratch/` for convenience without deleting the original). For each duplicate group, keep exactly one file (prefer the canonical plan-storage location over a scratch/temp copy) and drop the rest from `corpus_files.txt`.

**Pitfall — deduplication needs two passes, not one; hash dedup only catches the first class.**
Byte-hash dedup catches only exact copies. It does **not** catch a second, distinct class: two files that are near-duplicates because they tell the *same* take-stock storyline at different points in its life — e.g. an early snapshot of a plan captured in one location, and its fuller continuation (more passes appended, later verdict) saved in another location. These have different content (more entries in the later one) so hash dedup treats them as unrelated. Two wrong ways to handle this:
- Naive: count both as two separate plans → inflates plan count and double-counts every pass/take-stock event the earlier snapshot shares with the later one.
- Over-eager: run a generic text-similarity/near-duplicate detector and collapse anything above a similarity threshold → risks merging genuinely distinct plans that happen to share boilerplate structure or a common template.

**Pass B — continuation pairs (do this manually or with a lightweight heuristic, not a similarity threshold):**
```bash
# Heuristic candidate list: same title (line 1, stripped of leading '#') appearing
# more than once across different directories.
while read -r f; do
  title=$(head -1 "$f" | sed 's/^#\+ *//')
  printf '%s\t%s\n' "$title" "$f"
done < corpus_files.txt | sort > titles.tsv
cut -f1 titles.tsv | sort | uniq -d
```
For each title that appears more than once, open every candidate file and confirm by hand whether they are genuine continuations of the same plan (same title/slug, one clearly a subset of the other's log history) rather than coincidentally-named distinct plans. For a confirmed continuation pair, keep only the **more-advanced** file — the one with the longer `## Stress-Test Log` (more `### ` entries) and the later/terminal final verdict — and drop the earlier snapshot from `corpus_files.txt`. Do not pick arbitrarily between the pair; the earlier snapshot's data is a strict subset of the later file's, so keeping the earlier one loses information and keeping both double-counts it.

**Sanity-check:** after both passes, `wc -l corpus_files.txt` should be strictly less than or equal to the Step 1 count, and every dropped file should have a documented reason (exact-duplicate hash match, or confirmed continuation pair) — never drop a file on suspicion alone.

---

## Step 3 — Extract pass counts per plan

**Goal:** for each plan file, count how many stress-test passes it took to reach a terminal verdict (or how many it has accumulated so far if still open).

**The log entry shape** (from the stress-test log format): each pass is a `### ` line whose title is dash (`—` or `-`)-delimited, e.g.:
```
### 2026-07-27 14:03 — Pass 3 · Iteration 3 (opus) — CLEAN
### 2026-07-20 09:41 — Pass 2 · Iteration 2 (opus) — RERUN_NEEDED
```
Titles are **not guaranteed to start with `Pass N`** — a leading timestamp is normal, and a title may mention a pass number in prose without *being* that pass's entry (e.g. `### Take-Stock Resolution (as flagged in Pass 3) — UNSETTLED` is not pass 3's entry).

**Pitfall — the pass-entry test must anchor on the first dash-delimited segment, trimmed, not scan the whole line, and must not fall back to a bare status-token match.**
Two distinct failure modes if you get this wrong:
1. **Assuming segment 1 literally is `Pass N`.** A title like `2026-07-20 09:41 — Pass 2 · Iteration 2 (opus) — RERUN_NEEDED` has the timestamp as an earlier token but `Pass 2 · Iteration 2 (opus)` as the actual first `—`-delimited *segment* (split on `—`, not on whitespace) — a parser that requires the string to begin with the literal characters `Pass` will wrongly reject every entry with a leading timestamp, which is most of them.
2. **Matching `Pass N` anywhere in the line instead of anchored to the start of that first segment.** A bullet or title that merely *references* an earlier pass ("as flagged in Pass 3", "supersedes Pass 1's fix") must NOT be counted as its own pass entry — only a segment that, once trimmed of leading/trailing whitespace, *starts with* `^Pass <digits>` or `^Run <digits>` (case-insensitive) counts. A parser that searches the whole line for the substring `Pass \d+` anywhere will over-count. One real run produced a corrupted result (a 14,000+ "pass" outlier) from exactly this bug — treating every substring mention of a pass number as a distinct pass entry.

**Robust extraction — split each `### ` line on `—`, take the first segment, trim it, test the anchor:**
```bash
extract_passes() {
  local f="$1"
  awk '/^### /{print}' "$f" | while IFS= read -r line; do
    # strip leading "### ", then split on em-dash or hyphen-as-delimiter
    body="${line#### }"
    # first dash-delimited segment (handles both — and standalone -)
    seg1=$(printf '%s\n' "$body" | awk -F' — ' '{print $2}')
    [ -z "$seg1" ] && seg1=$(printf '%s\n' "$body" | awk -F' - ' '{print $2}')
    seg1_trimmed=$(printf '%s' "$seg1" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
    if printf '%s' "$seg1_trimmed" | grep -qiE '^(pass|run)[[:space:]]+[0-9]+'; then
      printf '%s\n' "$seg1_trimmed"
    fi
  done
}
extract_passes "path/to/plan.md" | wc -l
```
A `python3` equivalent, if available, is more robust against edge cases (multiple dash styles, `Passes N-M` ranges counting as `M-N+1`):
```python3
import re, sys
pat = re.compile(r'^(pass|run)\s+(\d+)', re.IGNORECASE)
range_pat = re.compile(r'^passes?\s+(\d+)\s*[-–]\s*(\d+)', re.IGNORECASE)
count = 0
for line in open(sys.argv[1]):
    if not line.startswith('### '):
        continue
    body = line[4:].strip()
    seg1 = re.split(r'—|(?<!\d)-(?!\d)', body, maxsplit=1)[0].strip()
    m = range_pat.match(seg1)
    if m:
        count += int(m.group(2)) - int(m.group(1)) + 1
        continue
    if pat.match(seg1):
        count += 1
print(count)
```

**Sanity-check before trusting this per-plan:** for every plan, the extracted pass count must be a small integer sane for a document review process — flag and manually inspect any single plan reporting more than ~15-20 passes as a probable extraction bug before including it in aggregate stats. Cross-check a handful of plans by eye (open the file, count `### Pass N` entries visually) against the script's count and confirm they match exactly.

---

## Step 4 — Extract take-stock events and option choices

**Goal:** for each plan that hit the take-stock threshold, record which option (A/B/C/D) was chosen and what happened next.

**Command (find candidate plans, case-insensitive):**
```bash
grep -lir 'take-stock' $(cat corpus_files.txt) > takestock_files.txt
```
For each file in `takestock_files.txt`, find the resolution marker line:
```bash
grep -n 'TAKE-STOCK RESOLVED' plan.md
```
This marker's own text format names the option and the pass number, e.g. `### <timestamp> — TAKE-STOCK RESOLVED — Option <A|C|D> at Pass <N>` (Option B — restructure — is recorded differently, typically via a `COUNTER RESET` marker rather than a `TAKE-STOCK RESOLVED` line, since restructuring resets pass numbering; grep for `COUNTER RESET` separately to catch these). Extract the option letter and the pass number `N` it was resolved at.

**For each take-stock event, record two independent outcomes (see Step 5/Interpreting Results for why both are required):**
1. **Immediate outcome:** what is the `VERDICT` of the very next `### ` pass entry after pass `N` (by chronological/pass-number order, not file order)? Terminal here means `CLEAN` or `ACCEPTED` on that entry's own merits.
2. **Eventual outcome:** what is the `VERDICT` of the *last* entry in the plan's log (chronologically last, which — per the log format's newest-first ordering convention — is usually the topmost `### ` entry under the header)? Terminal means `CLEAN`/`ACCEPTED`; non-terminal means `RESTRUCTURE`/`UNSETTLED`/still open with no closing entry.

**Sanity-check:** the immediate-outcome pass number you're checking must be strictly greater than `N` (the take-stock resolution pass) and must be the *next* one chronologically, not just any later pass — verify by eye on 2-3 examples that you're reading pass numbers in ascending order relative to the marker, not accidentally checking a pass from before the take-stock event.

---

## Step 5 — Plan size vs pass count

**Goal:** test whether plan length (as a rough coupling/complexity proxy) predicts pass count.

**Command:**
```bash
for f in $(cat corpus_files.txt); do
  lines=$(wc -l < "$f")
  passes=$(extract_passes "$f" | wc -l)  # from Step 3
  printf '%s\t%s\t%s\n' "$lines" "$passes" "$f"
done | sort -n > size_vs_passes.tsv
```

**Pitfall — plan size must be measured consistently (e.g. total file line count, or line count of content *above* the `## Stress-Test Log` section if you want size independent of log length).** The log section itself grows with pass count, so if you measure whole-file size, size and pass-count are partially correlated by construction, not by the effect under test — inflating any apparent correlation. Prefer measuring only the lines above the `## Stress-Test Log` header:
```bash
awk '/^## Stress-Test Log/{exit} {print}' plan.md | wc -l
```

**Sanity-check:** spot-check the smallest and largest plans by content-line-count — do they look like genuinely small/large plans by eye, or is the count dominated by something irrelevant (e.g. an embedded code block, a large table)? A raw line-count proxy is coarse; note this caveat in any report rather than treating it as a precise complexity metric.

---

## Interpreting Results

The steps above compute numbers. These four points govern how to read them correctly — get the arithmetic right and still draw a wrong conclusion without these.

**1. Report option performance as two separate numbers, never one blended "did it work" stat.** Immediate convergence (next pass terminal) and eventual convergence (ever reaches terminal) can diverge substantially for the same option in the same corpus — a single "convergence rate" conflates them and produces results that look contradictory across different audits of the same data because each audit silently picked a different one of the two measures. Always present both, labeled explicitly.

**2. Option C's "immediate success" rate is tautological, not informative, and must be flagged as such wherever shown.** Option C is "accept the known gaps, stop stress-testing." Choosing to stop is definitionally choosing not to continue — so by construction there is no next pass to fail, and immediate-outcome measurements for C will read close to 100%. This is not evidence that C is the right choice more often than A/B/D; it is a property of how the measure is defined for a terminal-by-choice option. State this caveat inline next to any Option C statistic, don't just footnote it once and let readers re-encounter the number without context.

**3. Watch for self-fulfilling "immediate convergence" via a re-triggered take-stock resolved by Option C.** A pass logged immediately after a take-stock choice can itself hit the take-stock threshold again and get resolved via Option C in that same next entry. A loose scoring rule ("next entry exists and isn't RERUN_NEEDED") will misclassify this as "the chosen option converged immediately," when what actually happened is the reviewer stopped one pass later rather than the chosen option succeeding. Score strictly: only count immediate convergence when the very next entry is a genuine `CLEAN`/`ACCEPTED` verdict reached on its own merits — a next entry that is itself a `TAKE-STOCK RESOLVED — Option C` marker does not count as the *original* option converging.

**4. Never pool option-performance numbers across corpora/projects — always report per-corpus.** The same option can show materially different convergence rates measured on different projects/corpora, and this can be a genuine effect of that corpus's plan style, reviewer, or domain rather than a measurement artifact (confirm via a targeted reconciliation check — re-verify the raw entries for a handful of cases in each corpus — before concluding a cross-corpus difference is real rather than a counting bug). Whatever the actual numbers come out to for a given corpus, present them scoped to that corpus by name/identifier, and do not average them into a single portable "Option X converges Y% of the time" claim — treat any option-performance finding as project-specific unless it has been independently replicated on a second, separately-audited corpus.

**5. Mark decidability-at-drafting-time judgments with an explicit confidence level, never assert flatly.** When a plan runs long (many passes, take-stock fired, possibly RESTRUCTURE), a natural follow-up question is whether the root cause (typically coupling/complexity) would have been visible before drafting, from the plan's stated Context/Approach, versus only surfaced during adversarial review. Answering this requires reading the finished plan after the fact and making a retrospective judgment call — it is not a mechanically extractable fact. For each plan assessed this way, record one of three explicit labels rather than picking a side by default:
   - `apparent` — the coupling/complexity is visible in the plan's own Context/Approach section, stated or clearly implied, before any review pass.
   - `emerged-later` — the plan's stated context gives no indication; the issue surfaces only in review findings.
   - `unsure` — the retrospective call is genuinely ambiguous.
   Do not round `unsure` cases into either bucket to produce a cleaner-looking split — an inflated "N% were apparent at drafting time" number built by force-classifying ambiguous cases is not a finding, it's noise dressed as one.
