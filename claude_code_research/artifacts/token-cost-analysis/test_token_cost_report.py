#!/usr/bin/env python3
"""Unit tests for token_cost_report.py / extractor.py (issue #101).

Step 4 of the plan at `.claude/plans/greedy-roaming-horizon.md` implements
the keep-max dedup restructure. Steps 2/3 wrote a red-before-green safety
net scoped to what was assertable against *pre-Step-4* (keep-first)
behaviour; most of those assertions were durable (order-independence-of-
totals, cache-absent/nested-vs-flat-fallback shape on single-occurrence
messages) and still pass unchanged. Four assertions pinned keep-first's
specific *tie-break* or *winner-selection* choice and are flipped here to
the keep-max equivalent, now that Step 4 has landed:

- `test_stub_then_settled_keeps_settled` -- flipped in Step 3 already
  (the core #101 regression); unchanged in this commit.
- `test_tie_on_output_last_seen_wins` (formerly
  `test_tie_on_output_pins_current_first_seen`) -- keep-max breaks output
  ties by keeping the LAST-seen occurrence (see plan Decision 1), the
  opposite of keep-first's tie behaviour.
- `test_whole_record_selected_not_per_field` -- proj-fieldmix's msg_F1 has
  its winner flip from occ1 (input=9999, output=2) to occ2 (input=10,
  output=800), since occ2 has the larger output. The point of the test is
  unchanged (the winner's input travels with its own output, never mixed
  across occurrences) but the winning occurrence itself is different now.
- `test_cross_file_duplicate_collapsed` -- proj-crossfile's msg_X1 winner
  flips from file_a's occurrence (output=10) to file_b's (output=999),
  since keep-max dedup is still keyed globally across files but now
  selects by output value, not file-sort order.
- `TestUsageFieldPreservation.test_cache_shape_counters_from_kept_record` --
  proj-cacheshapes' msg_C5 duplicate pair TIES on output (30 == 30): occ1
  is nested-shape, occ2 is flat_fallback-shape. Under keep-first, occ1 (the
  first-seen) won and counted as nested. Under keep-max's last-seen-wins
  tie-break, occ2 now wins, so msg_C5 counts as flat_fallback instead of
  nested -- this was not anticipated by this fixture's original design (it
  was built to test cache-shape-from-kept-record generically, not as a
  tie-break case), but the same last-seen-wins tie rule applies here as in
  the tiebreak fixture above.

TestWindowAttribution and TestCounterAccounting are filled in below for the
first time -- Step 4 is what introduces the counters they assert on
(msgids_boundary_rescued/_dropped/_day_straddled, distinct_msgids_total,
window_msgids_kept). TestRealCorpusInvariants (which needs
tools/measure_dup_msgids.py as a library, per the plan's Tests section) is
a separate step and not present here.
"""
import ast
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import extractor  # noqa: E402
import token_cost_report  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES_ROOT = os.path.join(HERE, "tests", "fixtures", "projects")
EXTRACTOR_PATH = os.path.join(HERE, "extractor.py")


def run_extract(root, since=None, until=None, project=None):
    """Calls extractor.scan() -- the same function token_cost_report.main()
    calls -- so a pass here means the shipped path works. `project` filters
    the returned `buckets` list to one project after the scan (mirroring
    session-analysis/test_session_analysis.py:49's run_scan() convention).
    meta and msgid_contributions are NOT project-filtered -- they are
    global to whatever `root` was scanned, so callers needing an isolated
    meta count must pass a narrower `root` (a single fixture project's own
    directory) instead of relying on this filter."""
    result = extractor.scan(root, since or "", until or "")
    if project is not None:
        result = dict(result)
        result["buckets"] = [b for b in result["buckets"] if b["project"] == project]
    return result


def bucket_totals(buckets):
    """Sums a list of bucket records into one dict -- used where a test
    wants the aggregate across every (day, model) bucket in a project
    rather than a single bucket row."""
    out = {"input": 0.0, "cache_write_5m": 0.0, "cache_write_1h": 0.0, "cache_read": 0.0, "output": 0.0, "lines": 0}
    for b in buckets:
        for k in out:
            out[k] += b[k]
    return out


def sole_bucket(buckets):
    if len(buckets) != 1:
        raise AssertionError("expected exactly one bucket, got %d: %r" % (len(buckets), buckets))
    return buckets[0]


# --------------------------------------------------------------------------
# TestKeepMaxDedup
# --------------------------------------------------------------------------


