#!/usr/bin/env python3
"""Unit tests for session_analysis.py (issue #71).

Covers steps 1-8 of the implementation plan: discovery/identify_file, the 10
known-answer fixtures (tests/fixtures/projects/), the pure classification/
usage/threshold functions in isolation, SessionAccumulator/scan_file,
sessions.csv + session_model_tokens.csv row-level invariants, and CLI-wired
filters/thresholds. Real-corpus invariant tests (step 10) are NOT included
here -- this phase stops after the manual step-8 corpus run.
"""
import json
import os
import statistics
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import session_analysis  # noqa: E402
from session_analysis import (  # noqa: E402
    apply_thresholds,
    build_model_rows,
    classify_session,
    extract_usage,
    identify_file,
    is_meta_line,
    is_tool_result_line,
    iter_transcript_files,
    new_guardrails,
    pick_primary_model,
    process_file,
    window_bounds,
)

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES_ROOT = os.path.join(HERE, "tests", "fixtures", "projects")
REAL_ROOT = os.path.expanduser("~/.claude/projects")

try:
    import pyarrow as _pyarrow_probe  # noqa: F401
    HAVE_PYARROW = True
except ImportError:
    HAVE_PYARROW = False


def run_scan(root, project=None, since=None, until=None, max_turns=175, max_cache_creation=1525000):
    """Mirrors session_analysis.main()'s core loop without argparse or file
    output -- the single code path every filter/threshold test exercises, so
    a test failure here means the same wiring main() uses is actually wrong,
    not a divergent test-only reimplementation."""
    since_dt, until_dt = window_bounds(since, until)
    guardrails = new_guardrails()
    global_seen_msgids = set()
    rows = []
    model_rows = []
    for path in iter_transcript_files(root):
        guardrails["files_seen"] += 1
        result, _info = process_file(
            path, root, guardrails, project_substr=project, since_dt=since_dt, until_dt=until_dt
        )
        if result is None:
            continue
        row, per_model = result
        for mid in row.get("_message_ids") or []:
            if mid in global_seen_msgids:
                guardrails["cross_file_duplicate_ids"] += 1
            else:
                global_seen_msgids.add(mid)
        flagged, reasons = apply_thresholds(row["api_turns"], row["cache_creation_total"], max_turns, max_cache_creation)
        row["flagged"] = flagged
        row["flag_reasons"] = ";".join(sorted(reasons))
        rows.append(row)
        model_rows.extend(build_model_rows(row["session_id"], row["project"], row["classification"], per_model))
    return rows, guardrails, model_rows


def row_by_id(rows, session_id):
    for r in rows:
        if r["session_id"] == session_id:
            return r
    raise AssertionError("no row with session_id=%r among %r" % (session_id, [r["session_id"] for r in rows]))


# --------------------------------------------------------------------------
# Step 1: discovery / identify_file
# --------------------------------------------------------------------------


class TestDiscovery(unittest.TestCase):
    def test_fixture_file_count(self):
        # 10 fixture files on disk (A-J); iter_transcript_files walks all of
        # them (exclusion happens later, in identify_file).
        self.assertEqual(len(iter_transcript_files(FIXTURES_ROOT)), 10)

    def test_identify_file_top_level(self):
        path = os.path.join(FIXTURES_ROOT, "proj-alpha", "11111111-1111-1111-1111-111111111111.jsonl")
        info = identify_file(path, FIXTURES_ROOT)
        self.assertFalse(info["excluded"])
        self.assertEqual(info["kind"], "top_level")
        self.assertEqual(info["session_id"], "11111111-1111-1111-1111-111111111111")
        self.assertIsNone(info["parent_session_id"])
        self.assertEqual(info["project"], "proj-alpha")
        self.assertFalse(info["subagent_path_unmatched"])

    def test_identify_file_flat_subagent(self):
        path = os.path.join(
            FIXTURES_ROOT, "proj-alpha", "11111111-1111-1111-1111-111111111111",
            "subagents", "agent-abc0000000000001.jsonl",
        )
        info = identify_file(path, FIXTURES_ROOT)
        self.assertFalse(info["excluded"])
        self.assertEqual(info["kind"], "subagent")
        self.assertEqual(info["session_id"], "agent-abc0000000000001")
        self.assertEqual(info["parent_session_id"], "11111111-1111-1111-1111-111111111111")

    def test_identify_file_nested_workflow_subagent(self):
        # The P1 finding: workflow-nested subagent paths must resolve the
        # SAME parent-UUID rule as the flat depth, at any nesting depth.
        path = os.path.join(
            FIXTURES_ROOT, "proj-alpha", "33333333-3333-3333-3333-333333333333",
            "subagents", "workflows", "wf_x", "agent-def0000000000001.jsonl",
        )
        info = identify_file(path, FIXTURES_ROOT)
        self.assertFalse(info["excluded"])
        self.assertEqual(info["kind"], "subagent")
        self.assertEqual(info["session_id"], "agent-def0000000000001")
        self.assertEqual(info["parent_session_id"], "33333333-3333-3333-3333-333333333333")

    def test_identify_file_denylist_excluded(self):
        path = os.path.join(
            FIXTURES_ROOT, "proj-alpha", "11111111-1111-1111-1111-111111111111",
            "subagents", "workflows", "wf_y", "journal.jsonl",
        )
        info = identify_file(path, FIXTURES_ROOT)
        self.assertTrue(info["excluded"])
        self.assertIsNone(info["kind"])

    def test_identify_file_subagent_path_unmatched(self):
        # "Older layout": an agent-<hex>.jsonl basename with no subagents/
        # segment anywhere in the path -- must NOT be misclassified as a
        # normal top-level session; must set the unmatched flag.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "proj-x", "agent-deadbeef000.jsonl")
            os.makedirs(os.path.dirname(path))
            open(path, "w").close()
            info = identify_file(path, tmp)
            self.assertFalse(info["excluded"])
            self.assertEqual(info["kind"], "top_level")
            self.assertIsNone(info["parent_session_id"])
            self.assertTrue(info["subagent_path_unmatched"])

    @unittest.skipUnless(os.path.isdir(REAL_ROOT), "requires ~/.claude/projects")
    def test_real_corpus_file_count(self):
        n = len(iter_transcript_files(REAL_ROOT))
        # Full tree including subagent transcripts at both depths: ~17,500,
        # not the top-level-only ~10,754-10,779. Seeing a count near the
        # latter means subagent discovery is under-matching.
        self.assertGreater(n, 15000, "file count %d suggests top-level-only discovery (subagent walk broken)" % n)
        self.assertLess(n, 30000, "file count %d is implausibly large for this corpus" % n)


