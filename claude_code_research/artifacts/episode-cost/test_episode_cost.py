"""Tests for episode_cost.py using tiny synthetic transcripts.

Run from this directory:  python3 -m unittest -v test_episode_cost
Standard library only.
"""
import json
import os
import tempfile
import unittest

import episode_cost as E

PROJ = "-proj-demo"


def asst(msg_id, ts, model="claude-sonnet-5", branch="main", out=0, inp=0,
         read=0, cw1h=0, entrypoint="cli"):
    return {
        "type": "assistant", "timestamp": ts, "gitBranch": branch,
        "entrypoint": entrypoint,
        "message": {"id": msg_id, "model": model, "usage": {
            "input_tokens": inp, "output_tokens": out,
            "cache_read_input_tokens": read,
            "cache_creation_input_tokens": cw1h,
            "cache_creation": {"ephemeral_5m_input_tokens": 0,
                               "ephemeral_1h_input_tokens": cw1h}}},
    }


def user(text, ts="2026-09-01T00:00:00Z", entrypoint="cli"):
    return {"type": "user", "timestamp": ts, "entrypoint": entrypoint,
            "message": {"role": "user", "content": text}}


def title(text):
    return {"type": "custom-title", "customTitle": text}


class Store:
    """Builds a throwaway projects root."""

    def __init__(self, tc):
        self.tmp = tempfile.TemporaryDirectory()
        tc.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def session(self, sid, entries, project=PROJ):
        d = os.path.join(self.root, project)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, sid + ".jsonl"), "w") as fh:
            for e in entries:
                fh.write(json.dumps(e) + "\n")

    def subagent(self, sid, agent, entries, agent_type="Explore", project=PROJ,
                 nested=None):
        d = os.path.join(self.root, project, sid, "subagents")
        if nested:
            d = os.path.join(d, *nested)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "agent-%s.jsonl" % agent), "w") as fh:
            for e in entries:
                fh.write(json.dumps(e) + "\n")
        with open(os.path.join(d, "agent-%s.meta.json" % agent), "w") as fh:
            json.dump({"agentType": agent_type}, fh)


def run(tc, store, issues=None, **kw):
    scanned = E.scan_store(store.root, ["*"])
    res = E.build(scanned, issues or [], **kw)
    return scanned, res


def session_row(res, sid):
    return next(r for r in res["sessions"] if r["session_id"] == sid)


class PricingTests(unittest.TestCase):
    def test_exact_cost_arithmetic(self):
        # 1M input + 1M output on sonnet-5 = $2 + $10
        p, _, path = E.resolve_price("claude-sonnet-5")
        self.assertEqual(path, "exact")
        rec = {"input": 10**6, "output": 10**6, "cw5m": 0, "cw1h": 0, "read": 0}
        self.assertEqual(E.fmt_usd(E.cost_nano(p, rec)), "12.0000")

    def test_cache_rates_and_special_reads(self):
        rec = {"input": 0, "output": 0, "cw5m": 0, "cw1h": 0, "read": 10**6}
        for model, usd in (("claude-opus-5-5", "0.2000"), ("claude-opus-5", "0.5000"),
                           ("claude-fable-5-1", "0.2500"), ("claude-fable-5", "1.0000"),
                           ("claude-haiku-4-5-20251001", "0.1000")):
            p, _, _ = E.resolve_price(model)
            self.assertEqual(E.fmt_usd(E.cost_nano(p, rec)), usd, model)
        rec = {"input": 0, "output": 0, "cw5m": 10**6, "cw1h": 10**6, "read": 0}
        p, _, _ = E.resolve_price("claude-opus-5-5")
        self.assertEqual(E.fmt_usd(E.cost_nano(p, rec)), "13.0000")  # 5 + 8

    def test_unknown_models(self):
        _, _, path = E.resolve_price("claude-opus-9-9")
        self.assertEqual(path, "fallback")
        _, _, path = E.resolve_price("gpt-5.6-luna")
        self.assertEqual(path, "unpriced")