class TestKeepMaxDedup(unittest.TestCase):
    """proj-keepmax / proj-keepmax-reversed / proj-tiebreak / proj-fieldmix /
    proj-crossfile. All assertions here pin CURRENT (keep-first) behaviour
    except test_stub_then_settled_keeps_settled, which Step 3 flips to the
    FUTURE (keep-max) expected value -- see that test's docstring."""

    # proj-keepmax and proj-keepmax-reversed deliberately reuse the SAME
    # message ids (msg_K1/K2/K3, per the plan's fixture spec) so the
    # reversed-order test below can prove order-independence on identical
    # ids. But extractor.scan()'s dedup is keyed globally by message.id
    # ALONE, with no project scoping (see plan Risk 5) -- so scanning both
    # projects together under one shared `root` would collapse msg_K1
    # across the two projects as if they were the same duplicate group,
    # silently dropping one project's data instead of testing either one.
    # Every test touching this fixture pair therefore scans each project's
    # own directory as an ISOLATED `root`, not the shared FIXTURES_ROOT +
    # project filter every other test in this file uses.
    KEEPMAX_ROOT = os.path.join(FIXTURES_ROOT, "proj-keepmax")
    KEEPMAX_REVERSED_ROOT = os.path.join(FIXTURES_ROOT, "proj-keepmax-reversed")

    def test_stub_then_settled_keeps_settled(self):
        # msg_K1: stub (output=3) occurs first, settled (output=1200) second.
        # This is the core #101 regression: the FUTURE keep-max policy must
        # keep the settled value, 1200. Today's code still implements
        # keep-first (keeps the stub, 3) -- Step 4 has not landed yet, so
        # this assertion is EXPECTED TO FAIL until it does. Flipped in Step 3
        # of the plan; do not "fix" this failure here.
        result = run_extract(self.KEEPMAX_ROOT)
        rec = result["msgid_contributions"]["msg_K1"]
        self.assertEqual(rec["output"], 1200)

    def test_settled_then_stub_keeps_settled(self):
        # msg_K2: settled (1200) occurs first, stub (3) second. Under
        # keep-first this already keeps 1200 -- the SAME value keep-max
        # would pick -- so this assertion holds both now and after Step 4.
        # It proves the fixture isn't accidentally testing "keep-last"
        # instead of "keep-max": K1 and K2 are mirror images of each other.
        result = run_extract(self.KEEPMAX_ROOT)
        rec = result["msgid_contributions"]["msg_K2"]
        self.assertEqual(rec["output"], 1200)

    def test_reversed_order_yields_identical_bucket_totals(self):
        # proj-keepmax-reversed is the same 3 messages, same ids, with the
        # file's lines in reverse order. Under today's keep-first policy,
        # WHICH occurrence of K1/K2 individually wins swaps between the two
        # projects (K1 goes from 3->1200, K2 goes from 1200->3), but the
        # bucket TOTAL is unaffected by that swap (3+1200 == 1200+3) -- so
        # this equality holds today and continues to hold, unchanged, after
        # Step 4 (where it would be 1200+1200 == 1200+1200 for a different
        # but still-equal reason: order-independence of keep-max itself).
        fwd = run_extract(self.KEEPMAX_ROOT)
        rev = run_extract(self.KEEPMAX_REVERSED_ROOT)
        self.assertEqual(bucket_totals(fwd["buckets"]), bucket_totals(rev["buckets"]))

    def test_byte_identical_repeat_not_double_counted(self):
        # msg_K3 appears twice, byte-identical, output=500 both times.
        # Never double-counted under either policy.
        result = run_extract(self.KEEPMAX_ROOT)
        rec = result["msgid_contributions"]["msg_K3"]
        self.assertEqual(rec["output"], 500)

    def test_tie_on_output_last_seen_wins(self):
        # proj-tiebreak: msg_T1 occurs twice with EQUAL output (700) but
        # different days (2026-06-03, 2026-06-20). Keep-max's tie-break is
        # "last seen wins" (plan Decision 1) -- the OPPOSITE of keep-first,
        # which kept whichever occurrence was first in file order.
        result = run_extract(FIXTURES_ROOT, project="proj-tiebreak")
        b = sole_bucket(result["buckets"])
        self.assertEqual(b["day"], "2026-06-20")
        self.assertEqual(b["output"], 700)
        rec = result["msgid_contributions"]["msg_T1"]
        self.assertEqual(rec["day"], "2026-06-20")

    def test_whole_record_selected_not_per_field(self):
        # proj-fieldmix: msg_F1 occ1 has input=9999/output=2, occ2 has
        # input=10/output=800. occ2's output is larger, so keep-max selects
        # occ2's WHOLE record -- input=10 AND output=800 together, never a
        # per-field mix (e.g. input=9999 paired with output=800 would mean
        # the code picked fields from different occurrences, which it never
        # does). input=10 traveling with the winner, not occ1's larger
        # 9999, is exactly what proves whole-record selection here.
        result = run_extract(FIXTURES_ROOT, project="proj-fieldmix")
        rec = result["msgid_contributions"]["msg_F1"]
        self.assertEqual(rec["input"], 10)
        self.assertEqual(rec["output"], 800)

    def test_cross_file_duplicate_collapsed(self):
        # proj-crossfile: msg_X1 appears once in file_a.jsonl (output=10)
        # and once in file_b.jsonl (output=999) -- same project, two
        # different files. Dedup is keyed globally by message.id, not
        # per-file, so this must collapse to one contribution regardless of
        # which file it came from. Keep-max selects file_b's occurrence
        # (999 > 10) even though file_a sorts first -- winner selection is
        # by output value, not file-scan order.
        root = os.path.join(FIXTURES_ROOT, "proj-crossfile")
        result = run_extract(root)
        rec = result["msgid_contributions"]["msg_X1"]
        self.assertEqual(rec["output"], 999)
        b = sole_bucket(result["buckets"])
        self.assertEqual(b["lines"], 1)
        self.assertEqual(result["meta"]["duplicate_lines_skipped_global"], 1)

    def test_keep_max_upgrades_nonzero_and_zero(self):
        # proj-keepmax: only msg_K1 (3 -> 1200) is a genuine upgrade;
        # msg_K2's second occurrence (3) is smaller than its first (1200)
        # so no upgrade, and msg_K3's tie (500 == 500) doesn't count as an
        # upgrade either (only a strict increase does) -- so exactly 1.
        upgraded = run_extract(self.KEEPMAX_ROOT)
        self.assertEqual(upgraded["meta"]["keep_max_upgrades"], 1)
        self.assertEqual(upgraded["meta"]["output_tokens_gained_by_keep_max"], 1197)

        # proj-tiebreak: msg_T1's tie (700 == 700) never counts as an
        # upgrade, even though the winner changes (last-seen-wins). Scanned
        # as its own isolated root -- meta counters are global-to-root, not
        # project-filtered (see run_extract's docstring).
        tied = run_extract(os.path.join(FIXTURES_ROOT, "proj-tiebreak"))
        self.assertEqual(tied["meta"]["keep_max_upgrades"], 0)
        self.assertEqual(tied["meta"]["output_tokens_gained_by_keep_max"], 0)


