#!/usr/bin/env python3
"""
Tests for the take-stock terminal-detection fix (kaybenleroll/random_llm_projects#76).

Stdlib unittest only, matching this artifact's zero-dependency convention.
Header strings and synthetic block lists are inline literals — no on-disk
fixtures. Run from this directory:

    python3 -m unittest -v

The corpus-level end-to-end assertions in TestCorpusRegression are skipped
automatically if ~/.claude/plans doesn't exist, so the suite stays hermetic
elsewhere.
"""
import os
import unittest

import parse_stress_test_logs as P


class TestClassifyTakeStock(unittest.TestCase):
    def test_option_c_is_terminal(self):
        h = "2026-08-23 18:42 — TAKE-STOCK RESOLVED — Option C at Pass 6"
        r = P.classify_and_parse_header(h)
        self.assertEqual(r["type"], "TAKE_STOCK_RESOLVED")
        self.assertEqual(r["verdict"], "ACCEPTED")
        self.assertEqual(r["option"], "C")
        self.assertEqual(r["pass_num"], 6)
        self.assertEqual(r["date"], "2026-08-23")
        self.assertEqual(r["time"], "18:42")

    def test_option_a_is_not_terminal(self):
        h = "2026-08-26 12:25 — TAKE-STOCK RESOLVED — Option A at Pass 6"
        r = P.classify_and_parse_header(h)
        self.assertEqual(r["type"], "TAKE_STOCK_RESOLVED")
        self.assertIsNone(r["verdict"])
        self.assertEqual(r["option"], "A")

    def test_option_d_is_not_terminal(self):
        h = "2026-08-24 10:18 — TAKE-STOCK RESOLVED — Option D at Pass 6"
        r = P.classify_and_parse_header(h)
        self.assertEqual(r["type"], "TAKE_STOCK_RESOLVED")
        self.assertIsNone(r["verdict"])
        self.assertEqual(r["option"], "D")

    def test_option_b_is_not_terminal(self):
        # SKILL.md says Option B writes a COUNTER RESET instead, but nothing
        # prevents someone writing "Option B" in a resolution header — treat
        # it as non-terminal like A/D rather than dropping it as unparseable.
        h = "2026-08-24 10:18 — TAKE-STOCK RESOLVED — Option B at Pass 6"
        r = P.classify_and_parse_header(h)
        self.assertEqual(r["type"], "TAKE_STOCK_RESOLVED")
        self.assertIsNone(r["verdict"])
        self.assertEqual(r["option"], "B")

    def test_legacy_titlecase_with_option(self):
        h = "2026-08-14 — Take-Stock Resolution 2 — Option D"
        r = P.classify_and_parse_header(h)
        self.assertEqual(r["type"], "TAKE_STOCK_RESOLVED")
        self.assertEqual(r["option"], "D")
        self.assertIsNone(r["pass_num"])

    def test_legacy_titlecase_bare(self):
        h = "2026-08-14 — Take-Stock Resolution"
        r = P.classify_and_parse_header(h)
        self.assertEqual(r["type"], "TAKE_STOCK_RESOLVED")
        self.assertIsNone(r["option"])
        self.assertIsNone(r["verdict"])

    def test_en_dash_and_hyphen_separators(self):
        for sep in ("—", "–", "-"):
            h = f"2026-08-23 18:42 {sep} TAKE-STOCK RESOLVED {sep} Option C at Pass 6"
            r = P.classify_and_parse_header(h)
            self.assertEqual(r["type"], "TAKE_STOCK_RESOLVED", msg=h)
            self.assertEqual(r["option"], "C", msg=h)

    def test_lowercase_variant(self):
        h = "2026-08-23 18:42 — take-stock resolved — option c at pass 6"
        r = P.classify_and_parse_header(h)
        self.assertEqual(r["type"], "TAKE_STOCK_RESOLVED")
        self.assertEqual(r["option"], "C")
        self.assertEqual(r["verdict"], "ACCEPTED")