class AttributionTests(unittest.TestCase):
    def test_title_signal(self):
        s = Store(self)
        s.session("s1", [title("#10 add thing"), user("hello"),
                         asst("m1", "2026-09-01T10:00:00Z", out=100)])
        sc, res = run(self, s)
        row = session_row(res, "s1")
        self.assertEqual((row["signal"], row["issues"], row["verdict"]),
                         ("title", "10", "issue"))
        self.assertIn(10, res["issues"])

    def test_latest_title_wins(self):
        s = Store(self)
        s.session("s1", [title("#10 old"), title("#11 renamed"),
                         asst("m1", "2026-09-01T10:00:00Z")])
        _, res = run(self, s)
        self.assertEqual(session_row(res, "s1")["issues"], "11")

    def test_branch_signal_forms(self):
        for branch, expect in (("issue-12", "12"), ("feature/issue-12-some-slug", "12"),
                               ("feature/issue-4307-phase1-and-4313", "4307")):
            s = Store(self)
            s.session("s1", [asst("m1", "2026-09-01T10:00:00Z", branch=branch)])
            _, res = run(self, s)
            row = session_row(res, "s1")
            self.assertEqual((row["signal"], row["issues"]), ("branch", expect), branch)

    def test_non_issue_branches_do_not_attribute(self):
        s = Store(self)
        s.session("s1", [asst("m1", "2026-09-01T10:00:00Z", branch="main"),
                         asst("m2", "2026-09-01T10:01:00Z", branch="feature/other-thing")])
        _, res = run(self, s)
        self.assertEqual(session_row(res, "s1")["verdict"], "unattributed")

    def test_task_prompt_signal(self):
        s = Store(self)
        s.session("s1", [user("Context\nTask: #77 do the thing\nmore"),
                         asst("m1", "2026-09-01T10:00:00Z")])
        _, res = run(self, s)
        row = session_row(res, "s1")
        self.assertEqual((row["signal"], row["issues"]), ("task", "77"))

    def test_task_prompt_must_start_a_line_and_be_the_first_prompt(self):
        s = Store(self)
        s.session("s1", [user("see the Task: #77 note inline"),
                         asst("m1", "2026-09-01T10:00:00Z")])
        s.session("s2", [user("first prompt"), user("Task: #78 second prompt"),
                         asst("m2", "2026-09-01T10:00:00Z")])
        _, res = run(self, s)
        self.assertEqual(session_row(res, "s1")["verdict"], "unattributed")
        self.assertEqual(session_row(res, "s2")["verdict"], "unattributed")

    def test_priority_title_over_branch_over_task(self):
        s = Store(self)
        s.session("a", [title("#1 x"), user("Task: #3 y"),
                        asst("m1", "2026-09-01T10:00:00Z", branch="issue-2")])
        s.session("b", [user("Task: #3 y"),
                        asst("m2", "2026-09-01T10:00:00Z", branch="issue-2")])
        _, res = run(self, s)
        self.assertEqual((session_row(res, "a")["signal"], session_row(res, "a")["issues"]),
                         ("title", "1"))
        self.assertEqual((session_row(res, "b")["signal"], session_row(res, "b")["issues"]),
                         ("branch", "2"))

    def test_turn_branch_wins_sensitivity_mode(self):
        s = Store(self)
        s.session("a", [title("#1 x"),
                        asst("m1", "2026-09-01T10:00:00Z", branch="main", out=10),
                        asst("m2", "2026-09-01T10:01:00Z", branch="issue-2", out=10)])
        _, res = run(self, s)
        self.assertEqual(set(res["issues"]), {1})
        _, res = run(self, s, branch_wins=True)
        self.assertEqual(set(res["issues"]), {1, 2})

    def test_unattributed_bucket_is_explicit_and_counted(self):
        s = Store(self)
        s.session("s1", [asst("m1", "2026-09-01T10:00:00Z", inp=1000000)])
        s.session("s2", [title("#5"), asst("m2", "2026-09-01T10:00:00Z", inp=1000000)])
        _, res = run(self, s)
        cov = E.coverage(res)
        self.assertEqual(cov["totals"]["unattributed"], 2 * 10**9)
        self.assertEqual(cov["totals"]["other_issues"], 2 * 10**9)
        self.assertEqual(cov["totals"]["total"], 4 * 10**9)

    def test_pr_number_resolves_to_issue(self):
        s = Store(self)
        s.session("s1", [title("Merge PR #100 for #9"),
                         asst("m1", "2026-09-01T10:00:00Z")])
        meta = [{"number": 9, "prs": [100], "merged_at": "2026-09-02T00:00:00Z"}]
        _, res = run(self, s, meta)
        self.assertEqual(session_row(res, "s1")["issues"], "9")
        # without the alias the same title is a two-issue session
        _, res = run(self, s, [])
        self.assertEqual(session_row(res, "s1")["issues"], "9 100")