# --------------------------------------------------------------------------
# TestNoMessageId
# --------------------------------------------------------------------------


class TestNoMessageId(unittest.TestCase):
    """proj-nomsgid: three byte-identical usage lines with no message.id.
    proj-nomsgid is the ONLY fixture project that omits message.id, so
    scanning the whole FIXTURES_ROOT tree gives an isolated
    lines_missing_message_id count without needing a narrower root."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_extract(FIXTURES_ROOT)

    def test_no_id_lines_never_collapsed(self):
        buckets = [b for b in self.result["buckets"] if b["project"] == "proj-nomsgid"]
        totals = bucket_totals(buckets)
        self.assertEqual(totals["lines"], 3)
        self.assertEqual(totals["output"], 150)  # 50 * 3, no dedup collapse

    def test_in_window_lines_missing_message_id_count(self):
        # Only proj-nomsgid's 3 lines lack message.id anywhere in the
        # fixture tree, and all 3 fall inside the unrestricted (full-
        # history) window used here -- so this count is isolated by
        # fixture design, not by narrowing `root`.
        self.assertEqual(self.result["meta"]["lines_missing_message_id"], 3)

    def test_corpus_wide_lines_missing_message_id_count(self):
        # New Step-4 counter: corpus-wide (not window-gated) count of
        # no-message.id lines. No fixture project provides a no-msgid line
        # OUTSIDE the full-history window used here, so this equals the
        # in-window count (3) on this fixture set -- the point of this test
        # is confirming the counter is wired up and reporting correctly,
        # not exercising a windowed divergence.
        self.assertEqual(self.result["meta"]["lines_missing_message_id_corpus_wide"], 3)

    def test_synthetic_keys_absent_from_msgid_contributions(self):
        # Current code has no synthetic-key mechanism at all (that is a
        # Step 4 addition) -- lines with no message.id simply never reach
        # msgid_contributions. Confirm no entry is attributable to
        # proj-nomsgid, and no None key ever appears.
        self.assertNotIn(None, self.result["msgid_contributions"])
        attributed = [
            v for v in self.result["msgid_contributions"].values()
            if v["project"] == "proj-nomsgid"
        ]
        self.assertEqual(attributed, [])


# --------------------------------------------------------------------------
# TestUsageFieldPreservation
# --------------------------------------------------------------------------


class TestUsageFieldPreservation(unittest.TestCase):
    """proj-cacheshapes / proj-models. Cache-shape and pricing-eligibility
    meta counters (cache_nested_lines, cache_flat_fallback_lines,
    cache_absent_lines, unrecognized_cache_key_lines,
    lines_skipped_unknown_model) are global-to-the-scanned-root, so each
    test here scans ONLY that fixture project's own directory as `root`,
    isolating it from every other fixture's cache/model lines."""

    @classmethod
    def setUpClass(cls):
        cls.cache_root = os.path.join(FIXTURES_ROOT, "proj-cacheshapes")
        cls.cache_result = run_extract(cls.cache_root)
        cls.models_root = os.path.join(FIXTURES_ROOT, "proj-models")
        cls.models_result = run_extract(cls.models_root)

    def _rec(self, result, mid):
        return result["msgid_contributions"][mid]

    def test_nested_ttl_split(self):
        rec = self._rec(self.cache_result, "msg_C1")
        self.assertEqual(rec["cache_write_5m"], 40)
        self.assertEqual(rec["cache_write_1h"], 60)

    def test_unrecognized_ttl_summed_at_1h_and_counted(self):
        rec = self._rec(self.cache_result, "msg_C2")
        self.assertEqual(rec["cache_write_5m"], 10)
        self.assertEqual(rec["cache_write_1h"], 200)  # unrecognized ephemeral_3h summed into 1h
        self.assertEqual(self.cache_result["meta"]["unrecognized_cache_key_lines"], 1)
        self.assertEqual(
            self.cache_result["meta"]["unrecognized_cache_keys_seen"], ["ephemeral_3h_input_tokens"]
        )

    def test_nested_all_zero_falls_back_to_flat(self):
        rec = self._rec(self.cache_result, "msg_C3")
        self.assertEqual(rec["cache_write_5m"], 0)
        self.assertEqual(rec["cache_write_1h"], 77)

    def test_cache_absent_counted(self):
        rec = self._rec(self.cache_result, "msg_C4")
        self.assertEqual(rec["cache_write_5m"], 0)
        self.assertEqual(rec["cache_write_1h"], 0)

    def test_cache_shape_counters_from_kept_record(self):
        # C1 (nested), C2 (nested) = 2 nested lines; C3 (flat fallback) = 1.
        # C5 occurs twice and TIES on output (30 == 30): occ1 is
        # nested-shape (cw_5m=5, cw_1h=15), occ2 is flat_fallback-shape
        # (cache_creation_input_tokens=999). Keep-max's tie-break is
        # last-seen-wins (same rule as the tiebreak fixture), so occ2 wins
        # here -- C5 now counts as flat_fallback, not nested. This flips
        # cache_nested_lines from 3->2 and cache_flat_fallback_lines from
        # 1->2 relative to keep-first; cache_absent_lines (C4) is unaffected
        # since C4 has no duplicate.
        meta = self.cache_result["meta"]
        self.assertEqual(meta["cache_nested_lines"], 2)
        self.assertEqual(meta["cache_flat_fallback_lines"], 2)
        self.assertEqual(meta["cache_absent_lines"], 1)
        rec = self._rec(self.cache_result, "msg_C5")
        self.assertEqual(rec["cache_write_5m"], 0)
        self.assertEqual(rec["cache_write_1h"], 999)

    def test_input_and_cache_read_from_kept_record(self):
        rec = self._rec(self.cache_result, "msg_C1")
        self.assertEqual(rec["input"], 200)
        self.assertEqual(rec["cache_read"], 10)

    def test_unknown_model_tier_skipped(self):
        self.assertNotIn("msg_M3", self.models_result["msgid_contributions"])
        self.assertEqual(self.models_result["meta"]["lines_skipped_unknown_model"], 1)
        model_ids = {b["model"] for b in self.models_result["buckets"]}
        self.assertNotIn("custom-model-x", model_ids)

    def test_non_assistant_line_with_usage_still_counted(self):
        # msg_M4 has top-level "type": "user" but a valid message.usage --
        # the extractor does not filter on type == "assistant" (unlike
        # session-analysis), so it must still be counted. Changing this
        # would shift totals -- this test pins that today's behaviour.
        rec = self._rec(self.models_result, "msg_M4")
        self.assertEqual(rec["output"], 50)
        self.assertEqual(rec["model"], "claude-sonnet-5")