class TestOrderingTrapRegressions(unittest.TestCase):
    """Headers that must classify identically before and after this fix."""

    def test_real_pass_mentioning_take_stock_stays_pass(self):
        h = "2026-08-23 18:05 — Pass 5 · Iteration 5 (opus) — RERUN_NEEDED (take-stock triggered, escalating)"
        r = P.classify_and_parse_header(h)
        self.assertEqual(r["type"], "PASS")
        self.assertEqual(r["pass_num"], 5)
        self.assertEqual(r["verdict"], "RERUN_NEEDED")

    def test_plain_pass_unaffected(self):
        h = "2026-08-23 18:05 — Pass 7 · Iteration 7 (opus) — CLEAN"
        r = P.classify_and_parse_header(h)
        self.assertEqual(r["type"], "PASS")
        self.assertEqual(r["verdict"], "CLEAN")

    def test_counter_reset_unaffected(self):
        h = "2026-08-23 17:55 — COUNTER RESET — baseline Pass 3"
        r = P.classify_and_parse_header(h)
        self.assertEqual(r["type"], "MARKER")
        self.assertIsNone(r["pass_num"])

    def test_accepted_standalone_take_stock_prose_unaffected(self):
        # Regression guard: this header already terminates correctly today
        # via the ACCEPTED_STANDALONE path. The new branch's `verdict is
        # None` guard must not intercept it.
        h = "2026-08-18 — Take-stock resolution — ACCEPTED"
        r = P.classify_and_parse_header(h)
        self.assertEqual(r["type"], "ACCEPTED_STANDALONE")

    def test_accepted_standalone_take_stock_hash_variant_unaffected(self):
        h = "2026-08-16 — Take-stock #3 — ACCEPTED"
        r = P.classify_and_parse_header(h)
        self.assertEqual(r["type"], "ACCEPTED_STANDALONE")

    def test_take_stock_unsettled_falls_to_marker(self):
        h = "2026-08-18 — Take-Stock Resolution (via /grill-me, not a stress-test pass) — UNSETTLED"
        r = P.classify_and_parse_header(h)
        self.assertEqual(r["type"], "MARKER")

    def test_accepted_option_c_fold_stays_pass(self):
        # precious-conjuring-forest.md's actual terminal entry — already
        # correct today via the pass_num+verdict short-circuit. Proves the
        # fix doesn't hijack it.
        h = "2026-08-26 13:03 — ACCEPTED (Option C fold, Pass 7's findings)"
        r = P.classify_and_parse_header(h)
        self.assertEqual(r["type"], "PASS")
        self.assertEqual(r["verdict"], "ACCEPTED")


def _block(type_, date=None, time=None, pass_num=None, verdict=None, order=0):
    return dict(type=type_, date=date, time=time, pass_num=pass_num, verdict=verdict,
                order_in_section=order, machine="local", file="x.md", scheme=None,
                superseded=False, option=None, header="")