class PrLinkTests(unittest.TestCase):
    META = [{"number": 70, "prs": [71]}]

    def _store(self, repo):
        s = Store(self)
        s.session("s1", [{"type": "pr-link", "prNumber": 71, "prRepository": repo,
                          "prUrl": "https://example.invalid/pull/71"},
                         asst("m1", "2026-09-01T10:00:00Z", inp=1000000)])
        return s

    def test_pr_link_is_last_resort_signal(self):
        s = self._store("o/r")
        scanned = E.scan_store(s.root, ["*"])
        res = E.build(scanned, self.META, pr_repo="o/r")
        row = session_row(res, "s1")
        self.assertEqual((row["signal"], row["issues"]), ("pr", "70"))
        self.assertEqual(res["issues"][70]["total_nano"], 2 * 10**9)

    def test_pr_link_off_without_repo_and_ignores_other_repos(self):
        s = self._store("other/repo")
        scanned = E.scan_store(s.root, ["*"])
        for kw in ({}, {"pr_repo": "o/r"}):
            res = E.build(scanned, self.META, **kw)
            self.assertEqual(session_row(res, "s1")["signal"], "none")

    def test_title_beats_pr_link(self):
        s = Store(self)
        s.session("s1", [title("#5 x"),
                         {"type": "pr-link", "prNumber": 71, "prRepository": "o/r"},
                         asst("m1", "2026-09-01T10:00:00Z", inp=1000000)])
        res = E.build(E.scan_store(s.root, ["*"]), self.META, pr_repo="o/r")
        self.assertEqual(session_row(res, "s1")["signal"], "title")


class MultiIssueTests(unittest.TestCase):
    def test_split_by_turn_branch_else_shared(self):
        s = Store(self)
        s.session("s1", [title("Batch #20 #21"),
                         asst("m1", "2026-09-01T10:00:00Z", branch="issue-20", inp=1000000),
                         asst("m2", "2026-09-01T10:01:00Z", branch="feature/issue-21-x", inp=2000000),
                         asst("m3", "2026-09-01T10:02:00Z", branch="main", inp=4000000)])
        _, res = run(self, s)
        self.assertEqual(res["issues"][20]["total_nano"], 2 * 10**9)
        self.assertEqual(res["issues"][21]["total_nano"], 4 * 10**9)
        self.assertEqual(res["shared"][(20, 21)]["main"], 8 * 10**9)
        # shared cost is exposed per issue but never added into the total
        self.assertEqual(res["issues"][20]["shared_exposure_even_split_nano"], 4 * 10**9)
        self.assertEqual(session_row(res, "s1")["verdict"], "multi")

    def test_multi_branch_session_without_title(self):
        s = Store(self)
        s.session("s1", [asst("m1", "2026-09-01T10:00:00Z", branch="issue-1", inp=1000000),
                         asst("m2", "2026-09-01T10:01:00Z", branch="issue-2", inp=1000000),
                         asst("m3", "2026-09-01T10:02:00Z", branch="main", inp=1000000)])
        _, res = run(self, s)
        self.assertEqual(res["issues"][1]["total_nano"], 2 * 10**9)
        self.assertEqual(res["issues"][2]["total_nano"], 2 * 10**9)
        self.assertEqual(sum(res["shared"][(1, 2)].values()), 2 * 10**9)

    def test_single_branch_session_takes_its_main_turns(self):
        s = Store(self)
        s.session("s1", [asst("m1", "2026-09-01T10:00:00Z", branch="main", inp=1000000),
                         asst("m2", "2026-09-01T10:01:00Z", branch="issue-3", inp=1000000)])
        _, res = run(self, s)
        self.assertEqual(res["issues"][3]["total_nano"], 4 * 10**9)
        self.assertEqual(res["shared"], {})