# --------------------------------------------------------------------------
# Fixture-A arithmetic spot-check (self-contained, does not import the
# scanner) -- required before freezing these numbers as test constants.
# --------------------------------------------------------------------------


class TestFixtureAArithmeticSpotCheck(unittest.TestCase):
    def test_hand_computed_totals(self):
        msg_A1 = {"input": 100, "cache_read": 0, "output": 50, "c5m": 20, "c1h": 30, "model": "claude-sonnet-5"}
        msg_A2 = {"input": 40, "cache_read": 200, "output": 25, "c5m": 0, "c1h": 15, "model": "claude-haiku-4-5"}
        msg_A3 = {"input": 10, "cache_read": 0, "output": 5, "c5m": 0, "c1h": 0, "model": "claude-sonnet-5"}
        # msg_A1 appears twice in the fixture file (byte-identical repeat) --
        # deduped to a single contribution here, matching the tool's dedup.
        msgs = [msg_A1, msg_A2, msg_A3]

        self.assertEqual(sum(m["input"] for m in msgs), 150)
        self.assertEqual(sum(m["cache_read"] for m in msgs), 200)
        self.assertEqual(sum(m["output"] for m in msgs), 80)
        self.assertEqual(sum(m["c5m"] for m in msgs), 20)
        self.assertEqual(sum(m["c1h"] for m in msgs), 45)
        self.assertEqual(sum(m["c5m"] for m in msgs) + sum(m["c1h"] for m in msgs), 65)

        per_model = {}
        for m in msgs:
            pm = per_model.setdefault(m["model"], {"input": 0, "cache_read": 0, "output": 0, "c5m": 0, "c1h": 0})
            for k in ("input", "cache_read", "output", "c5m", "c1h"):
                pm[k] += m[k]

        def volume(pm):
            return pm["input"] + pm["c5m"] + pm["c1h"] + pm["cache_read"] + pm["output"]

        self.assertEqual(volume(per_model["claude-sonnet-5"]), 215)
        self.assertEqual(volume(per_model["claude-haiku-4-5"]), 280)
        primary = max(per_model.items(), key=lambda kv: volume(kv[1]))[0]
        self.assertEqual(primary, "claude-haiku-4-5")


# --------------------------------------------------------------------------
# Step 3: pure functions
# --------------------------------------------------------------------------


class TestClassifySessionMatrix(unittest.TestCase):
    def test_branch1_subagent_path_unconditional(self):
        # Even with a promptSource present, subagent-by-path wins outright.
        lines = [{"type": "user", "promptSource": "typed", "entrypoint": "cli"}]
        self.assertEqual(classify_session(True, lines), ("subagent", "path"))
        self.assertEqual(classify_session(True, []), ("subagent", "path"))

    def test_branch2_no_user_lines(self):
        self.assertEqual(classify_session(False, []), ("unclassified", "no_user_lines"))

    def test_branch3_prompt_source_real_work(self):
        for ps in ("typed", "queued"):
            lines = [{"promptSource": ps, "entrypoint": "cli"}]
            self.assertEqual(classify_session(False, lines), ("real_work", "prompt_source"))

    def test_branch3_prompt_source_automated(self):
        for ps in ("sdk", "system"):
            lines = [{"promptSource": ps, "entrypoint": "sdk-cli"}]
            self.assertEqual(classify_session(False, lines), ("automated", "prompt_source"))

    def test_branch4_unknown_prompt_source_does_not_fall_through(self):
        lines = [{"promptSource": "suggestion_accepted", "entrypoint": "cli"}]
        self.assertEqual(classify_session(False, lines), ("unclassified", "unknown_prompt_source"))

    def test_branch5_entrypoint_fallback_real_work(self):
        lines = [{"entrypoint": "cli"}]  # no promptSource key at all
        self.assertEqual(classify_session(False, lines), ("real_work", "entrypoint_fallback"))

    def test_branch5_entrypoint_fallback_automated(self):
        lines = [{"entrypoint": "sdk-cli"}]
        self.assertEqual(classify_session(False, lines), ("automated", "entrypoint_fallback"))

    def test_branch6_no_signal(self):
        lines = [{"entrypoint": "something-else"}]
        self.assertEqual(classify_session(False, lines), ("unclassified", "no_signal"))
        lines = [{}]
        self.assertEqual(classify_session(False, lines), ("unclassified", "no_signal"))

    def test_sidechain_all_excluded_case_resolves_to_no_user_lines(self):
        # Same shape as fixtures G/I: caller (SessionAccumulator) would have
        # already filtered these out for a top-level file, so the candidate
        # list classify_session receives is empty. Confirm this resolves to
        # no_user_lines, NOT a fall-through to the entrypoint fallback.
        candidate_lines_after_top_level_filtering = []
        self.assertEqual(
            classify_session(False, candidate_lines_after_top_level_filtering),
            ("unclassified", "no_user_lines"),
        )