# --------------------------------------------------------------------------
# TestWindowAttribution -- proj-boundary. Exercises the deferred-bucketing
# design: window membership and day-bucket assignment follow the WINNER's
# timestamp, not the first occurrence's.
# --------------------------------------------------------------------------


class TestWindowAttribution(unittest.TestCase):
    BOUNDARY_ROOT = os.path.join(FIXTURES_ROOT, "proj-boundary")

    def test_window_membership_follows_winner_timestamp(self):
        # msg_B2: first occurrence 2026-06-03 (output=5, OUTSIDE this
        # window), winner (settled) 2026-06-09 (output=650, INSIDE it). The
        # old dedup-before-window-filter caveat -- a message whose first
        # occurrence fell outside the window was silently lost even if a
        # later occurrence fell inside -- is fixed by this: window
        # membership is now decided by the winner's own timestamp.
        result = run_extract(self.BOUNDARY_ROOT, since="2026-06-05", until="2026-06-30")
        self.assertIn("msg_B2", result["msgid_contributions"])
        rec = result["msgid_contributions"]["msg_B2"]
        self.assertEqual(rec["output"], 650)
        self.assertEqual(rec["day"], "2026-06-09")

    def test_boundary_rescued_increments(self):
        # Same window as above: msg_B2 is rescued (first occurrence outside,
        # winner inside); msg_B1's first AND winner occurrences (2026-06-01,
        # 2026-06-02) both fall before this window's --since, so neither is
        # a boundary event -- it's just fully excluded.
        result = run_extract(self.BOUNDARY_ROOT, since="2026-06-05", until="2026-06-30")
        self.assertEqual(result["meta"]["msgids_boundary_rescued"], 1)
        self.assertEqual(result["meta"]["msgids_boundary_dropped"], 0)

    def test_winner_past_until_dropped_and_counted(self):
        # Opposite edge case, new in Step 4: msg_B2's first occurrence
        # (2026-06-03) is INSIDE this narrower window, but its winner
        # (2026-06-09) falls OUTSIDE --until. Under keep-max this message
        # is dropped from buckets/msgid_contributions entirely -- whereas
        # keep-first would have at least partially counted it, at the stub
        # value. msg_B1 stays fully in-window on both ends here, so it is
        # not a boundary event.
        result = run_extract(self.BOUNDARY_ROOT, since="2026-06-01", until="2026-06-05")
        self.assertNotIn("msg_B2", result["msgid_contributions"])
        self.assertEqual(result["meta"]["msgids_boundary_dropped"], 1)
        self.assertEqual(result["meta"]["msgids_boundary_rescued"], 0)

    def test_day_bucket_follows_winner_across_midnight(self):
        # msg_B1: first occurrence 2026-06-01T23:59:30Z (day 06-01,
        # output=2), winner 2026-06-02T00:00:24Z (day 06-02, output=900),
        # 54 seconds apart. Day bucket follows the WINNER, not the first
        # occurrence.
        result = run_extract(self.BOUNDARY_ROOT)
        rec = result["msgid_contributions"]["msg_B1"]
        self.assertEqual(rec["day"], "2026-06-02")
        self.assertEqual(rec["output"], 900)

    def test_full_history_leaves_boundary_counters_zero(self):
        # A full-history run has no --since/--until, so every occurrence of
        # every message (both B1's and B2's) is always "in window" -- no
        # boundary rescue/drop is possible. msgids_day_straddled, by
        # contrast, is NOT window-gated: msg_B1 (day 06-01 -> 06-02) and
        # msg_B2 (day 06-03 -> 06-09) both change days between their first
        # occurrence and their winner, so it is 2 here, independent of any
        # window.
        result = run_extract(self.BOUNDARY_ROOT)
        self.assertEqual(result["meta"]["msgids_boundary_rescued"], 0)
        self.assertEqual(result["meta"]["msgids_boundary_dropped"], 0)
        self.assertEqual(result["meta"]["msgids_day_straddled"], 2)