class SubagentRollupTests(unittest.TestCase):
    def build(self):
        s = Store(self)
        s.session("p1", [title("#30 work"),
                         asst("m1", "2026-09-01T10:00:00Z", inp=1000000)])
        s.subagent("p1", "aaa", [asst("a1", "2026-09-01T10:05:00Z", inp=3000000, branch="main")],
                   agent_type="stress-tester")
        s.subagent("p1", "bbb", [asst("b1", "2026-09-01T10:06:00Z", inp=1000000, branch="main")])
        return s

    def test_subagents_roll_up_into_parent_issue(self):
        _, res = run(self, self.build())
        r = res["issues"][30]
        self.assertEqual(r["total_nano"], 10 * 10**9)  # (1+3+1)M at $2/MTok
        self.assertEqual(r["episode_by_class"]["subagent"], 8 * 10**9)
        self.assertEqual(r["episode_by_class"]["main"], 2 * 10**9)
        self.assertEqual(r["subagent_transcripts"], 2)
        self.assertEqual((r["turns_main"], r["turns_subagent"]), (1, 2))
        self.assertEqual(r["sessions"], 1)

    def test_session_row_includes_subagent_cost(self):
        _, res = run(self, self.build())
        row = session_row(res, "p1")
        self.assertEqual(row["cost_nano"], 10 * 10**9)
        self.assertEqual(row["subagent_files"], 2)

    def test_subagent_with_unattributed_parent_stays_unattributed(self):
        s = Store(self)
        s.session("p2", [asst("m1", "2026-09-01T10:00:00Z", inp=1000000)])
        s.subagent("p2", "ccc", [asst("c1", "2026-09-01T10:01:00Z", inp=1000000)])
        _, res = run(self, s)
        self.assertEqual(res["unattributed"]["subagent"], 2 * 10**9)

    def test_subagent_branch_is_evidence_for_the_parent_session(self):
        s = Store(self)
        s.session("p3", [asst("m1", "2026-09-01T10:00:00Z", inp=1000000, branch="main")])
        s.subagent("p3", "ddd", [asst("d1", "2026-09-01T10:01:00Z", inp=1000000,
                                      branch="feature/issue-40-x")])
        _, res = run(self, s)
        self.assertEqual(res["issues"][40]["total_nano"], 4 * 10**9)


class HookChildTests(unittest.TestCase):
    def test_hook_child_class_and_prompt_rule_ignored(self):
        s = Store(self)
        prompt = E.DEFAULT_HOOK_PROMPT_PREFIX + " ...\nTask: #99 quoted from an excerpt"
        s.session("h1", [user(prompt, entrypoint="sdk-cli"),
                         asst("m1", "2026-09-01T10:00:00Z", model="claude-haiku-4-5-20251001",
                              entrypoint="sdk-cli", branch="issue-50", inp=1000000)])
        s.session("h2", [user(prompt, entrypoint="sdk-cli"),
                         asst("m2", "2026-09-01T10:00:00Z", model="claude-haiku-4-5-20251001",
                              entrypoint="sdk-cli", branch="main", inp=1000000)])
        _, res = run(self, s)
        self.assertEqual(session_row(res, "h1")["class"], "hook_child")
        self.assertEqual(res["issues"][50]["episode_by_class"]["hook_child"], 10**9)
        self.assertEqual(session_row(res, "h2")["verdict"], "unattributed")
        self.assertEqual(res["unattributed"]["hook_child"], 10**9)

    def test_interactive_sdk_session_is_not_a_hook_child(self):
        s = Store(self)
        entries = [user("do real work", entrypoint="sdk-cli")]
        entries += [asst("m%d" % i, "2026-09-01T10:%02d:00Z" % i, entrypoint="sdk-cli")
                    for i in range(6)]
        s.session("x1", entries)
        _, res = run(self, s)
        self.assertNotEqual(session_row(res, "x1")["class"], "hook_child")