class TestExtractUsageMatrix(unittest.TestCase):
    def _assistant(self, usage, model="claude-sonnet-5", msg_id="m1"):
        return {"type": "assistant", "message": {"id": msg_id, "model": model, "usage": usage}}

    def test_non_assistant_line_returns_none(self):
        self.assertIsNone(extract_usage({"type": "user"}))

    def test_missing_usage_block_returns_none(self):
        self.assertIsNone(extract_usage({"type": "assistant", "message": {"id": "m1"}}))

    def test_nested_cache_only(self):
        u = extract_usage(self._assistant({
            "input_tokens": 10, "cache_read_input_tokens": 5, "output_tokens": 3,
            "cache_creation": {"ephemeral_5m_input_tokens": 7, "ephemeral_1h_input_tokens": 9},
        }))
        self.assertEqual(u["cache_creation_5m"], 7)
        self.assertEqual(u["cache_creation_1h"], 9)

    def test_flat_fallback_only(self):
        u = extract_usage(self._assistant({
            "input_tokens": 10, "cache_read_input_tokens": 5, "output_tokens": 3,
            "cache_creation_input_tokens": 42,
        }))
        self.assertEqual(u["cache_creation_5m"], 0)
        self.assertEqual(u["cache_creation_1h"], 42)

    def test_both_present_nested_wins(self):
        u = extract_usage(self._assistant({
            "input_tokens": 10, "output_tokens": 3,
            "cache_creation_input_tokens": 999,  # must be ignored
            "cache_creation": {"ephemeral_5m_input_tokens": 1, "ephemeral_1h_input_tokens": 2},
        }))
        self.assertEqual(u["cache_creation_5m"], 1)
        self.assertEqual(u["cache_creation_1h"], 2)

    def test_nested_all_zero_falls_back_to_flat(self):
        u = extract_usage(self._assistant({
            "input_tokens": 10, "output_tokens": 3,
            "cache_creation_input_tokens": 42,
            "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0},
        }))
        self.assertEqual(u["cache_creation_5m"], 0)
        self.assertEqual(u["cache_creation_1h"], 42)

    def test_unrecognized_nested_key_summed_into_1h(self):
        u = extract_usage(self._assistant({
            "input_tokens": 10, "output_tokens": 3,
            "cache_creation": {"ephemeral_5m_input_tokens": 1, "ephemeral_90d_input_tokens": 500},
        }))
        self.assertEqual(u["cache_creation_5m"], 1)
        self.assertEqual(u["cache_creation_1h"], 500)

    def test_cache_absent(self):
        u = extract_usage(self._assistant({"input_tokens": 10, "output_tokens": 3}))
        self.assertEqual(u["cache_creation_5m"], 0)
        self.assertEqual(u["cache_creation_1h"], 0)


class TestPickPrimaryModel(unittest.TestCase):
    def _m(self, input_tokens, cache_creation_total, cache_read_tokens, output_tokens, assistant_messages):
        return {
            "input_tokens": input_tokens, "cache_creation_total": cache_creation_total,
            "cache_read_tokens": cache_read_tokens, "output_tokens": output_tokens,
            "assistant_messages": assistant_messages,
        }

    def test_empty(self):
        self.assertIsNone(pick_primary_model({}))

    def test_highest_volume_wins(self):
        per_model = {
            "model-a": self._m(100, 0, 0, 0, 1),
            "model-b": self._m(200, 0, 0, 0, 1),
        }
        self.assertEqual(pick_primary_model(per_model), "model-b")

    def test_tie_on_volume_broken_by_assistant_messages(self):
        per_model = {
            "model-a": self._m(100, 0, 0, 0, 1),
            "model-b": self._m(100, 0, 0, 0, 5),
        }
        self.assertEqual(pick_primary_model(per_model), "model-b")

    def test_tie_on_volume_and_messages_broken_lexically(self):
        per_model = {
            "model-z": self._m(100, 0, 0, 0, 1),
            "model-a": self._m(100, 0, 0, 0, 1),
        }
        self.assertEqual(pick_primary_model(per_model), "model-a")


class TestApplyThresholds(unittest.TestCase):
    def test_strict_greater_than(self):
        self.assertEqual(apply_thresholds(175, 0, 175, 1000), (False, []))
        self.assertEqual(apply_thresholds(176, 0, 175, 1000), (True, ["api_turns"]))

    def test_or_logic_both_reasons(self):
        flagged, reasons = apply_thresholds(200, 2000, 175, 1000)
        self.assertTrue(flagged)
        self.assertEqual(sorted(reasons), ["api_turns", "cache_creation_total"])


class TestSmallHelpers(unittest.TestCase):
    def test_is_meta_line(self):
        self.assertTrue(is_meta_line({"isMeta": True}))
        self.assertFalse(is_meta_line({"isMeta": False}))
        self.assertFalse(is_meta_line({}))

    def test_is_tool_result_line(self):
        self.assertTrue(is_tool_result_line({"type": "user", "message": {"content": [{"type": "tool_result"}]}}))
        self.assertFalse(is_tool_result_line({"type": "user", "message": {"content": "plain text"}}))
        self.assertFalse(is_tool_result_line({"type": "assistant"}))


# --------------------------------------------------------------------------
# Steps 4-5: SessionAccumulator / scan_file / sessions.csv / model rows
# --------------------------------------------------------------------------


class TestFixtureRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.guardrails, cls.model_rows = run_scan(FIXTURES_ROOT)

    def test_row_count(self):
        # 10 fixture files, 1 excluded (J) -> 9 rows.
        self.assertEqual(len(self.rows), 9)

    def test_fixture_A_real_work_dedup_multi_model(self):
        r = row_by_id(self.rows, "11111111-1111-1111-1111-111111111111")
        self.assertEqual(r["classification"], "real_work")
        self.assertEqual(r["classification_basis"], "prompt_source")
        self.assertEqual(r["api_turns"], 3)
        self.assertEqual(r["user_prompts"], 2)
        self.assertEqual(r["assistant_messages"], 3)  # not 4 -- msg_A1 deduped
        self.assertEqual(r["model_count"], 2)
        self.assertEqual(r["input_tokens"], 150)
        self.assertEqual(r["cache_read_tokens"], 200)
        self.assertEqual(r["output_tokens"], 80)
        self.assertEqual(r["cache_creation_5m"], 20)
        self.assertEqual(r["cache_creation_1h"], 45)
        self.assertEqual(r["cache_creation_total"], 65)
        self.assertEqual(r["primary_model"], "claude-haiku-4-5")
        self.assertEqual(r["models"], "claude-haiku-4-5;claude-sonnet-5")

    def test_fixture_B_automated(self):
        r = row_by_id(self.rows, "22222222-2222-2222-2222-222222222222")
        self.assertEqual(r["classification"], "automated")
        self.assertEqual(r["classification_basis"], "prompt_source")

    def test_fixture_C_entrypoint_fallback(self):
        r = row_by_id(self.rows, "33333333-3333-3333-3333-333333333333")
        self.assertEqual(r["classification"], "real_work")
        self.assertEqual(r["classification_basis"], "entrypoint_fallback")

    def test_fixture_D_malformed_line(self):
        r = row_by_id(self.rows, "44444444-4444-4444-4444-444444444444")
        self.assertEqual(r["malformed_lines"], 1)
        # row still emitted (not dropped)
        self.assertIsNotNone(r)

    def test_fixture_E_no_user_lines(self):
        r = row_by_id(self.rows, "55555555-5555-5555-5555-555555555555")
        self.assertEqual(r["classification"], "unclassified")
        self.assertEqual(r["classification_basis"], "no_user_lines")
        self.assertEqual(r["api_turns"], 0)
        self.assertEqual(r["user_prompts"], 0)
        self.assertEqual(r["assistant_messages"], 0)
        self.assertEqual(r["input_tokens"], 0)
        self.assertIsNotNone(r["first_ts"])  # timestamps still populated
        self.assertIsNotNone(r["last_ts"])

    def test_fixture_F_unknown_prompt_source(self):
        r = row_by_id(self.rows, "66666666-6666-6666-6666-666666666666")
        self.assertEqual(r["classification"], "unclassified")
        self.assertEqual(r["classification_basis"], "unknown_prompt_source")

    def test_fixture_G_subagent_flat_growing_repeat(self):
        r = row_by_id(self.rows, "agent-abc0000000000001")
        self.assertEqual(r["classification"], "subagent")
        self.assertEqual(r["classification_basis"], "path")
        self.assertEqual(r["parent_session_id"], "11111111-1111-1111-1111-111111111111")
        # sidechain exclusion NOT applied to subagent rows -- api_turns=2,
        # not 0 (the regression this proves against).
        self.assertEqual(r["api_turns"], 2)
        # dedup last-occurrence matters here: last output_tokens=250, not
        # the first (smaller) occurrence's 100.
        self.assertEqual(r["output_tokens"], 250)
        self.assertNotEqual(r["output_tokens"], 100)
        # A's tokens must not be folded into this row or vice versa.
        a = row_by_id(self.rows, "11111111-1111-1111-1111-111111111111")
        self.assertNotEqual(a["output_tokens"], r["output_tokens"])

    def test_fixture_H_filter_target(self):
        r = row_by_id(self.rows, "88888888-8888-8888-8888-888888888888")
        self.assertEqual(r["project"], "proj-beta")
        self.assertEqual(r["classification"], "real_work")

    def test_fixture_I_workflow_nested_subagent(self):
        r = row_by_id(self.rows, "agent-def0000000000001")
        self.assertEqual(r["classification"], "subagent")
        self.assertEqual(r["classification_basis"], "path")
        self.assertEqual(r["parent_session_id"], "33333333-3333-3333-3333-333333333333")
        self.assertEqual(r["api_turns"], 1)  # sidechain exclusion not applied

    def test_fixture_J_excluded_non_transcript(self):
        session_ids = [r["session_id"] for r in self.rows]
        self.assertNotIn("journal", session_ids)
        self.assertEqual(self.guardrails["files_excluded_non_transcript"], 1)

    def test_dedup_last_occurrence(self):
        # Same assertion as fixture G's test, isolated as its own named test
        # per the plan's Verification section.
        r = row_by_id(self.rows, "agent-abc0000000000001")
        self.assertEqual(r["output_tokens"], 250)

    def test_no_double_count_on_byte_identical_repeat(self):
        # If dedup were broken (naive per-line summation), A's msg_A1 would
        # be counted twice: input_tokens would be 250 (100+100+40+10)
        # instead of 150, output_tokens 130 instead of 80.
        a = row_by_id(self.rows, "11111111-1111-1111-1111-111111111111")
        self.assertEqual(a["input_tokens"], 150)
        self.assertNotEqual(a["input_tokens"], 250)
        self.assertEqual(a["output_tokens"], 80)
        self.assertNotEqual(a["output_tokens"], 130)


class TestModelRowsSumToSession(unittest.TestCase):
    def test_model_rows_sum_to_session(self):
        rows, _guardrails, model_rows = run_scan(FIXTURES_ROOT)
        fields = ["input_tokens", "cache_creation_5m", "cache_creation_1h",
                   "cache_creation_total", "cache_read_tokens", "output_tokens"]
        for r in rows:
            this_session_models = [m for m in model_rows if m["session_id"] == r["session_id"]]
            for f in fields:
                self.assertEqual(
                    sum(m[f] for m in this_session_models), r[f],
                    "field %s mismatch for session %s" % (f, r["session_id"]),
                )
            self.assertEqual(len(this_session_models), r["model_count"])


# --------------------------------------------------------------------------
# Step 6: filters + thresholds
# --------------------------------------------------------------------------


