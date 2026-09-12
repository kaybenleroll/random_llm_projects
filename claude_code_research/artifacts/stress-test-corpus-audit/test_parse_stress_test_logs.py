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
import io
import contextlib
import os
import unittest

import parse_stress_test_logs as P

# Per this repo's convention, all temp/output files for tests go under the
# subproject's .scratch/, never /tmp.
SCRATCH_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".scratch",
)


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


class TestArrowSynonymVerdicts(unittest.TestCase):
    """Free-text arrow-suffix resolution synonyms resolve to CLEAN
    (kaybenleroll/random_llm_projects#79)."""

    def test_landed_resolves_to_clean(self):
        self.assertEqual(P.extract_verdict("RERUN_NEEDED -> LANDED"), "CLEAN")

    def test_addressed_resolves_to_clean(self):
        self.assertEqual(P.extract_verdict("RERUN_NEEDED -> addressed"), "CLEAN")

    def test_resolved_resolves_to_clean(self):
        self.assertEqual(P.extract_verdict("RERUN_NEEDED -> resolved"), "CLEAN")

    def test_folded_resolves_to_clean(self):
        self.assertEqual(
            P.extract_verdict("RERUN_NEEDED -> all findings folded here"), "CLEAN"
        )

    def test_unrelated_free_text_falls_back_to_pre_arrow_token(self):
        # Out of scope per issue #79: an unrelated free-text word after the
        # arrow must NOT be guessed as a synonym — falls back to the
        # pre-arrow canonical token instead.
        self.assertEqual(
            P.extract_verdict("RERUN_NEEDED -> revised, this version"), "RERUN_NEEDED"
        )

    def test_canonical_token_after_arrow_still_wins_over_synonym_wording(self):
        # A canonical token after the arrow takes priority even if synonym
        # wording is also present.
        self.assertEqual(
            P.extract_verdict("RERUN_NEEDED -> addressed, now CLEAN"), "CLEAN"
        )


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

    def test_unparseable_time_falls_through_to_order_tiebreak(self):
        # kaybenleroll/random_llm_projects#105: twinkly-hugging-storm.md has a
        # placeholder timestamp ("21:5x", unparseable -> time=None) on the
        # chronologically-first (order 0, newest-first) ACCEPTED block, same
        # date as a later-ordered RERUN_NEEDED pass with a real HH:MM. An
        # unparseable time must not be treated as the lexicographic minimum
        # (which would make the real-timed block win outright) — it must
        # fall through date-tie handling to the pass_num/order tiebreak.
        blocks = [
            _block("ACCEPTED_STANDALONE", "2026-08-26", None, None, "ACCEPTED", order=0),
            _block("PASS", "2026-08-26", "21:22", 7, "RERUN_NEEDED", order=1),
        ]
        ttype, b = P.pick_terminal(blocks)
        self.assertEqual(ttype, "ACCEPTED_STANDALONE")
        self.assertEqual(b["verdict"], "ACCEPTED")


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