class SessionClassTests(unittest.TestCase):
    def test_main_vs_branch(self):
        s = Store(self)
        s.session("m", [asst("m1", "2026-09-01T10:00:00Z", branch="main", inp=1000000)])
        s.session("b", [asst("b1", "2026-09-01T10:00:00Z", branch="issue-7", inp=3000000),
                        asst("b2", "2026-09-01T10:01:00Z", branch="main", inp=1000000)])
        _, res = run(self, s)
        self.assertEqual(session_row(res, "m")["class"], "main")
        self.assertEqual(session_row(res, "b")["class"], "branch")


class DedupTests(unittest.TestCase):
    def test_keep_max_output_whole_record(self):
        s = Store(self)
        s.session("s1", [asst("dup", "2026-09-01T10:00:00Z", out=5, inp=7),
                         asst("dup", "2026-09-01T10:00:02Z", out=50, inp=7)])
        sc, res = run(self, s)
        self.assertEqual(len(sc["best"]), 1)
        rec = sc["best"]["dup"]
        self.assertEqual((rec["output"], rec["input"]), (50, 7))

    def test_cross_session_duplicate_counted_once(self):
        s = Store(self)
        s.session("orig", [asst("same", "2026-09-01T10:00:00Z", inp=1000000)])
        s.session("resumed", [asst("same", "2026-09-01T10:00:00Z", inp=1000000)])
        sc, res = run(self, s)
        self.assertEqual(sum(r["cost_nano"] for r in res["sessions"]), 2 * 10**9)
        self.assertEqual(sc["cross_session_dup_lines"], 1)
        self.assertEqual(session_row(res, "orig")["cost_nano"], 2 * 10**9)


class WindowTests(unittest.TestCase):
    def test_episode_tail_late(self):
        s = Store(self)
        s.session("s1", [title("#60 x"),
                         asst("m1", "2026-09-01T10:00:00Z", inp=1000000),
                         asst("m2", "2026-09-10T10:00:00Z", inp=1000000),
                         asst("m3", "2026-09-20T10:00:00Z", inp=1000000),
                         asst("m4", "2026-11-01T10:00:00Z", inp=1000000)])
        meta = [{"number": 60, "merged_at": "2026-09-05T00:00:00Z"}]
        _, res = run(self, s, meta)
        r = res["issues"][60]
        self.assertEqual((r["episode_nano"], r["tail_nano"], r["late_nano"]),
                         (2 * 10**9, 2 * 10**9, 4 * 10**9))
        self.assertEqual(r["first_ts"], "2026-09-01T10:00:00Z")
        self.assertEqual(r["episode_last_ts"], "2026-09-01T10:00:00Z")

    def test_close_time_used_when_no_merge(self):
        s = Store(self)
        s.session("s1", [title("#61 x"), asst("m1", "2026-09-01T10:00:00Z", inp=1000000),
                         asst("m2", "2026-09-03T10:00:00Z", inp=1000000)])
        meta = [{"number": 61, "closed_at": "2026-09-02T00:00:00Z"}]
        _, res = run(self, s, meta)
        self.assertEqual(res["issues"][61]["end_ts"], "2026-09-02T00:00:00Z")
        self.assertEqual(res["issues"][61]["tail_nano"], 2 * 10**9)