class TestFilters(unittest.TestCase):
    def test_project_filter(self):
        rows, _g, _m = run_scan(FIXTURES_ROOT, project="beta")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["project"], "proj-beta")

    def test_since_filter_excludes_only_H(self):
        unfiltered_rows, _g, _m = run_scan(FIXTURES_ROOT)
        total = len(unfiltered_rows)
        filtered_rows, guardrails, _m2 = run_scan(FIXTURES_ROOT, since="2026-02-01")
        self.assertEqual(len(filtered_rows), total - 1)
        session_ids = [r["session_id"] for r in filtered_rows]
        self.assertNotIn("88888888-8888-8888-8888-888888888888", session_ids)
        self.assertGreaterEqual(guardrails["files_filtered_out"], 1)

    def test_invariant_unfiltered_run(self):
        rows, guardrails, _m = run_scan(FIXTURES_ROOT)
        self.assertEqual(
            len(rows) + guardrails["files_unreadable"] + guardrails["files_excluded_non_transcript"],
            guardrails["files_seen"],
        )

    def test_invariant_filtered_run(self):
        rows, guardrails, _m = run_scan(FIXTURES_ROOT, since="2026-02-01")
        self.assertEqual(
            len(rows) + guardrails["files_unreadable"] + guardrails["files_excluded_non_transcript"]
            + guardrails["files_filtered_out"] + guardrails["rows_excluded_no_timestamp"],
            guardrails["files_seen"],
        )


class TestThresholds(unittest.TestCase):
    def test_thresholds_low(self):
        # Fixture A: api_turns=3, cache_creation_total=65 -- exercise the
        # strict `>` boundary and the OR/both-reasons logic against a real
        # scanned row (not just the pure apply_thresholds unit).
        rows, _g, _m = run_scan(FIXTURES_ROOT, max_turns=3, max_cache_creation=65)
        a = row_by_id(rows, "11111111-1111-1111-1111-111111111111")
        self.assertFalse(a["flagged"])  # equal, not strictly greater -- not flagged

        rows, _g, _m = run_scan(FIXTURES_ROOT, max_turns=2, max_cache_creation=1_000_000)
        a = row_by_id(rows, "11111111-1111-1111-1111-111111111111")
        self.assertTrue(a["flagged"])
        self.assertEqual(a["flag_reasons"], "api_turns")

        rows, _g, _m = run_scan(FIXTURES_ROOT, max_turns=1_000_000, max_cache_creation=64)
        a = row_by_id(rows, "11111111-1111-1111-1111-111111111111")
        self.assertTrue(a["flagged"])
        self.assertEqual(a["flag_reasons"], "cache_creation_total")

        rows, _g, _m = run_scan(FIXTURES_ROOT, max_turns=2, max_cache_creation=64)
        a = row_by_id(rows, "11111111-1111-1111-1111-111111111111")
        self.assertTrue(a["flagged"])
        self.assertEqual(a["flag_reasons"], "api_turns;cache_creation_total")  # sorted, both

    def test_thresholds_apply_to_automated(self):
        # Fixture B is automated, not real_work -- thresholds must still
        # apply (per Design/Thresholds: "applied to every row").
        rows, _g, _m = run_scan(FIXTURES_ROOT, max_turns=0, max_cache_creation=1_000_000)
        b = row_by_id(rows, "22222222-2222-2222-2222-222222222222")
        self.assertEqual(b["classification"], "automated")
        self.assertTrue(b["flagged"])

    def test_multivalued_column_format(self):
        rows, _g, _m = run_scan(FIXTURES_ROOT)
        a = row_by_id(rows, "11111111-1111-1111-1111-111111111111")
        self.assertEqual(a["models"], "claude-haiku-4-5;claude-sonnet-5")  # sorted, ;-joined

        rows, _g, _m = run_scan(FIXTURES_ROOT, max_turns=2, max_cache_creation=64)
        a = row_by_id(rows, "11111111-1111-1111-1111-111111111111")
        self.assertEqual(a["flag_reasons"], "api_turns;cache_creation_total")  # sorted, ;-joined


# --------------------------------------------------------------------------
# Step 7: error handling / guardrails
# --------------------------------------------------------------------------