class TestExtractSectionDuplicateHeading(unittest.TestCase):
    """kaybenleroll/random_llm_projects#80: a second '## Stress-Test Log'
    heading must not silently drop the second section's content."""

    def test_single_heading_unchanged(self):
        text = "intro\n\n## Stress-Test Log\n\n### 2026-01-01 10:00 — Pass 1 — CLEAN\nfirst body\n"
        section, n = P.extract_section(text)
        self.assertEqual(n, 1)
        self.assertIn("first body", section)

    def test_no_heading(self):
        section, n = P.extract_section("no log section here at all")
        self.assertIsNone(section)
        self.assertEqual(n, 0)

    def test_duplicate_heading_combines_both_sections(self):
        text = (
            "## Stress-Test Log\n\n"
            "### 2026-01-01 10:00 — Pass 1 — CLEAN\nfirst section body\n\n"
            "## Unrelated Section\nirrelevant content\n\n"
            "## Stress-Test Log\n\n"
            "### 2026-02-01 10:00 — Pass 2 — RESTRUCTURE\nsecond section body\n"
        )
        section, n = P.extract_section(text)
        self.assertEqual(n, 2)
        self.assertIn("first section body", section, "first section's content must not be dropped")
        self.assertIn("second section body", section, "second section's content must not be dropped")

    def test_process_file_warns_and_parses_both_sections(self):
        text = (
            "## Stress-Test Log\n\n"
            "### 2026-01-01 10:00 — Pass 1 — CLEAN\nfirst body\n\n"
            "## Stress-Test Log\n\n"
            "### 2026-02-01 10:00 — Pass 2 — RESTRUCTURE\nsecond body\n"
        )
        os.makedirs(SCRATCH_DIR, exist_ok=True)
        path = os.path.join(SCRATCH_DIR, "test_issue80_duplicate_heading.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        try:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                section, blocks = P.process_file("local", path)
            self.assertIsNotNone(section)
            self.assertIn("2 '## Stress-Test Log' headings", stderr.getvalue(),
                          "duplicate heading must produce a warning, not silence")
            self.assertIn(path, stderr.getvalue(), "warning must identify the offending file")

            pass_nums_verdicts = {(b["pass_num"], b["verdict"]) for b in blocks if b["type"] == "PASS"}
            self.assertIn((1, "CLEAN"), pass_nums_verdicts, "first section's pass must survive")
            self.assertIn((2, "RESTRUCTURE"), pass_nums_verdicts, "second section's pass must not be dropped")
        finally:
            os.remove(path)

    def test_single_heading_process_file_no_warning(self):
        text = "## Stress-Test Log\n\n### 2026-01-01 10:00 — Pass 1 — CLEAN\nbody\n"
        os.makedirs(SCRATCH_DIR, exist_ok=True)
        path = os.path.join(SCRATCH_DIR, "test_issue80_single_heading.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        try:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                section, blocks = P.process_file("local", path)
            self.assertEqual(stderr.getvalue(), "", "a single heading must never warn")
            self.assertEqual(len(blocks), 1)
        finally:
            os.remove(path)


class TestRoundDetection(unittest.TestCase):
    """kaybenleroll/random_llm_projects#96: a round of 3 parallel reviewers
    is logged as one '### Pass N' entry whose body embeds one
    '- Reviewer <k>: ...' bullet per reviewer (SKILL.md canonical shape).
    Detection is structural (reviewer-line count), never date-based."""

    ROUND_BODY = """
Action: proceed to implementation — both P1 findings were patched in place
and verified this round.

Round of 3 — ~19 findings after dedup: 0 Showstoppers, 2 P1, ~9 Gaps.

- Reviewer 1: ACCEPTED — 11 findings; lead finding: no test discriminates
  the two allocation bases
- Reviewer 2: ACCEPTED — 9 findings; independently found the same P1
- Reviewer 3: ACCEPTED — 10 findings; same P1 a third time
- Gate: 2 distinct P1s after cross-reviewer dedup, neither non-patchable,
  both patched and reverified

Self-review: n/a — no fixes applied this round
Resolution: n/a
"""

    OLD_BODY = """
10 findings: 1 showstopper, 6 gaps, 1 inconsistency, 2 underspecified, 0
suggestions.

- **[S]** oracle's instrument cannot observe 2+ of M13's 8 claims. Not folded.
- **[G]** corpus driver is deterministic-only; stochastic path never invoked.
"""

    def test_round_body_detected_with_size_3(self):
        is_round, round_size = P.detect_round(self.ROUND_BODY)
        self.assertTrue(is_round)
        self.assertEqual(round_size, 3)

    def test_old_format_body_not_round(self):
        is_round, round_size = P.detect_round(self.OLD_BODY)
        self.assertFalse(is_round)
        self.assertEqual(round_size, 1)

    def test_two_reviewer_round_counted_honestly_not_truncated_to_three(self):
        # Real corpus is always 0 or 3, but detection counts the lines
        # actually present rather than assuming 3 — a differently sized
        # round must not be silently truncated.
        body = ("- Reviewer 1: ACCEPTED — no findings\n"
                "- Reviewer 2: ACCEPTED — no findings\n")
        is_round, round_size = P.detect_round(body)
        self.assertTrue(is_round)
        self.assertEqual(round_size, 2)

    def test_round_body_bullets_exclude_reviewer_and_gate_lines(self):
        # Reviewer/Gate summary bullets are not a per-finding list — they
        # must not feed n_bullets/restatement/new-flagged counts.
        n_findings, n_before_cap, n_bullets, n_restatement, n_new_flagged, \
            is_round, round_size = P.classify_findings_and_restatement(self.ROUND_BODY)
        self.assertTrue(is_round)
        self.assertEqual(round_size, 3)
        self.assertEqual(n_bullets, 0)
        self.assertEqual(n_restatement, 0)
        self.assertEqual(n_new_flagged, 0)
        self.assertEqual(n_findings, 19)

    def test_old_format_bullets_unaffected(self):
        n_findings, n_before_cap, n_bullets, n_restatement, n_new_flagged, \
            is_round, round_size = P.classify_findings_and_restatement(self.OLD_BODY)
        self.assertFalse(is_round)
        self.assertEqual(round_size, 1)
        self.assertEqual(n_bullets, 2)

    def test_findings_re_not_fooled_by_severity_token_before_real_count(self):
        # Folded into #96: a round-format Action field routinely says "both
        # P1 findings were patched" before the real "~19 findings after
        # dedup" line; FINDINGS_RE's leftmost match must not read "1" off
        # of "P1". Confirmed against real corpus data (29/63 round blocks
        # affected pre-fix).
        m = P.FINDINGS_RE.search(self.ROUND_BODY)
        self.assertIsNotNone(m)
        self.assertEqual(int(m.group(1)), 19)

    def test_process_file_marks_round_block(self):
        text = (
            "# Plan — Fixture\n\n"
            "## Stress-Test Log\n\n"
            "### 2026-09-01 10:00 — Pass 1 · Iteration 1 (opus) — ACCEPTED\n"
            + self.ROUND_BODY
        )
        os.makedirs(SCRATCH_DIR, exist_ok=True)
        path = os.path.join(SCRATCH_DIR, "test_issue96_round_fixture.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        try:
            _, blocks = P.process_file("local", path)
            self.assertEqual(len(blocks), 1)
            b = blocks[0]
            self.assertEqual(b["type"], "PASS")
            self.assertEqual(b["pass_num"], 1)
            self.assertTrue(b["is_round"])
            self.assertEqual(b["round_size"], 3)
        finally:
            os.remove(path)


class TestLineageStatsRoundWeighting(unittest.TestCase):
    """kaybenleroll/random_llm_projects#96: a round of 3 counts as 3 passes
    toward n_pass_blocks/total_pass_estimate; max_pass_num stays unweighted
    (it measures rounds-to-converge, not reviewer-per-round volume)."""

    def _round_block(self, pass_num, order):
        b = _block("PASS", "2026-09-01", "10:00", pass_num, "ACCEPTED", order=order)
        b["is_round"] = True
        b["round_size"] = 3
        return b

    def _old_block(self, pass_num, order):
        b = _block("PASS", "2026-08-01", "10:00", pass_num, "ACCEPTED", order=order)
        b["is_round"] = False
        b["round_size"] = 1
        return b

    def test_single_round_entry_counts_as_three_passes(self):
        blocks = [self._round_block(1, 0)]
        stats = P.compute_lineage_stats(blocks)
        self.assertEqual(stats["max_pass_num"], 1)
        self.assertEqual(stats["n_pass_blocks"], 3)
        self.assertEqual(stats["total_pass_estimate"], 3)
        self.assertEqual(stats["n_round_entries"], 1)

    def test_two_round_entries_count_as_six_passes(self):
        blocks = [self._round_block(1, 0), self._round_block(2, 1)]
        stats = P.compute_lineage_stats(blocks)
        self.assertEqual(stats["max_pass_num"], 2, "iteration index stays unweighted")
        self.assertEqual(stats["n_pass_blocks"], 6)
        self.assertEqual(stats["total_pass_estimate"], 6)
        self.assertEqual(stats["n_round_entries"], 2)

    def test_old_format_lineage_unchanged_by_the_fix(self):
        blocks = [self._old_block(1, 0), self._old_block(2, 1), self._old_block(3, 2)]
        stats = P.compute_lineage_stats(blocks)
        self.assertEqual(stats["max_pass_num"], 3)
        self.assertEqual(stats["n_pass_blocks"], 3)
        self.assertEqual(stats["total_pass_estimate"], 3)
        self.assertEqual(stats["n_round_entries"], 0)

    def test_mixed_lineage_old_then_round(self):
        # A lineage that started before the redesign and continued after it.
        blocks = [self._old_block(1, 0), self._old_block(2, 1), self._round_block(3, 2)]
        stats = P.compute_lineage_stats(blocks)
        self.assertEqual(stats["max_pass_num"], 3)
        self.assertEqual(stats["n_pass_blocks"], 5)  # 1 + 1 + 3
        self.assertEqual(stats["total_pass_estimate"], 5)
        self.assertEqual(stats["n_round_entries"], 1)

    def test_legacy_range_compression_not_regressed_by_round_weighting(self):
        # async-drifting-lollipop.md's real shape: a legacy 'Passes 1-3 —
        # summary only' RANGE marker (pre-redesign compressed history, no
        # individual blocks for 1-3) plus individually-logged Pass 4 and
        # Pass 5 old-format blocks. True total is 5 — a pure weighted-sum-
        # of-present-blocks approach would wrongly report 2 (only blocks 4
        # and 5 exist as blocks at all).
        blocks = [
            self._old_block(5, 0),
            self._old_block(4, 1),
            dict(type="RANGE", date="2026-08-05", time=None, pass_num=None,
                 range_end=3, verdict=None, order_in_section=2,
                 machine="local", file="x.md", header=""),
        ]
        stats = P.compute_lineage_stats(blocks)
        self.assertEqual(stats["max_pass_num"], 5)
        self.assertEqual(stats["n_pass_blocks"], 5, "RANGE floor must win over the weighted-sum-of-present-blocks (2)")
        self.assertEqual(stats["total_pass_estimate"], 5)

    def test_missing_is_round_round_size_keys_default_safely(self):
        # Hand-built dicts (e.g. check_placeholder_bullet.py) don't carry
        # is_round/round_size — must default to old (unweighted) behaviour.
        blocks = [_block("PASS", "2026-08-01", "10:00", 1, "ACCEPTED", order=0)]
        stats = P.compute_lineage_stats(blocks)
        self.assertEqual(stats["n_pass_blocks"], 1)
        self.assertEqual(stats["total_pass_estimate"], 1)
        self.assertEqual(stats["n_round_entries"], 0)


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

    @unittest.skipUnless(os.path.isdir(PLANS_DIR), "~/.claude/plans not present")
    def test_known_duplicate_heading_file_warns_without_crashing(self):
        """kaybenleroll/random_llm_projects#80: memoized-sniffing-wave.md has
        two '## Stress-Test Log' headings on this machine."""
        path = os.path.join(self.PLANS_DIR, "memoized-sniffing-wave.md")
        if not os.path.isfile(path):
            self.skipTest("memoized-sniffing-wave.md not present in current corpus")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            section, blocks = P.process_file("local", path)
        self.assertIsNotNone(section)
        self.assertIn("2 '## Stress-Test Log' headings", stderr.getvalue())
        self.assertIn(path, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
