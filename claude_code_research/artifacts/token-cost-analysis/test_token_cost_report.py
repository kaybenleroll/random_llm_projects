#!/usr/bin/env python3
"""Unit tests for token_cost_report.py / extractor.py (issue #101).

Step 2/3 of the plan at `.claude/plans/greedy-roaming-horizon.md`: a
red-before-green safety net scoped to what's actually assertable against
*current* (pre-Step-4, keep-first) behaviour. TestKeepMaxDedup,
TestNoMessageId, TestUsageFieldPreservation and TestExtractorSelfContainment
below all assert CURRENT extractor.scan() behaviour -- most of these
assertions are durable (order-independence-of-totals, whole-record
selection, cache-shape handling) and will keep passing after Step 4's
keep-max restructure lands. Exactly one -- TestKeepMaxDedup's
stub-then-settled test -- is deliberately flipped to the FUTURE expected
value in a follow-up commit (Step 3), and is EXPECTED TO FAIL until Step 4
ships the actual keep-max policy.

TestWindowAttribution and TestCounterAccounting's distinct_msgids_total
assertion are intentionally left as empty stub classes: they need counters
(msgids_boundary_rescued/_dropped/_day_straddled, distinct_msgids_total)
that do not exist before Step 4. Writing full assertions against them now
would produce KeyError failures, not clean assertion failures, defeating
the point of this red-before-green commit. TestRealCorpusInvariants (which
needs tools/measure_dup_msgids.py as a library, per the plan's Tests
section) is out of scope for Step 2/3 entirely and not present here.
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
        # Today's keep-first policy keeps the FIRST occurrence -- the stub,
        # 3 -- which is the #101 bug itself. This is the one test Step 3
        # flips to the future keep-max value (1200); until Step 4 ships,
        # that flipped assertion is EXPECTED TO FAIL.
        result = run_extract(self.KEEPMAX_ROOT)
        rec = result["msgid_contributions"]["msg_K1"]
        self.assertEqual(rec["output"], 3)

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

    def test_tie_on_output_pins_current_first_seen(self):
        # proj-tiebreak: msg_T1 occurs twice with EQUAL output (700) but
        # different days (2026-06-03, 2026-06-20). Today's keep-first
        # policy keeps whichever occurrence is first in file order -- the
        # 2026-06-03 occurrence -- regardless of the output tie. (Step 4's
        # keep-max policy breaks ties the other way, "last seen wins" --
        # that is a Step 4 concern, not asserted here.)
        result = run_extract(FIXTURES_ROOT, project="proj-tiebreak")
        b = sole_bucket(result["buckets"])
        self.assertEqual(b["day"], "2026-06-03")
        self.assertEqual(b["output"], 700)
        rec = result["msgid_contributions"]["msg_T1"]
        self.assertEqual(rec["day"], "2026-06-03")

    def test_whole_record_selected_not_per_field(self):
        # proj-fieldmix: msg_F1 occ1 has input=9999/output=2, occ2 has
        # input=10/output=800. Today's keep-first keeps occ1's WHOLE
        # record -- input=9999 AND output=2 together, never a per-field mix
        # (e.g. input=10 paired with output=2 would mean the code picked
        # fields from different occurrences, which it never does).
        result = run_extract(FIXTURES_ROOT, project="proj-fieldmix")
        rec = result["msgid_contributions"]["msg_F1"]
        self.assertEqual(rec["input"], 9999)
        self.assertEqual(rec["output"], 2)

    def test_cross_file_duplicate_collapsed(self):
        # proj-crossfile: msg_X1 appears once in file_a.jsonl and once in
        # file_b.jsonl (same project, two different files) -- dedup is
        # keyed globally by message.id, not per-file, so this must collapse
        # to one contribution. all_files is path-sorted, so file_a.jsonl
        # (alphabetically first) is scanned first and its occurrence
        # (output=10) wins under keep-first; file_b's (output=999) is the
        # duplicate.
        root = os.path.join(FIXTURES_ROOT, "proj-crossfile")
        result = run_extract(root)
        rec = result["msgid_contributions"]["msg_X1"]
        self.assertEqual(rec["output"], 10)
        b = sole_bucket(result["buckets"])
        self.assertEqual(b["lines"], 1)
        self.assertEqual(result["meta"]["duplicate_lines_skipped_global"], 1)


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
        # C1 (nested), C2 (nested), C5 (nested -- occ1 is first-seen under
        # today's keep-first policy, so the kept record is nested, not the
        # occ2 flat "loser") = 3 nested lines; C3 (flat fallback) = 1;
        # C4 (absent) = 1.
        meta = self.cache_result["meta"]
        self.assertEqual(meta["cache_nested_lines"], 3)
        self.assertEqual(meta["cache_flat_fallback_lines"], 1)
        self.assertEqual(meta["cache_absent_lines"], 1)
        rec = self._rec(self.cache_result, "msg_C5")
        self.assertEqual(rec["cache_write_5m"], 5)
        self.assertEqual(rec["cache_write_1h"], 15)

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
# TestWindowAttribution -- stub. Needs msgids_boundary_rescued/_dropped/
# _day_straddled, which do not exist before Step 4. Left empty deliberately
# per the plan's Step 2 scope (writing assertions here now would KeyError,
# not fail cleanly).
# --------------------------------------------------------------------------


class TestWindowAttribution(unittest.TestCase):
    pass


# --------------------------------------------------------------------------
# TestCounterAccounting -- stub. Its distinct_msgids_total assertion needs
# a counter that does not exist before Step 4; left empty for the same
# reason as TestWindowAttribution above.
# --------------------------------------------------------------------------


class TestCounterAccounting(unittest.TestCase):
    pass


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