# --------------------------------------------------------------------------
# TestCounterAccounting -- generic accounting invariants that hold
# regardless of which fixture(s) they're computed over. These deliberately
# scan the WHOLE FIXTURES_ROOT tree (including proj-keepmax /
# proj-keepmax-reversed, which share message ids and would cross-collapse
# if scanned together, per TestKeepMaxDedup's isolation comment above) --
# that cross-collapse doesn't invalidate a pure arithmetic identity like
# "every eligible line is either a first occurrence or a later duplicate of
# some key," which holds no matter how the keys happen to be shared.
# --------------------------------------------------------------------------


class TestCounterAccounting(unittest.TestCase):
    def test_usage_lines_total_is_predup_denominator(self):
        # usage_lines_total counts every eligible line before dedup; each
        # such line is either the first occurrence of its dedup key
        # (contributing to distinct_msgids_total) or a later duplicate of
        # an already-seen key (contributing to
        # duplicate_lines_skipped_global) -- so the two must sum to it
        # exactly, corpus-wide, regardless of window.
        result = run_extract(FIXTURES_ROOT)
        meta = result["meta"]
        self.assertEqual(
            meta["duplicate_lines_skipped_global"] + meta["distinct_msgids_total"],
            meta["usage_lines_total"],
        )

    def test_cache_shape_counters_sum_to_kept_records(self):
        result = run_extract(os.path.join(FIXTURES_ROOT, "proj-cacheshapes"))
        meta = result["meta"]
        self.assertEqual(
            meta["cache_nested_lines"] + meta["cache_flat_fallback_lines"] + meta["cache_absent_lines"],
            meta["window_msgids_kept"],
        )

    def test_dedup_ratio_nonzero_on_duplicate_fixture(self):
        result = run_extract(os.path.join(FIXTURES_ROOT, "proj-keepmax"))
        meta = result["meta"]
        ratio = meta["window_duplicate_lines"] / meta["window_usage_lines_with_msgid"]
        self.assertGreater(ratio, 0.0)

    def test_bucket_lines_sum_equals_kept_records(self):
        result = run_extract(FIXTURES_ROOT)
        total_lines = sum(b["lines"] for b in result["buckets"])
        self.assertEqual(total_lines, result["meta"]["window_msgids_kept"])