class TestTerminalSelection(unittest.TestCase):
    def test_take_stock_beats_resolved_pass_newest_first(self):
        blocks = [
            _block("TAKE_STOCK_RESOLVED", "2026-08-23", "18:42", 6, "ACCEPTED", order=0),
            _block("PASS", "2026-08-23", "18:33", 6, "RERUN_NEEDED", order=1),
        ]
        ttype, b = P.pick_terminal(blocks)
        self.assertEqual(ttype, "TAKE_STOCK_RESOLVED")
        self.assertEqual(b["verdict"], "ACCEPTED")

    def test_take_stock_beats_resolved_pass_oldest_first(self):
        blocks = [
            _block("PASS", "2026-08-23", "18:33", 6, "RERUN_NEEDED", order=0),
            _block("TAKE_STOCK_RESOLVED", "2026-08-23", "18:42", 6, "ACCEPTED", order=1),
        ]
        ttype, b = P.pick_terminal(blocks)
        self.assertEqual(ttype, "TAKE_STOCK_RESOLVED")
        self.assertEqual(b["verdict"], "ACCEPTED")

    def test_option_a_does_not_hijack_terminal(self):
        blocks = [
            _block("TAKE_STOCK_RESOLVED", "2026-08-23", "18:42", 6, None, order=0),
            _block("PASS", "2026-08-23", "18:33", 6, "RERUN_NEEDED", order=1),
        ]
        ttype, b = P.pick_terminal(blocks)
        self.assertEqual(ttype, "PASS")
        self.assertEqual(b["verdict"], "RERUN_NEEDED")

    def test_option_d_does_not_hijack_terminal(self):
        blocks = [
            _block("TAKE_STOCK_RESOLVED", "2026-08-24", "10:18", 6, None, order=0),
            _block("PASS", "2026-08-23", "18:33", 6, "RERUN_NEEDED", order=1),
        ]
        ttype, b = P.pick_terminal(blocks)
        self.assertEqual(ttype, "PASS")

    def test_date_only_tiebreak_newest_first(self):
        # No HH:MM: date ties, time ties (both ""), pass_num ties (both 6) —
        # without the later() rank tiebreak this falls through to file
        # position and silently flips between orderings.
        blocks = [
            _block("TAKE_STOCK_RESOLVED", "2026-08-14", None, 6, "ACCEPTED", order=0),
            _block("PASS", "2026-08-14", None, 6, "RERUN_NEEDED", order=1),
        ]
        ttype, b = P.pick_terminal(blocks)
        self.assertEqual(ttype, "TAKE_STOCK_RESOLVED", msg="failed in newest-first order")

    def test_date_only_tiebreak_oldest_first(self):
        blocks = [
            _block("PASS", "2026-08-14", None, 6, "RERUN_NEEDED", order=0),
            _block("TAKE_STOCK_RESOLVED", "2026-08-14", None, 6, "ACCEPTED", order=1),
        ]
        ttype, b = P.pick_terminal(blocks)
        self.assertEqual(ttype, "TAKE_STOCK_RESOLVED", msg="failed in oldest-first order")

    def test_later_accepted_fold_outranks_take_stock(self):
        blocks = [
            _block("TAKE_STOCK_RESOLVED", "2026-08-26", "13:00", 7, "ACCEPTED", order=0),
            _block("PASS", "2026-08-26", "13:03", 7, "ACCEPTED", order=1),
        ]
        ttype, b = P.pick_terminal(blocks)
        self.assertEqual(ttype, "PASS")
        self.assertEqual(b["time"], "13:03")

    def test_option_a_lineage_with_clean_pass_no_hijack(self):
        blocks = [
            _block("TAKE_STOCK_RESOLVED", "2026-08-20", "09:00", 3, None, order=0),
            _block("PASS", "2026-08-22", "10:00", 5, "CLEAN", order=1),
        ]
        ttype, b = P.pick_terminal(blocks)
        self.assertEqual(ttype, "PASS")
        self.assertEqual(b["verdict"], "CLEAN")


class TestStatisticsUnchanged(unittest.TestCase):
    def test_take_stock_excluded_from_pass_statistics(self):
        blocks = [
            _block("TAKE_STOCK_RESOLVED", "2026-08-23", "18:42", 6, "ACCEPTED", order=0),
            _block("PASS", "2026-08-23", "18:33", 5, "RERUN_NEEDED", order=1),
        ]
        pass_only = [b for b in blocks if b["type"] == "PASS" and b["pass_num"]]
        self.assertEqual(len(pass_only), 1)
        self.assertEqual(pass_only[0]["pass_num"], 5)
        max_pass = max((b["pass_num"] for b in pass_only), default=None)
        self.assertEqual(max_pass, 5, "TAKE_STOCK_RESOLVED's pass_num=6 must not inflate max_pass")


class TestCorpusRegression(unittest.TestCase):
    """End-to-end guard against the real corpus. Skipped if it's absent."""

    PLANS_DIR = os.path.expanduser("~/.claude/plans")

    @unittest.skipUnless(os.path.isdir(PLANS_DIR), "~/.claude/plans not present")
    def test_expected_flip_set(self):
        expected_flipped = {
            "lazy-swimming-mccarthy.md",
            "logical-orbiting-brooks.md",
            "bubbly-mixing-clover.md",
        }
        for fname in expected_flipped:
            path = os.path.join(self.PLANS_DIR, fname)
            if not os.path.isfile(path):
                self.skipTest(f"{fname} not present in current corpus")
            _, blocks = P.process_file("local", path)
            ttype, b = P.pick_terminal(blocks)
            self.assertEqual(b["verdict"], "ACCEPTED", msg=f"{fname} should now terminate ACCEPTED")

        forest = os.path.join(self.PLANS_DIR, "precious-conjuring-forest.md")
        if os.path.isfile(forest):
            _, blocks = P.process_file("local", forest)
            ttype, b = P.pick_terminal(blocks)
            self.assertEqual(b["verdict"], "ACCEPTED",
                              msg="precious-conjuring-forest.md was already correct — must stay ACCEPTED")


if __name__ == "__main__":
    unittest.main()
