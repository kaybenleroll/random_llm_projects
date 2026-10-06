"""Unit tests for pr_grader. No model calls, no network.

Run from the pr-grader directory:  python3 -m unittest discover -s tests -v
Temporary files go under $PR_GRADER_TMP if set, else the system temp directory.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import pr_grader as pg  # noqa: E402

SCHEMA_DIR = HERE.parent / "schemas"
REVIEW_SCHEMA = json.loads((SCHEMA_DIR / "review.schema.json").read_text())
VERIFY_SCHEMA = json.loads((SCHEMA_DIR / "verification.schema.json").read_text())


def tmpdir():
    return tempfile.TemporaryDirectory(dir=os.environ.get("PR_GRADER_TMP"))


def run_git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid",
               GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def write(repo, rel, text):
    p = Path(repo) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def make_fixture_repo(root):
    """Base commit, then a squash-style commit touching code plus process files."""
    repo = Path(root) / "fixture"
    repo.mkdir()
    run_git(repo, "init", "-q", "-b", "main")
    write(repo, "src/app.py", "def f(x):\n    return x\n")
    write(repo, "README.md", "hello\n")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "base")
    write(repo, "src/app.py", "def f(x):\n    return x + 1\n")
    write(repo, "src/app_test.py", "assert True\n")
    write(repo, "CLAUDE.md", "process rules\n")
    write(repo, "sub/AGENTS.md", "agents\n")
    write(repo, ".claude/rules/r.md", "rule\n")
    write(repo, ".github/workflows/ci.yml", "on: push\n")
    write(repo, "docs/plans/2026-01-01-plan-12-thing.md", "the plan for the thing\n")
    write(repo, "planning/archive/old.md", "old\n")
    write(repo, ".env", "SECRET=1\n")
    write(repo, ".env.example", "SECRET=\n")
    write(repo, "docs/guide.md", "a guide\n")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "Fix thing (#99)\n\nCo-Authored-By: someone\nClaude-Session: x")
    return repo


class StripTests(unittest.TestCase):
    def test_is_stripped(self):
        for p in [".claude/x", "a/.claude/settings.local.json", "CLAUDE.md", "pkg/AGENTS.md",
                  ".github/workflows/a.yml", "docs/plans/x.md", "planning/archive/a.md",
                  ".env", ".env.local", "x/.scratch/n.md", ".mcp.json", "skills-lock.json"]:
            self.assertTrue(pg.is_stripped(p), p)
        for p in ["src/app.py", "docs/guide.md", ".env.example", "docs/planning_notes.md",
                  "packages/planning-ui/a.ts", "a/plans_of_care.py", "docs/plan.md"]:
            self.assertFalse(pg.is_stripped(p), p)

    def test_extra_prefix(self):
        self.assertTrue(pg.is_stripped("docs/templates/a.md", ("docs/templates",)))
        self.assertFalse(pg.is_stripped("docs/templates2/a.md", ("docs/templates",)))

    def test_filter_diff_drops_plan_blocks(self):
        diff = (
            "diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n@@ -1 +1 @@\n-x\n+y\n"
            "diff --git a/docs/plans/p.md b/docs/plans/p.md\nnew file mode 100644\n+++ b/docs/plans/p.md\n+plan\n"
            "diff --git a/CLAUDE.md b/CLAUDE.md\n+++ b/CLAUDE.md\n+rules\n"
            "diff --git a/b.py b/b.py\n+++ b/b.py\n+z\n"
        )
        out, dropped = pg.filter_diff(diff)
        self.assertIn("src/a.py", out)
        self.assertIn("b.py", out)
        self.assertNotIn("plan", out)
        self.assertNotIn("CLAUDE", out)
        self.assertEqual(sorted(dropped), ["CLAUDE.md", "docs/plans/p.md"])

    def test_issue_md_only_title_body_and_redacts_paths(self):
        text, n = pg.build_issue_md(
            "Title here", "Body.\n\nPart of the programme; see .scratch/agent-eval-final.md (2026-09-25)\n"
            "Also docs/plans/2026-10-01-plan-1.md and planning/archive/x.md.")
        self.assertTrue(text.startswith("# Title here\n\nBody."))
        self.assertNotIn(".scratch", text)
        self.assertNotIn("docs/plans", text)
        self.assertNotIn("planning/archive", text)
        self.assertEqual(n, 3)
        self.assertIn("[path removed]", text)


class StageTests(unittest.TestCase):
    def test_stage_inputs(self):
        with tmpdir() as t:
            repo = make_fixture_repo(t)
            sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True,
                                 text=True).stdout.strip()
            stage = Path(t) / "stage" / "abc"
            m = pg.stage_inputs(repo, sha, "Fix thing", "Make f add one.", stage)
            files = {f["path"] for f in m["files"]}
            self.assertIn("after/src/app.py", files)
            self.assertIn("after/src/app_test.py", files)
            self.assertIn("after/docs/guide.md", files)
            self.assertIn("after/.env.example", files)
            self.assertIn("diff.patch", files)
            self.assertIn("issue.md", files)
            for banned in ["CLAUDE.md", "AGENTS.md", ".claude", ".github", "plans", "planning", ".env\n"]:
                self.assertFalse(any(banned in f for f in files if f != "after/.env.example"), banned)
            self.assertNotIn("after/.env", files)
            self.assertEqual(m["tree"]["stripped_files"], 7)
            diff = (stage / "diff.patch").read_text()
            self.assertIn("src/app.py", diff)
            self.assertNotIn("plan", diff)
            self.assertNotIn("CLAUDE", diff)
            self.assertNotIn("Co-Authored-By", diff)
            self.assertEqual(m["first_parent"],
                             subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD^"],
                                            capture_output=True, text=True).stdout.strip())
            self.assertEqual((stage / "issue.md").read_text(), "# Fix thing\n\nMake f add one.\n")
            # read-only
            self.assertFalse(os.access(stage / "after/src/app.py", os.W_OK))
            # source repo untouched (no new refs, clean status)
            st = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                                capture_output=True, text=True).stdout
            self.assertEqual(st, "")
            pg.make_tree_writable(stage)

    def test_restage_replaces_readonly_tree(self):
        with tmpdir() as t:
            repo = make_fixture_repo(t)
            stage = Path(t) / "stage" / "abc"
            pg.stage_inputs(repo, "HEAD", "T", "B", stage)
            pg.stage_inputs(repo, "HEAD", "T", "B", stage)
            self.assertTrue((stage / "issue.md").exists())
            pg.make_tree_writable(stage)

    def test_no_first_parent_fails(self):
        with tmpdir() as t:
            repo = make_fixture_repo(t)
            root = subprocess.run(["git", "-C", str(repo), "rev-list", "--max-parents=0", "HEAD"],
                                  capture_output=True, text=True).stdout.strip()
            with self.assertRaises(RuntimeError):
                pg.stage_inputs(repo, root, "T", "B", Path(t) / "s")


class ScanTests(unittest.TestCase):
    def stage_with(self, t, issue="# T\n\nbody\n", diff="diff --git a/a b/a\n+x\n", tree=None):
        s = Path(t) / "stage"
        (s / "after/src").mkdir(parents=True)
        (s / "issue.md").write_text(issue)
        (s / "diff.patch").write_text(diff)
        for rel, text in (tree or {"src/a.py": "x = 1\n"}).items():
            write(s / "after", rel, text)
        return s

    def test_clean_stage_passes(self):
        with tmpdir() as t:
            s = self.stage_with(t)
            r = pg.scan_blinding(s, pr_number=4742, leak_terms=["issue-4525-branch"])
            self.assertTrue(r["ok"], r)

    def test_hard_leaks_in_authored_content_fail(self):
        with tmpdir() as t:
            s = self.stage_with(
                t, diff="diff --git a/a b/a\n+# see PR 4742\n+Co-Authored-By: x\n+Claude-Session: y\n"
                        "+branch issue-4525-branch\n")
            r = pg.scan_blinding(s, pr_number=4742, leak_terms=["issue-4525-branch"])
            terms = {h["term"] for h in r["hard"]}
            self.assertEqual(terms, {"pr-number", "co-authored-by", "claude-session",
                                     "leak:issue-4525-branch"})
            self.assertFalse(r["ok"])
        with tmpdir() as t:
            s = self.stage_with(t, issue="# T\n\nbranch issue-4525-branch, PR 4742\n")
            r = pg.scan_blinding(s, pr_number=4742, leak_terms=["issue-4525-branch"])
            self.assertFalse(r["ok"])
            self.assertEqual({h["file"] for h in r["hard"]}, {"issue.md"})

    def test_hard_hits_in_ambient_tree_are_recorded_not_failed(self):
        with tmpdir() as t:
            s = self.stage_with(t, tree={"src/a.py": "x = 147421\ny = 4742\n",
                                         "doc.md": "Never add Co-Authored-By lines\n"})
            r = pg.scan_blinding(s, pr_number=4742)
            self.assertTrue(r["ok"])
            self.assertEqual(r["hard"], [])
            self.assertEqual(r["ambient_tree_hits"]["hard:pr-number"]["hits"], 1)
            self.assertEqual(r["ambient_tree_hits"]["hard:co-authored-by"]["files"], {"after/doc.md": 1})

    def test_pr_number_is_not_matched_inside_longer_numbers(self):
        with tmpdir() as t:
            s = self.stage_with(t, issue="# T\n\nx = 147421\ny = 4742\n")
            r = pg.scan_blinding(s, pr_number=4742)
            self.assertEqual([h["line"] for h in r["hard"]], [4])

    def test_arm_terms_in_issue_or_added_diff_lines_fail_but_tree_only_records(self):
        with tmpdir() as t:
            s = self.stage_with(t, issue="# T\n\nran the stress-test first\n",
                                tree={"src/a.py": "# orchestrator plan\n"})
            r = pg.scan_blinding(s)
            self.assertFalse(r["ok"])
            self.assertEqual({h["term"] for h in r["arm_fail"]}, {"stress-test"})
            self.assertEqual({k for k in r["ambient_tree_hits"] if k.startswith("arm:")},
                             {"arm:orchestrat", "arm:plan"})
        with tmpdir() as t:
            s = self.stage_with(t, tree={"src/a.py": "# orchestrator plan\n"})
            r = pg.scan_blinding(s)
            self.assertTrue(r["ok"])
            self.assertEqual(r["ambient_tree_hits"]["arm:plan"]["hits"], 1)
        with tmpdir() as t:
            diff = ("diff --git a/a b/a\n--- a/a\n+++ b/a\n"
                    " # plan context line\n-# plan removed line\n+# fine\n")
            self.assertTrue(pg.scan_blinding(self.stage_with(t, diff=diff))["ok"])
        with tmpdir() as t:
            diff = "diff --git a/a b/a\n--- a/a\n+++ b/a\n+# plan: stage one\n"
            r = pg.scan_blinding(self.stage_with(t, diff=diff))
            self.assertFalse(r["ok"])
            self.assertEqual(r["arm_fail"][0]["file"], "diff.patch")

    def test_prompts_are_scanned(self):
        with tmpdir() as t:
            s = self.stage_with(t)
            r = pg.scan_blinding(s, extra_texts={"reviewer_system": "use the check-acs flow"})
            self.assertFalse(r["ok"])
            self.assertEqual(r["arm_fail"][0]["file"], "<prompt>reviewer_system")

    def test_path_names_in_diff_are_scanned(self):
        with tmpdir() as t:
            s = self.stage_with(t, diff="diff --git a/src/issue-4525-branch.py b/src/issue-4525-branch.py\n+x\n")
            r = pg.scan_blinding(s, leak_terms=["issue-4525-branch"])
            self.assertTrue(r["hard"])


    def test_shipped_prompts_pass_the_scan(self):
        prompts = pg.load_prompts()
        with tmpdir() as t:
            s = self.stage_with(t)
            texts = {k: v for k, v in prompts.items() if isinstance(v, str)}
            r = pg.scan_blinding(s, extra_texts=texts)
            self.assertTrue(r["ok"], r)


def good_review(**over):
    r = {
        "acs": [{"id": "AC1", "text": "does a", "status": "met", "evidence": "a.py:3"},
                {"id": "AC2", "text": "does b", "status": "not_assessable", "evidence": "needs a run"}],
        "findings": [
            {"id": "F1", "severity": "major", "file": "src/a.py", "line": 10, "title": "t",
             "description": "d", "evidence": "e", "verifiable_by_inspection": True},
            {"id": "F2", "severity": "minor", "file": "src/b.py", "line": 2, "title": "t",
             "description": "d", "evidence": "e", "verifiable_by_inspection": True}],
        "unrequested_scope": [],
        "test_adequacy": {"rating": "adequate", "rationale": "ok"},
        "grade": 4, "grade_rationale": "one major",
    }
    r.update(over)
    return r


def verdict(v="confirmed", sev="major", ne=False):
    return {"verdict": v, "confirmed_severity": sev, "needs_execution": ne,
            "reasoning": "r", "evidence": "e"}


class SchemaTests(unittest.TestCase):
    def test_good_review_validates(self):
        self.assertEqual(pg.validate(good_review(), REVIEW_SCHEMA), [])

    def test_bad_reviews(self):
        bad = good_review()
        del bad["grade"]
        self.assertTrue(any("missing required 'grade'" in e for e in pg.validate(bad, REVIEW_SCHEMA)))
        bad = good_review(grade=6)
        self.assertTrue(pg.validate(bad, REVIEW_SCHEMA))
        bad = good_review(grade=True)
        self.assertTrue(pg.validate(bad, REVIEW_SCHEMA))
        bad = good_review()
        bad["findings"][0]["severity"] = "critical"
        self.assertTrue(any("not in" in e for e in pg.validate(bad, REVIEW_SCHEMA)))
        bad = good_review()
        bad["findings"][0]["line"] = "10"
        self.assertTrue(any("expected integer" in e for e in pg.validate(bad, REVIEW_SCHEMA)))
        bad = good_review()
        bad["findings"][0]["verifiable_by_inspection"] = "yes"
        self.assertTrue(pg.validate(bad, REVIEW_SCHEMA))
        bad = good_review()
        bad["extra"] = 1
        self.assertTrue(any("unexpected property" in e for e in pg.validate(bad, REVIEW_SCHEMA)))
        bad = good_review()
        bad["findings"][0]["line"] = 0
        self.assertTrue(pg.validate(bad, REVIEW_SCHEMA))

    def test_verification_schema(self):
        self.assertEqual(pg.validate(verdict(), VERIFY_SCHEMA), [])
        self.assertTrue(pg.validate(verdict("maybe"), VERIFY_SCHEMA))
        v = verdict()
        del v["reasoning"]
        self.assertTrue(pg.validate(v, VERIFY_SCHEMA))

    def test_extract_json_object(self):
        obj = {"a": 1}
        self.assertEqual(pg.extract_json_object('{"a": 1}'), obj)
        self.assertEqual(pg.extract_json_object('```json\n{"a": 1}\n```'), obj)
        self.assertEqual(pg.extract_json_object('Here you go: {"a": 1} done'), obj)
        self.assertEqual(pg.extract_json_object('{bad} {"a": 1}'), obj)
        self.assertIsNone(pg.extract_json_object("no json here"))
        self.assertIsNone(pg.extract_json_object('{"a": 1'))
        self.assertIsNone(pg.extract_json_object(None))


class GradeTests(unittest.TestCase):
    def grade(self, ac=("met",), blocker=0, major=0, tests="adequate", scope=()):
        return pg.compute_grade(ac, {"blocker": blocker, "major": major, "minor": 9}, tests, scope)

    def test_anchors(self):
        self.assertEqual(self.grade(), 5)
        self.assertEqual(self.grade(ac=("met", "not_assessable")), 5)
        self.assertEqual(self.grade(ac=()), 5)
        self.assertEqual(self.grade(major=1), 4)
        self.assertEqual(self.grade(tests="partial"), 4)
        self.assertEqual(self.grade(scope=("minor", "significant")), 4)
        self.assertEqual(self.grade(scope=("minor",)), 5)
        self.assertEqual(self.grade(major=2), 3)
        self.assertEqual(self.grade(ac=("met", "partial")), 3)
        self.assertEqual(self.grade(tests="inadequate"), 3)
        self.assertEqual(self.grade(major=3), 2)
        self.assertEqual(self.grade(major=7), 2)
        self.assertEqual(self.grade(ac=("partial", "partial")), 2)
        self.assertEqual(self.grade(blocker=1), 1)
        self.assertEqual(self.grade(ac=("met", "not_met")), 1)
        self.assertEqual(self.grade(blocker=1, major=5, tests="inadequate"), 1)

    def test_apply_verification_discards_unverified(self):
        review = good_review()
        review["findings"].append({"id": "F3", "severity": "blocker", "file": "x", "line": 1,
                                   "title": "t", "description": "d", "evidence": "e",
                                   "verifiable_by_inspection": False})
        review["findings"].append({"id": "F4", "severity": "major", "file": "x", "line": 1,
                                   "title": "t", "description": "d", "evidence": "e",
                                   "verifiable_by_inspection": True})
        review["grade"] = 1
        v = {"finding:F1": verdict("confirmed", "major"),
             "finding:F3": verdict("unverifiable", "not_applicable", ne=True),
             "finding:F4": verdict("refuted", "not_a_defect")}
        out = pg.apply_verification(review, v)
        self.assertEqual(out["verified"], {"blocker": 0, "major": 1, "minor": 0})
        self.assertEqual(out["reported_minor"], 1)
        self.assertEqual(out["grade"], 4)
        self.assertEqual(out["reviewer_reported_grade"], 1)
        reasons = {d["id"]: d["reason"] for d in out["discarded"]}
        self.assertEqual(reasons, {"F3": "unverifiable_needs_execution", "F4": "refuted"})

    def test_downgrade_on_confirmation_and_missing_verification(self):
        review = good_review()
        out = pg.apply_verification(review, {"finding:F1": verdict("confirmed", "minor")})
        self.assertEqual(out["verified"], {"blocker": 0, "major": 0, "minor": 1})
        self.assertEqual(out["grade"], 5)
        out = pg.apply_verification(review, {})
        self.assertEqual(out["discarded"][0]["reason"], "not_verified")
        out = pg.apply_verification(review, {"finding:F1": verdict("confirmed", "not_a_defect")})
        self.assertEqual(out["discarded"][0]["reason"], "confirmed_as_not_a_defect")

    def test_ac_claims_are_verified(self):
        review = good_review()
        review["acs"][0]["status"] = "not_met"
        review["findings"] = []
        n = pg.apply_verification(review, {"ac:AC1": verdict("confirmed", "not_applicable")})
        self.assertEqual((n["grade"], n["ac_statuses"][0]), (1, "not_met"))
        n = pg.apply_verification(review, {"ac:AC1": verdict("refuted", "not_applicable")})
        self.assertEqual((n["grade"], n["ac_statuses"][0]), (5, "met"))
        n = pg.apply_verification(review, {"ac:AC1": verdict("unverifiable", "not_applicable", ne=True)})
        self.assertEqual((n["grade"], n["ac_statuses"][0]), (5, "not_assessable"))
        n = pg.apply_verification(review, {})
        self.assertEqual(n["ac_statuses"][0], "not_assessable")

    def test_claims_to_verify_order_and_cap(self):
        review = good_review()
        review["acs"][1]["status"] = "partial"
        review["acs"].append({"id": "AC3", "text": "c", "status": "not_met", "evidence": "e"})
        review["findings"].append({"id": "F3", "severity": "blocker", "file": "x", "line": 1,
                                   "title": "t", "description": "d", "evidence": "e",
                                   "verifiable_by_inspection": True})
        keys = [k for k, _ in pg.claims_to_verify(review, 10)]
        self.assertEqual(keys, ["finding:F3", "ac:AC3", "finding:F1", "ac:AC2"])
        self.assertEqual([k for k, _ in pg.claims_to_verify(review, 2)], ["finding:F3", "ac:AC3"])
        body = dict(pg.claims_to_verify(review, 10))["finding:F1"]
        self.assertNotIn("reviewer", json.dumps(body).lower())
        self.assertNotIn("grade", body)

    def test_median_and_aggregate(self):
        mk = lambda g, met=2, tot=2: {  # noqa: E731
            "grade": g, "reviewer_reported_grade": g, "verified": {"blocker": 0, "major": 0, "minor": 0},
            "reported_minor": 0, "discarded": [], "acs_met": met, "acs_total": tot}
        a = pg.aggregate([mk(5), mk(3), mk(4)])
        self.assertEqual(a["grade"], 4)
        self.assertEqual(a["per_reviewer_grades"], [5, 3, 4])
        a = pg.aggregate([mk(5), None, mk(3)])
        self.assertEqual((a["grade"], a["n_valid_reviewers"]), (4, 2))
        a = pg.aggregate([mk(5), mk(2), None])
        self.assertEqual(a["grade"], 3.5)
        a = pg.aggregate([None, None, None])
        self.assertIsNone(a["grade"])
        self.assertEqual(pg.median_grade([1, 5, 5]), 5)


class RunnerTests(unittest.TestCase):
    def test_argv_is_read_only_and_isolated(self):
        argv = pg.build_argv("/x/claude", "opus", "high", "SYS", Path("/stage/abc"), 15.0)
        joined = " ".join(argv)
        self.assertEqual(argv[0], "/x/claude")
        for flag in ["-p", "--no-session-persistence", "--disable-slash-commands", "--restricted",
                     "--strict-mcp-config", "--add-dir", "--output-format"]:
            self.assertIn(flag, argv)
        self.assertEqual(argv[argv.index("--tools") + 1], "Read,Grep,Glob")
        self.assertEqual(argv[argv.index("--model") + 1], "opus")
        self.assertNotIn("Bash", joined)
        self.assertNotIn("--dangerously-skip-permissions", argv)
        settings = json.loads(argv[argv.index("--settings") + 1])
        self.assertTrue(settings["disableAllHooks"])
        self.assertFalse(settings["autoMemoryEnabled"])
        self.assertEqual(argv[argv.index("--add-dir") + 1], "/stage/abc")
        self.assertEqual(pg.child_env()["CLAUDE_CODE_DISABLE_AUTO_MEMORY"], "1")

    def test_parse_cli_json_and_usage(self):
        ev = {"type": "result", "result": "{}", "total_cost_usd": 1.5, "num_turns": 3,
              "usage": {"input_tokens": 10, "cache_creation_input_tokens": 20,
                        "cache_read_input_tokens": 30, "output_tokens": 40},
              "modelUsage": {"claude-opus-x": {}}}
        for payload in (json.dumps([{"type": "system"}, ev]), json.dumps(ev)):
            got = pg.parse_cli_json(payload)
            self.assertEqual(got["total_cost_usd"], 1.5)
        self.assertIsNone(pg.parse_cli_json("not json"))
        self.assertIsNone(pg.parse_cli_json(json.dumps([{"type": "system"}])))
        u = pg.usage_of(ev)
        total = pg.add_usage(pg.add_usage({}, u), u)
        self.assertEqual((total["input_tokens"], total["output_tokens"], total["total_cost_usd"]),
                         (20, 80, 3.0))
        self.assertEqual(total["models"], ["claude-opus-x"])

    def test_fill_and_prompts_load(self):
        p = pg.load_prompts()
        self.assertIn("Grade anchors", p["reviewer_system"])
        self.assertNotIn("{{", p["reviewer_system"])
        self.assertNotIn("{{", p["verifier_system"])
        self.assertIn("{{CLAIM_JSON}}", p["verifier_task"])
        self.assertEqual(pg.fill("a {{X}} b", X="1"), "a 1 b")

    def test_table_row_and_render(self):
        mk = lambda g, maj: {  # noqa: E731
            "grade": g, "reviewer_reported_grade": g + 1 if g < 5 else 5,
            "verified": {"blocker": 0, "major": maj, "minor": 1}, "reported_minor": 2,
            "discarded": [{"id": "F9", "severity": "major", "reason": "refuted"}],
            "acs_met": 3, "acs_total": 4}
        per = [mk(4, 1), None, mk(5, 0)]
        result = {"label": "L", "issue": 7, "merge_sha": "a" * 40, "model_alias": "opus",
                  "cli_version": "9.9", "graded_at": "t", "per_reviewer": per,
                  "aggregate": pg.aggregate(per)}
        row = pg.table_row(result)
        self.assertEqual(row["grade"], 4.5)
        self.assertEqual(row["reviewer_grades"], "4|-|5")
        self.assertEqual(row["verified_major"], "1|-|0")
        self.assertEqual(row["verified_minor_reported"], "3|-|3")
        self.assertEqual(row["discarded_blocker_major"], "1|-|1")
        self.assertEqual(row["acs_met"], "3/4|-|3/4")
        md = pg.render_markdown([row])
        self.assertEqual(md.count("\n"), 3)
        self.assertEqual(set(row), set(pg.TABLE_COLUMNS))

    def test_execute_role_rejects_nonempty_cwd(self):
        with tmpdir() as t:
            cwd = Path(t) / "cwd"
            cwd.mkdir()
            (cwd / "stray").write_text("x")
            stage = Path(t) / "stage"
            stage.mkdir()
            ctx = {"resume": False, "claude": "/nonexistent/claude", "model": "opus", "effort": "high",
                   "stage_dir": stage, "max_budget_usd": 1, "cwd": cwd, "timeout": 5,
                   "manifest_file_count": 0, "manifest_sha256": "0"}
            with self.assertRaises(RuntimeError):
                pg.execute_role("reviewer:1", Path(t) / "run", ctx, "S", "U", REVIEW_SCHEMA)


if __name__ == "__main__":
    unittest.main()