class OutputTests(unittest.TestCase):
    def test_deterministic_and_confined_to_out_dir(self):
        s = Store(self)
        s.session("s1", [title("#70 x"), asst("m1", "2026-09-01T10:00:00Z", inp=1234567)])
        s.subagent("s1", "zzz", [asst("z1", "2026-09-01T10:01:00Z", inp=7654321)])
        s.session("s2", [asst("m2", "2026-09-02T10:00:00Z", inp=999)])
        issues = os.path.join(s.root, "issues.json")
        with open(issues, "w") as fh:
            json.dump([{"number": 70, "merged_at": "2026-09-02T00:00:00Z"}], fh)
        outs = []
        for i in range(2):
            out = os.path.join(s.root, "out%d" % i)
            argv = ["--projects-root", s.root, "--issues", issues, "--out", out,
                    "--coverage-since", "2026-09-01"]
            self.assertEqual(E.main(argv), 0)
            outs.append(out)
        names = sorted(os.listdir(outs[0]))
        self.assertEqual(names, sorted(os.listdir(outs[1])))
        self.assertIn("report.json", names)
        for n in names:
            with open(os.path.join(outs[0], n), "rb") as a, open(os.path.join(outs[1], n), "rb") as b:
                self.assertEqual(a.read(), b.read(), n)

    def test_no_prompt_text_or_titles_in_output(self):
        s = Store(self)
        s.session("s1", [title("#71 SECRETTITLE"), user("SECRETPROMPT Task: #71"),
                         asst("m1", "2026-09-01T10:00:00Z", inp=1000)])
        out = os.path.join(s.root, "out")
        E.main(["--projects-root", s.root, "--out", out])
        for n in os.listdir(out):
            with open(os.path.join(out, n)) as fh:
                body = fh.read()
            self.assertNotIn("SECRET", body, n)


class ReconcileTests(unittest.TestCase):
    def test_rollup_and_unpriced_adjustment(self):
        s = Store(self)
        s.session("p1", [title("#80"), asst("m1", "2026-09-01T10:00:00Z", inp=1000000)])
        s.subagent("p1", "aaa", [asst("a1", "2026-09-01T10:05:00Z", inp=3000000)])
        s.session("p2", [asst("m2", "2026-09-01T10:00:00Z", model="claude-sonnet-5-5", inp=1000000)])
        sc, res = run(self, s)
        cc = {
            "p1": {"totalCost": 8.0, "modelBreakdowns": [
                {"modelName": "claude-sonnet-5", "cost": 8.0, "inputTokens": 4000000,
                 "outputTokens": 0, "cacheCreationTokens": 0, "cacheReadTokens": 0}]},
            "p2": {"totalCost": 0.0, "modelBreakdowns": [
                {"modelName": "claude-sonnet-5-5", "cost": 0.0, "inputTokens": 1000000,
                 "outputTokens": 0, "cacheCreationTokens": 0, "cacheReadTokens": 0}]},
            "other": {"totalCost": 5.0, "modelBreakdowns": []},
        }
        r = E.reconcile(sc, cc, 0.005)
        self.assertEqual(r["sessions_common"], 2)
        self.assertEqual(r["sessions_only_in_ccusage"], 1)
        self.assertEqual(r["ccusage_unpriced_models"], ["sonnet-5-5"])
        self.assertAlmostEqual(r["delta_raw"], 2.0 / 8.0)
        self.assertEqual(r["delta_adjusted"], 0.0)
        self.assertTrue(r["within_tolerance"])
        self.assertEqual(r["rollup"]["sessions_with_subagents"], 1)
        self.assertEqual(r["rollup"]["delta_with_rollup"], 0.0)
        self.assertAlmostEqual(r["rollup"]["delta_main_only"], -0.75)

    def test_nested_subagent_transcripts_are_counted_and_reported(self):
        s = Store(self)
        s.session("p1", [asst("m1", "2026-09-01T10:00:00Z", inp=1000000)])
        s.subagent("p1", "aaa", [asst("a1", "2026-09-01T10:05:00Z", inp=1000000)])
        s.subagent("p1", "bbb", [asst("a2", "2026-09-01T10:06:00Z", inp=1000000)],
                   nested=("workflows", "wf_1"))
        sc, res = run(self, s)
        self.assertEqual(session_row(res, "p1")["cost_nano"], 6 * 10**9)
        # an exporter that skips the nested directory sees only two of the three
        cc = {"p1": {"totalCost": 4.0, "modelBreakdowns": []}}
        r = E.reconcile(sc, cc, 0.005)
        self.assertEqual(r["nested_files"], 1)
        self.assertEqual(r["nested_nano"], 2 * 10**9)
        self.assertEqual(r["delta_without_nested"], 0.0)
        self.assertAlmostEqual(r["delta_raw"], 0.5)


if __name__ == "__main__":
    unittest.main()