class TestErrorHandling(unittest.TestCase):
    def test_no_crash_on_unreadable_nonexistent_path(self):
        guardrails = new_guardrails()
        result, info = process_file("/nonexistent/path/foo.jsonl", "/nonexistent/path", guardrails)
        self.assertIsNone(result)
        self.assertEqual(guardrails["files_unreadable"], 1)

    def test_no_crash_on_unreadable_directory_as_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            trap = os.path.join(tmp, "trap.jsonl")
            os.makedirs(trap)  # a directory whose name ends in .jsonl
            guardrails = new_guardrails()
            result, info = process_file(trap, tmp, guardrails)
            self.assertIsNone(result)
            self.assertEqual(guardrails["files_unreadable"], 1)

    def test_cross_file_duplicate_counter(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = os.path.join(tmp, "proj-dup")
            os.makedirs(proj)
            shared_id = "msg_SHARED1"
            f1 = os.path.join(proj, "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa.jsonl")
            f2 = os.path.join(proj, "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb.jsonl")
            with open(f1, "w") as fh:
                fh.write('{"type": "user", "isSidechain": false, "promptSource": "typed", "entrypoint": "cli", "timestamp": "2026-07-01T00:00:00.000Z", "message": {"role": "user", "content": "hi"}}\n')
                fh.write('{"type": "assistant", "timestamp": "2026-07-01T00:00:01.000Z", "message": {"id": "%s", "model": "claude-sonnet-5", "usage": {"input_tokens": 10, "output_tokens": 5}}}\n' % shared_id)
            with open(f2, "w") as fh:
                fh.write('{"type": "user", "isSidechain": false, "promptSource": "typed", "entrypoint": "cli", "timestamp": "2026-07-02T00:00:00.000Z", "message": {"role": "user", "content": "hi again"}}\n')
                fh.write('{"type": "assistant", "timestamp": "2026-07-02T00:00:01.000Z", "message": {"id": "%s", "model": "claude-sonnet-5", "usage": {"input_tokens": 10, "output_tokens": 5}}}\n' % shared_id)

            rows, guardrails, _m = run_scan(tmp)
            self.assertEqual(len(rows), 2)
            self.assertEqual(guardrails["cross_file_duplicate_ids"], 1)
            # Both sessions keep their full tokens -- never subtracted.
            for r in rows:
                self.assertEqual(r["input_tokens"], 10)
                self.assertEqual(r["output_tokens"], 5)


# --------------------------------------------------------------------------
# Step 9: Parquet output
# --------------------------------------------------------------------------


def _run_main(argv):
    """Runs session_analysis.main() with the given argv (argv[0] is the
    program name, matching sys.argv's own shape). Returns the SystemExit
    code. main() always calls sys.exit() on success (0) or parser.error()
    (2) -- never returns normally."""
    with mock.patch.object(sys, "argv", argv):
        with unittest.TestCase().assertRaises(SystemExit) as cm:
            session_analysis.main()
    return cm.exception.code


class TestParquetAbsentPath(unittest.TestCase):
    """pyarrow genuinely uninstalled OR forced absent via sys.modules --
    runs on every machine regardless of whether pyarrow happens to be
    installed here."""

    def test_pyarrow_absent_still_exits_zero_with_correct_csvs_no_parquet(self):
        with tempfile.TemporaryDirectory() as out_dir:
            argv = ["session_analysis.py", "--root", FIXTURES_ROOT, "--out-dir", out_dir]
            with mock.patch.dict(sys.modules, {"pyarrow": None}):
                code = _run_main(argv)
            self.assertEqual(code, 0)

            self.assertTrue(os.path.isfile(os.path.join(out_dir, "sessions.csv")))
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "session_model_tokens.csv")))
            self.assertFalse(os.path.exists(os.path.join(out_dir, "sessions.parquet")))
            self.assertFalse(os.path.exists(os.path.join(out_dir, "session_model_tokens.parquet")))

            with open(os.path.join(out_dir, "session_summary.json"), encoding="utf-8") as f:
                summary = json.load(f)
            self.assertFalse(summary["pyarrow_available"])
            # CSV row count still correct (9 -- fixture J excluded) -- proves
            # the absent-parquet path doesn't disturb CSV output at all.
            with open(os.path.join(out_dir, "sessions.csv"), encoding="utf-8") as f:
                self.assertEqual(sum(1 for _ in f) - 1, 9)  # -1 for header

    def test_no_parquet_flag_writes_no_parquet_files(self):
        # Portable regardless of whether pyarrow happens to be installed on
        # this machine -- the flag alone must suppress writing.
        with tempfile.TemporaryDirectory() as out_dir:
            argv = ["session_analysis.py", "--root", FIXTURES_ROOT, "--out-dir", out_dir, "--no-parquet"]
            code = _run_main(argv)
            self.assertEqual(code, 0)
            self.assertFalse(os.path.exists(os.path.join(out_dir, "sessions.parquet")))
            self.assertFalse(os.path.exists(os.path.join(out_dir, "session_model_tokens.parquet")))
            self.assertTrue(os.path.isfile(os.path.join(out_dir, "sessions.csv")))


@unittest.skipUnless(HAVE_PYARROW, "requires pyarrow")
class TestParquetPresentPath(unittest.TestCase):
    """Skip-unless: only runs if pyarrow is actually installed. Not
    installed in this environment as of this writing -- verify by gating,
    not by attempting to pip install anything."""

    def test_schema_matches_explicit_builder_and_parent_id_is_string(self):
        import pyarrow as pa
        import pyarrow.parquet as pq

        with tempfile.TemporaryDirectory() as out_dir:
            argv = ["session_analysis.py", "--root", FIXTURES_ROOT, "--out-dir", out_dir]
            code = _run_main(argv)
            self.assertEqual(code, 0)

            with open(os.path.join(out_dir, "session_summary.json"), encoding="utf-8") as f:
                summary = json.load(f)
            self.assertTrue(summary["pyarrow_available"])

            session_table = pq.read_table(os.path.join(out_dir, "sessions.parquet"))
            expected_session_schema = session_analysis.session_parquet_schema(pa)
            self.assertEqual(session_table.schema, expected_session_schema)
            self.assertEqual(
                session_table.schema.field("parent_session_id").type, pa.string()
            )
            self.assertNotEqual(
                session_table.schema.field("parent_session_id").type, pa.null()
            )

            model_table = pq.read_table(os.path.join(out_dir, "session_model_tokens.parquet"))
            expected_model_schema = session_analysis.model_parquet_schema(pa)
            self.assertEqual(model_table.schema, expected_model_schema)

    def test_no_parquet_flag_with_pyarrow_present(self):
        with tempfile.TemporaryDirectory() as out_dir:
            argv = ["session_analysis.py", "--root", FIXTURES_ROOT, "--out-dir", out_dir, "--no-parquet"]
            code = _run_main(argv)
            self.assertEqual(code, 0)
            self.assertFalse(os.path.exists(os.path.join(out_dir, "sessions.parquet")))
            with open(os.path.join(out_dir, "session_summary.json"), encoding="utf-8") as f:
                summary = json.load(f)
            # pyarrow IS importable here (class-level skip-unless) -- the
            # flag suppresses writing, not the availability report.
            self.assertTrue(summary["pyarrow_available"])

    def test_from_pylist_naive_inference_would_produce_null_typed_column(self):
        # Documented reasoning, not just re-asserting the explicit-schema
        # path: demonstrate that from_pylist's own inference -- which
        # try_write_parquet deliberately avoids -- WOULD have produced a
        # null-typed parent_session_id column on this exact fixture data.
        # Fixture file-walk order sorts the top-level (null-parent) row
        # first (see tests/fixtures/projects listing: proj-alpha's
        # 1111...jsonl top-level file sorts before any subagents/ path),
        # which is precisely the ordering that triggers pyarrow's
        # null-type-inference bug when from_pylist sees a leading None.
        import pyarrow as pa

        rows, _guardrails, _model_rows = run_scan(FIXTURES_ROOT)
        self.assertIsNone(rows[0]["parent_session_id"])  # confirms the ordering claim
        minimal = [{"parent_session_id": r["parent_session_id"]} for r in rows]
        inferred_table = pa.Table.from_pylist(minimal)
        self.assertEqual(
            inferred_table.schema.field("parent_session_id").type, pa.null(),
            "expected from_pylist's naive inference to produce a null-typed "
            "column here -- if this now fails, pyarrow's inference behavior "
            "changed and the explicit-schema rationale should be re-verified",
        )
        # And contrast: the tool's own explicit schema keeps it a string.
        explicit_schema = session_analysis.session_parquet_schema(pa)
        self.assertEqual(explicit_schema.field("parent_session_id").type, pa.string())