# --------------------------------------------------------------------------
# TestExtractorSelfContainment
# --------------------------------------------------------------------------


class TestExtractorSelfContainment(unittest.TestCase):
    def test_ast_imports_are_stdlib_only(self):
        # This is what stops someone silently breaking every remote host --
        # extractor.py's source is piped verbatim to `python3 -` there, with
        # nothing else on disk.
        stdlib_roots = {"json", "os", "sys", "collections", "datetime"}
        with open(EXTRACTOR_PATH) as f:
            tree = ast.parse(f.read(), filename=EXTRACTOR_PATH)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    self.assertIn(root, stdlib_roots, "non-stdlib import: %s" % alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    self.fail("relative import found in extractor.py: %s" % ast.dump(node))
                root = (node.module or "").split(".")[0]
                self.assertIn(root, stdlib_roots, "non-stdlib import: %s" % node.module)

    def test_extractor_src_equals_file_text(self):
        # Tautological given Step 1's implementation -- kept only because
        # the other three assertions in this class carry the real coverage.
        with open(EXTRACTOR_PATH) as f:
            self.assertEqual(token_cost_report._EXTRACTOR_SRC, f.read())

    def test_piped_subprocess_scans_fixture_tree_not_real_corpus(self):
        # Without TOKEN_COST_ROOT this would scan the real ~/.claude/projects
        # corpus -- a slow, silent no-op of a test on any machine that has
        # one. Proves the shipped `python3 -` self-containment path works
        # end to end against a fixture tree, on a genuinely separate
        # interpreter invocation (not just an in-process import).
        env = dict(os.environ)
        env["TOKEN_COST_ROOT"] = FIXTURES_ROOT
        proc = subprocess.run(
            [sys.executable, "-", "", ""],
            input=token_cost_report._EXTRACTOR_SRC,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, "stderr: %s" % proc.stderr)
        parsed = json.loads(proc.stdout)
        self.assertIn("meta", parsed)
        self.assertIn("buckets", parsed)
        self.assertIn("msgid_contributions", parsed)

    def test_importing_extractor_produces_no_stdout(self):
        proc = subprocess.run(
            [sys.executable, "-c", "import sys; sys.path.insert(0, %r); import extractor" % HERE],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, "stderr: %s" % proc.stderr)
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