# --------------------------------------------------------------------------
# Step 10: real-corpus regression invariants
# --------------------------------------------------------------------------


def _percentile(sorted_vals, pct):
    """Linear-interpolation percentile (matches numpy's default 'linear'
    method) over an already-sorted list."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


@unittest.skipUnless(os.path.isdir(REAL_ROOT), "requires ~/.claude/projects")
class TestRealCorpusInvariants(unittest.TestCase):
    """Corpus-scale regression tests (Design plan's Verification/Real-corpus
    invariants section, step 10). ONE unfiltered full-tree scan is run once
    in setUpClass and shared across every test method below -- a full scan
    is the expensive part (full ~17,500-file/~2.8GB tree), so re-running it
    per-assertion would multiply runtime for no benefit.

    Machine-specificity caveat (applies to invariants 4, 5, 6, 7 -- see
    README.md): the absolute-count/percentile bands below are calibrated
    against THIS development machine's corpus. A failure on a different
    machine's ~/.claude/projects should prompt re-deriving the bands there,
    not an assumption the tool itself is broken. Invariants 1, 2, 3, 8, 9
    have no such caveat -- they check structural properties (no silent
    drops, dedup firing, runtime budget) that hold regardless of corpus
    mix."""

    @classmethod
    def setUpClass(cls):
        guardrails = new_guardrails()
        seen_msgids = set()
        rows = []
        model_rows = []
        t0 = time.time()
        for path in iter_transcript_files(REAL_ROOT):
            guardrails["files_seen"] += 1
            result, _info = process_file(path, REAL_ROOT, guardrails)
            if result is None:
                continue
            row, per_model = result
            for mid in row.get("_message_ids") or []:
                if mid in seen_msgids:
                    guardrails["cross_file_duplicate_ids"] += 1
                else:
                    seen_msgids.add(mid)
            flagged, reasons = apply_thresholds(row["api_turns"], row["cache_creation_total"], 175, 1525000)
            row["flagged"] = flagged
            row["flag_reasons"] = ";".join(sorted(reasons))
            rows.append(row)
            model_rows.extend(
                build_model_rows(row["session_id"], row["project"], row["classification"], per_model)
            )
        cls.elapsed = time.time() - t0
        cls.rows = rows
        cls.guardrails = guardrails
        cls.model_rows = model_rows
        cls.distinct_ids = len(seen_msgids)
        cls.top_level_session_ids = {r["session_id"] for r in rows if r["parent_session_id"] is None}

    # -- Invariant 1: rows + files_unreadable + files_excluded_non_transcript == files_seen
    def test_invariant_1_no_silent_drops(self):
        g = self.guardrails
        self.assertEqual(
            len(self.rows) + g["files_unreadable"] + g["files_excluded_non_transcript"],
            g["files_seen"],
            "unfiltered-run accounting must be exact -- any gap is a silent drop",
        )

    # -- Invariant 2: subagent parent coverage + both-depths detection
    def test_invariant_2_subagent_parent_and_depth_coverage(self):
        subagent_rows = [r for r in self.rows if r["classification"] == "subagent"]
        no_parent = [r for r in subagent_rows if r["parent_session_id"] is None]
        self.assertEqual(len(no_parent), 0, "every subagent row in this corpus is expected to resolve a parent")

        parent_ids = {r["parent_session_id"] for r in subagent_rows if r["parent_session_id"]}
        self.assertGreater(len(parent_ids), 0)
        matched = sum(1 for pid in parent_ids if pid in self.top_level_session_ids)
        self.assertGreaterEqual(
            matched / len(parent_ids), 0.99,
            "fewer than 99%% of subagent parent_session_ids resolve to a top-level session_id",
        )

        # Both-depths coverage: re-derive flat vs workflow-nested file
        # counts directly (cheap -- identify_file does no file I/O) and
        # confirm the row count tracks both, and specifically that the
        # nested depth is non-trivially represented (this is exactly the
        # invariant that would have caught the 683-file miss before it
        # shipped).
        flat_files = 0
        nested_files = 0
        for path in iter_transcript_files(REAL_ROOT):
            info = identify_file(path, REAL_ROOT)
            if info["kind"] != "subagent":
                continue
            rel = os.path.relpath(path, REAL_ROOT)
            dir_parts = rel.split(os.sep)[:-1]
            idx = dir_parts.index("subagents")
            if idx == len(dir_parts) - 1:
                flat_files += 1
            else:
                nested_files += 1

        total_subagent_files = flat_files + nested_files
        self.assertGreater(nested_files, 400, "workflow-nested subagent files near-zero -- depth-agnostic detection may have regressed")
        self.assertGreater(flat_files, 4000)
        # Row count should track file count closely -- the only legitimate
        # gap is files_unreadable among subagent files, expected to be ~0.
        diff = abs(len(subagent_rows) - total_subagent_files)
        self.assertLessEqual(
            diff, max(5, int(0.03 * total_subagent_files)),
            "subagent row count %d vs subagent file count %d diverge by more than a few percent"
            % (len(subagent_rows), total_subagent_files),
        )

    # -- Invariant 3: dedup is firing
    def test_invariant_3_dedup_ratio(self):
        total_assistant_messages = sum(r["assistant_messages"] for r in self.rows)
        usage_lines_seen = self.guardrails["usage_lines_seen"]
        self.assertGreater(usage_lines_seen, 0)
        ratio = total_assistant_messages / usage_lines_seen
        self.assertTrue(
            0.30 <= ratio <= 0.55,
            "dedup ratio %.4f outside [0.30,0.55] -- ratio near 1.0 means dedup stopped firing" % ratio,
        )

    # -- Invariant 4: classification split (full corpus)
    def test_invariant_4_classification_split(self):
        counts = {}
        for r in self.rows:
            counts[r["classification"]] = counts.get(r["classification"], 0) + 1
        full_corpus_total = self.guardrails["files_seen"]

        real_work = counts.get("real_work", 0)
        automated = counts.get("automated", 0)
        subagent = counts.get("subagent", 0)
        unclassified = counts.get("unclassified", 0)

        self.assertTrue(
            400 <= real_work <= 700,
            "real_work=%d outside [400,700] -- KEPT TIGHT deliberately (see plan/README): "
            "a jump toward ~1178 means the workflow-nested subagent-path fix regressed" % real_work,
        )
        self.assertTrue(9000 <= automated <= 12000, "automated=%d outside [9000,12000]" % automated)
        self.assertTrue(6500 <= subagent <= 7500, "subagent=%d outside [6500,7500]" % subagent)
        self.assertLessEqual(
            unclassified, 0.01 * full_corpus_total,
            "unclassified=%d exceeds 1%% of full-corpus total %d" % (unclassified, full_corpus_total),
        )

    # -- Invariant 5: threshold provenance (real_work population only)
    def test_invariant_5_threshold_provenance(self):
        real_work_rows = [r for r in self.rows if r["classification"] == "real_work"]
        self.assertGreater(len(real_work_rows), 50, "too few real_work rows to derive a meaningful p95")

        p95_turns = _percentile(sorted(r["api_turns"] for r in real_work_rows), 95)
        p95_cache = _percentile(sorted(r["cache_creation_total"] for r in real_work_rows), 95)

        self.assertTrue(
            175 * 0.8 <= p95_turns <= 175 * 1.2,
            "re-derive defaults and update README (api_turns p95=%.1f, default=175)" % p95_turns,
        )
        self.assertTrue(
            1525000 * 0.8 <= p95_cache <= 1525000 * 1.2,
            "re-derive defaults and update README (cache_creation_total p95=%.0f, default=1525000)" % p95_cache,
        )

    # -- Invariant 6: flag rate on real_work
    def test_invariant_6_flag_rate_real_work(self):
        real_work_rows = [r for r in self.rows if r["classification"] == "real_work"]
        flagged = sum(1 for r in real_work_rows if r["flagged"])
        rate = flagged / len(real_work_rows)
        self.assertTrue(0.02 <= rate <= 0.12, "real_work flag rate %.4f outside [0.02,0.12]" % rate)

    # -- Invariant 7: user_prompts <= api_turns everywhere; real_work ratio band
    def test_invariant_7_user_prompts_le_api_turns(self):
        for r in self.rows:
            self.assertLessEqual(
                r["user_prompts"], r["api_turns"],
                "user_prompts > api_turns for session_id=%s (should be structurally impossible)" % r["session_id"],
            )

        real_work_ratios = [
            r["api_turns"] / r["user_prompts"]
            for r in self.rows
            if r["classification"] == "real_work" and r["user_prompts"] > 0
        ]
        self.assertGreater(len(real_work_ratios), 0)
        median_real_work = statistics.median(real_work_ratios)
        self.assertTrue(
            2.5 <= median_real_work <= 6.0,
            "real_work median api_turns/user_prompts=%.2f outside [2.5,6.0]" % median_real_work,
        )

        other_ratios = [
            r["api_turns"] / r["user_prompts"]
            for r in self.rows
            if r["classification"] in ("automated", "subagent") and r["user_prompts"] > 0
        ]
        if other_ratios:
            median_other = statistics.median(other_ratios)
            # "Near 1.0" per plan -- asserted as well below the real_work
            # floor of 2.5 rather than pinned to a tight band of its own,
            # since a drift toward the real_work band is the failure mode
            # actually worth catching here.
            self.assertLess(
                median_other, 2.0,
                "automated/subagent median ratio=%.2f should sit near 1.0, well below real_work's 2.5 floor" % median_other,
            )

    # -- Invariant 8: cross-file duplicate id rate
    def test_invariant_8_cross_file_duplicate_rate(self):
        dup = self.guardrails["cross_file_duplicate_ids"]
        self.assertGreater(self.distinct_ids, 0)
        rate = dup / self.distinct_ids
        self.assertLessEqual(
            rate, 0.005,
            "cross-file duplicate rate %.4f%% exceeds 0.5%% -- README's <=0.1%% caveat is stale" % (rate * 100),
        )

    # -- Invariant 9: full-corpus runtime budget
    def test_invariant_9_runtime_budget(self):
        self.assertLess(
            self.elapsed, 45,
            "full-corpus scan took %.1fs, exceeding the 45s budget" % self.elapsed,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
