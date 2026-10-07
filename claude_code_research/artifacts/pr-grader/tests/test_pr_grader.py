"""Unit tests for pr_grader. No model calls (a fake `claude` executable stands in), no network.

Run from anywhere:  python3 -I /abs/path/to/pr-grader/tests/test_pr_grader.py
Temporary files go under $PR_GRADER_TMP if set, else the system temp directory.
"""
import getpass
import json
import os
import re
import shutil
import stat
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

    def test_strip_list_patterns(self):
        pats = pg.parse_strip_list(
            "# comment\n\ndocs/dev/workflow-guide.md  # trailing note\nWORKFLOW.md\n"
            "data/token-analysis/**\n**/skills-*.md\n")
        self.assertEqual(pats, ["docs/dev/workflow-guide.md", "WORKFLOW.md", "data/token-analysis/**",
                                "**/skills-*.md"])
        for p in ["docs/dev/workflow-guide.md", "WORKFLOW.md", "data/token-analysis/a.csv",
                  "data/token-analysis/sub/b.csv", "skills-x.md", "a/b/skills-ref.md"]:
            self.assertTrue(pg.is_stripped(p, pats), p)
        for p in ["docs/dev/workflow-guide.md.bak", "docs/WORKFLOW.md", "data/token-analysis2/a.csv",
                  "data/other.csv", "a/skills.md", "src/app.py"]:
            self.assertFalse(pg.is_stripped(p, pats), p)

    def test_poc_example_strip_list_ships_and_parses(self):
        pats = pg.load_strip_list(HERE.parent / "strip-list.example.txt")
        for need in ["docs/developer-guide/workflow-guide.md", "docs/developer-guide/skills-reference.md",
                     "DEVELOPMENT_WORKFLOW.md", "GETTING_STARTED.md", "NEWDEV_GUIDE.md",
                     "docs/operations/token-usage-analysis.md", "devtools/data/token-analysis/**"]:
            self.assertIn(need, pats)
        self.assertTrue(pg.is_stripped("devtools/data/token-analysis/token_analysis_raw.csv", pats))

    def test_strip_list_applies_to_tree_diff_and_reports_unmatched(self):
        with tmpdir() as t:
            repo = make_fixture_repo(t)
            stage = Path(t) / "stage"
            m = pg.stage_inputs(repo, "HEAD", "T", "B", stage, ("docs/guide.md", "nope/**"))
            files = {f["path"] for f in m["files"]}
            self.assertNotIn("after/docs/guide.md", files)
            self.assertEqual(m["tree"]["strip_patterns_unmatched"], ["nope/**"])
            self.assertEqual(m["tree"]["strip_pattern_matches"]["docs/guide.md"], 1)
            self.assertNotIn("docs/guide.md", (stage / "diff.patch").read_text())
            pg.make_tree_writable(stage)

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

    def test_strict_leaks_in_authored_content_fail(self):
        with tmpdir() as t:
            s = self.stage_with(
                t, diff="diff --git a/a b/a\n+# see PR 4742\n+Co-Authored-By: x\n+Claude-Session: y\n"
                        "+branch issue-4525-branch\n")
            r = pg.scan_blinding(s, pr_number=4742, leak_terms=["issue-4525-branch"])
            terms = {h["term"] for h in r["strict_fail"]}
            self.assertEqual(terms, {"pr-number", "co-authored-by", "claude-session",
                                     "leak:issue-4525-branch"})
            self.assertFalse(r["ok"])
        with tmpdir() as t:
            s = self.stage_with(t, issue="# T\n\nbranch issue-4525-branch, PR 4742\n")
            r = pg.scan_blinding(s, pr_number=4742, leak_terms=["issue-4525-branch"])
            self.assertFalse(r["ok"])
            self.assertEqual({h["file"] for h in r["strict_fail"]}, {"issue.md"})

    def test_strict_terms_check_added_diff_lines_and_prompts(self):
        strict_lines = ["see check-acs output", "wrote .scratch/notes.md", "see handover-2026.md",
                        "docs/plans/2026-01-01-x.md", "via superpowers"]
        for line in strict_lines:
            with tmpdir() as t:
                s = self.stage_with(t, issue=f"# T\n\n{line}\n")
                self.assertFalse(pg.scan_blinding(s)["ok"], line)
            with tmpdir() as t:
                diff = f"diff --git a/a b/a\n--- a/a\n+++ b/a\n+{line}\n"
                self.assertFalse(pg.scan_blinding(self.stage_with(t, diff=diff))["ok"], line)
            with tmpdir() as t:  # context and removed lines of a diff are not authored by the change
                diff = f"diff --git a/a b/a\n--- a/a\n+++ b/a\n {line}\n-{line}\n+fine\n"
                self.assertTrue(pg.scan_blinding(self.stage_with(t, diff=diff))["ok"], line)
        with tmpdir() as t:
            s = self.stage_with(t)
            r = pg.scan_blinding(s, extra_texts={"reviewer_system": "use the check-acs flow"})
            self.assertFalse(r["ok"])
            self.assertEqual(r["strict_fail"][0]["file"], "<prompt>reviewer_system")

    def test_domain_ambiguous_terms_warn_count_but_never_abort(self):
        with tmpdir() as t:
            s = self.stage_with(
                t, issue="# T\n\nwe plan to stress-test the orchestrator; a subagent helps\n",
                diff="diff --git a/a b/a\n--- a/a\n+++ b/a\n+# plan: stage one\n",
                tree={"src/a.py": "# orchestrator plan\n# see CLAUDE.md\n"})
            r = pg.scan_blinding(s, extra_texts={"x": "an action plan"})
            self.assertTrue(r["ok"], r)
            self.assertEqual(r["strict_fail"], [])
            by = r["counts"]["warn_authored_by_term"]
            self.assertEqual(by["stress-test"], 1)
            self.assertEqual(by["subagent"], 1)
            self.assertEqual(by["orchestrat"], 1)
            self.assertEqual(by["plan"], 3)  # issue, added diff line, prompt
            amb = r["counts"]["ambient_domain_ambiguous_by_term"]
            self.assertEqual((amb["plan"], amb["orchestrat"], amb["claude.md"]), (1, 1, 1))
            self.assertEqual(r["counts"]["ambient_strict"], 0)

    def test_ambient_strict_hits_are_counted_not_failed_unless_limited(self):
        tree = {"doc.md": "Never add Co-Authored-By lines\nrun in .scratch/\n", "src/a.py": "x = 4742\n"}
        with tmpdir() as t:
            s = self.stage_with(t, tree=tree)
            r = pg.scan_blinding(s, pr_number=4742)
            self.assertTrue(r["ok"], r)  # a bare number in unchanged code is ambient
            self.assertEqual(r["counts"]["ambient_strict_by_term"], {"co-authored-by": 1, "scratch": 1})
            self.assertEqual(r["ambient"]["strict"]["co-authored-by"]["files"], {"after/doc.md": 1})
            r = pg.scan_blinding(s, pr_number=4742, max_ambient_strict=1)
            self.assertFalse(r["ok"])
            self.assertTrue(r["ambient_strict_over_limit"])
            self.assertTrue(pg.scan_blinding(s, pr_number=4742, max_ambient_strict=2)["ok"])

    def test_change_specific_identifiers_abort_even_in_the_tree(self):
        for text in ["fixed in #4742\n", "see PR 4742 for details\n", "pull/4742\n", "branch issue-4525-x\n"]:
            with tmpdir() as t:
                s = self.stage_with(t, tree={"doc.md": text})
                r = pg.scan_blinding(s, pr_number=4742, leak_terms=["issue-4525-x"])
                self.assertFalse(r["ok"], text)

    def test_handover_and_plan_path_names_abort_in_tree(self):
        for rel in ["notes/handover-2026-10-01.md", "docs/handover.md"]:
            with tmpdir() as t:
                s = self.stage_with(t, tree={rel: "x\n"})
                r = pg.scan_blinding(s)
                self.assertFalse(r["ok"], rel)
                self.assertTrue({h["term"] for h in r["strict_fail"]} & {"handover-file", "handover-filename"})

    def test_pr_number_is_not_matched_inside_longer_numbers(self):
        with tmpdir() as t:
            s = self.stage_with(t, issue="# T\n\nx = 147421\ny = 4742\n")
            r = pg.scan_blinding(s, pr_number=4742)
            self.assertEqual([h["line"] for h in r["strict_fail"]], [4])

    def test_path_names_in_diff_are_scanned(self):
        with tmpdir() as t:
            s = self.stage_with(t, diff="diff --git a/src/issue-4525-branch.py b/src/issue-4525-branch.py\n+x\n")
            r = pg.scan_blinding(s, leak_terms=["issue-4525-branch"])
            self.assertTrue(r["strict_fail"])

    def test_shipped_prompts_pass_the_scan(self):
        prompts = pg.load_prompts()
        with tmpdir() as t:
            s = self.stage_with(t)
            texts = {k: v for k, v in prompts.items() if isinstance(v, str)}
            r = pg.scan_blinding(s, extra_texts=texts)
            self.assertTrue(r["ok"], r["strict_fail"])


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
        "grade": 4, "grade_rationale": "one major", "assessable_fraction": 0.5,
    }
    r.update(over)
    return r


def strong_review(**over):
    """Five assessable ACs, all met; one major finding F1; adequate tests."""
    r = good_review(**over)
    r["acs"] = [{"id": f"AC{i}", "text": "t", "status": "met", "evidence": "e"} for i in range(1, 6)]
    r["assessable_fraction"] = 1.0
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
    def grade(self, ac=("met",) * 5, blocker=0, major=0, tests="adequate", scope=(), unresolved=0):
        return pg.compute_grade(ac, {"blocker": blocker, "major": major, "minor": 9}, tests, scope,
                                unresolved)

    def test_anchors(self):
        self.assertEqual(self.grade(), 5)
        self.assertEqual(self.grade(ac=("met", "met", "met", "met", "not_assessable")), 5)  # 0.8
        self.assertEqual(self.grade(major=1), 4)
        self.assertEqual(self.grade(tests="partial"), 4)
        self.assertEqual(self.grade(scope=("minor", "significant")), 4)
        self.assertEqual(self.grade(scope=("minor",)), 5)
        self.assertEqual(self.grade(major=2), 3)
        self.assertEqual(self.grade(ac=("met",) * 4 + ("partial",)), 3)
        self.assertEqual(self.grade(tests="inadequate"), 3)
        self.assertEqual(self.grade(major=3), 2)
        self.assertEqual(self.grade(major=7), 2)
        self.assertEqual(self.grade(ac=("met", "met", "met", "partial", "partial")), 2)

    def test_intermediate_rules_replace_the_cliff(self):
        met = ("met",) * 5
        # one not_met AC, no blocker: 3 (was 1)
        self.assertEqual(self.grade(ac=met[:4] + ("not_met",)), 3)
        # two not_met, no blocker: 2; three or more: 1
        self.assertEqual(self.grade(ac=met[:3] + ("not_met",) * 2), 2)
        self.assertEqual(self.grade(ac=met[:2] + ("not_met",) * 3), 1)
        # one blocker alone: 2 (was 1); two blockers: 1
        self.assertEqual(self.grade(blocker=1), 2)
        self.assertEqual(self.grade(blocker=2), 1)
        # blocker plus a not_met AC: the issue is not delivered: 1
        self.assertEqual(self.grade(blocker=1, ac=met[:4] + ("not_met",)), 1)
        # the minimum of all caps applies
        self.assertEqual(self.grade(ac=met[:4] + ("not_met",), major=3), 2)
        self.assertEqual(self.grade(blocker=1, major=5, tests="inadequate"), 2)

    def test_assessable_fraction_caps_at_four_and_flags(self):
        self.assertEqual(pg.assessable_fraction(["met", "not_assessable"]), 0.5)
        self.assertEqual(pg.assessable_fraction([]), 0.0)
        d = pg.grade_details(("met", "not_assessable"), {}, "adequate", ())
        self.assertEqual((d["grade"], d["assessable_fraction"], d["low_confidence"]), (4, 0.5, True))
        d = pg.grade_details(("met",) * 4 + ("not_assessable",), {}, "adequate", ())
        self.assertEqual((d["grade"], d["low_confidence"]), (5, False))  # 0.8 is not below 0.8
        d = pg.grade_details((), {}, "adequate", ())  # no ACs: cannot be a 5
        self.assertEqual((d["grade"], d["assessable_fraction"], d["low_confidence"]), (4, 0.0, True))
        self.assertEqual(self.grade(ac=("not_assessable",) * 3 + ("met",), blocker=1), 2)
        self.assertEqual(pg.grade_details(("met",) * 4 + ("not_assessable",) * 2 + ("met",) * 0,
                                          {}, "adequate", ())["grade"], 4)

    def test_unresolved_severe_claim_caps_at_four(self):
        d = pg.grade_details(("met",) * 5, {}, "adequate", (), unresolved_severe=1)
        self.assertEqual((d["grade"], d["low_confidence"]), (4, True))
        self.assertEqual(self.grade(unresolved=2), 4)

    def test_apply_verification_discards_unverified(self):
        review = strong_review()
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
        self.assertEqual(out["unresolved_claims"], 1)
        self.assertEqual(out["unresolved_breakdown"], {"unverifiable": 1, "not_verified": 0})
        self.assertTrue(out["low_confidence"])
        self.assertEqual(out["assessable_fraction"], 1.0)

    def test_unresolved_claims_never_lift_a_grade_silently(self):
        review = strong_review()
        review["findings"] = [{"id": "F3", "severity": "blocker", "file": "x", "line": 1, "title": "t",
                               "description": "d", "evidence": "e", "verifiable_by_inspection": False}]
        for v in ({"finding:F3": verdict("unverifiable", "not_applicable", ne=True)}, {}):
            out = pg.apply_verification(review, v)
            self.assertEqual(out["verified"]["blocker"], 0)
            self.assertEqual(out["grade"], 4)  # not 5
            self.assertEqual(out["unresolved_claims"], 1)
            self.assertTrue(out["low_confidence"])
        self.assertEqual(pg.apply_verification(review, {})["unresolved_breakdown"],
                         {"unverifiable": 0, "not_verified": 1})
        # a refuted claim is resolved: nothing outstanding, grade 5
        out = pg.apply_verification(review, {"finding:F3": verdict("refuted", "not_a_defect")})
        self.assertEqual((out["grade"], out["unresolved_claims"], out["low_confidence"]), (5, 0, False))

    def test_downgrade_on_confirmation_and_missing_verification(self):
        review = strong_review()
        out = pg.apply_verification(review, {"finding:F1": verdict("confirmed", "minor")})
        self.assertEqual(out["verified"], {"blocker": 0, "major": 0, "minor": 1})
        self.assertEqual(out["grade"], 5)
        out = pg.apply_verification(review, {})
        self.assertEqual(out["discarded"][0]["reason"], "not_verified")
        out = pg.apply_verification(review, {"finding:F1": verdict("confirmed", "not_a_defect")})
        self.assertEqual(out["discarded"][0]["reason"], "confirmed_as_not_a_defect")

    def test_ac_claims_are_verified(self):
        review = strong_review()
        review["acs"][0]["status"] = "not_met"
        review["findings"] = []
        n = pg.apply_verification(review, {"ac:AC1": verdict("confirmed", "not_applicable")})
        self.assertEqual((n["grade"], n["ac_statuses"][0]), (3, "not_met"))  # one not_met, no blocker
        n = pg.apply_verification(review, {"ac:AC1": verdict("refuted", "not_applicable")})
        self.assertEqual((n["grade"], n["ac_statuses"][0]), (5, "met"))
        n = pg.apply_verification(review, {"ac:AC1": verdict("unverifiable", "not_applicable", ne=True)})
        self.assertEqual((n["grade"], n["ac_statuses"][0]), (5, "not_assessable"))  # 4/5 = 0.8
        self.assertEqual((n["assessable_fraction"], n["unresolved_claims"]), (0.8, 1))
        n = pg.apply_verification(review, {})
        self.assertEqual(n["ac_statuses"][0], "not_assessable")
        self.assertEqual(n["unresolved_breakdown"], {"unverifiable": 0, "not_verified": 1})
        review["acs"][1]["status"] = "partial"
        n = pg.apply_verification(review, {"ac:AC1": verdict("unverifiable", "not_applicable", ne=True),
                                           "ac:AC2": verdict("unverifiable", "not_applicable", ne=True)})
        self.assertEqual((n["grade"], n["assessable_fraction"], n["low_confidence"]), (4, 0.6, True))

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
        mk = lambda g, met=2, tot=2, frac=1.0, unres=0: {  # noqa: E731
            "grade": g, "reviewer_reported_grade": g, "verified": {"blocker": 0, "major": 0, "minor": 0},
            "reported_minor": 0, "discarded": [], "acs_met": met, "acs_total": tot,
            "assessable_fraction": frac, "low_confidence": frac < 0.8, "unresolved_claims": unres}
        a = pg.aggregate([mk(5), mk(3), mk(4)])
        self.assertEqual(a["grade"], 4)
        self.assertEqual(a["per_reviewer_grades"], [5, 3, 4])
        self.assertEqual((a["assessable_fraction"], a["low_confidence"]), (1.0, False))
        a = pg.aggregate([mk(5), None, mk(3)])
        self.assertEqual((a["grade"], a["n_valid_reviewers"]), (4, 2))
        a = pg.aggregate([mk(5), mk(2), None])
        self.assertEqual(a["grade"], 3.5)
        a = pg.aggregate([None, None, None])
        self.assertIsNone(a["grade"])
        self.assertIsNone(a["assessable_fraction"])
        self.assertFalse(a["low_confidence"])
        self.assertEqual(pg.median_grade([1, 5, 5]), 5)
        a = pg.aggregate([mk(4, frac=0.5), mk(4, frac=0.5, unres=2), mk(4, frac=1.0, unres=1)])
        self.assertEqual((a["assessable_fraction"], a["low_confidence"]), (0.5, True))
        self.assertEqual((a["unresolved_claims"], a["unresolved_claims_total"]), ([0, 2, 1], 3))
        self.assertEqual(a["per_reviewer_assessable_fraction"], [0.5, 0.5, 1.0])


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
            "acs_met": 3, "acs_total": 4, "assessable_fraction": 0.75, "low_confidence": True,
            "unresolved_claims": 2}
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
        self.assertEqual((row["assessable_fraction"], row["low_confidence"]), (0.75, True))
        self.assertEqual(row["unresolved_claims"], "2|-|2")
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


# --------------------------------------------------------------------------
# A fake `claude` executable stands in for the model: it records everything it
# is handed (argv, cwd, PWD, stdin) so tests can assert what a reviewer receives.
# --------------------------------------------------------------------------

FAKE_TEMPLATE = r"""#!__PY__
import json, os, re, sys
args = sys.argv[1:]
if args[:1] == ["--version"]:
    print(os.environ.get("FAKE_VERSION", "2.1.292 (Claude Code)")); sys.exit(0)
if args[:1] == ["--help"]:
    print("Options:\n  --add-dir <d>  dirs\n" + ("" if os.environ.get("FAKE_NO_RESTRICTED")
          else "  --restricted   Restricted mode: confines file tools\n")); sys.exit(0)
stdin = sys.stdin.read()
with open(os.environ["PR_GRADER_FAKE_LOG"], "a") as f:
    f.write(json.dumps({"argv": args, "cwd": os.getcwd(), "pwd": os.environ.get("PWD"),
                        "stdin": stdin, "config_dir": os.environ.get("CLAUDE_CONFIG_DIR")}) + "\n")
if "Quote verbatim, from everything in your context" in stdin:
    print(json.dumps([{"type": "result", "result": os.environ.get("FAKE_CONTEXT_LEAK", "NONE"),
                       "total_cost_usd": 0.01}])); sys.exit(0)
if "File-reading probe" in " ".join(args) or "file-reading probe" in " ".join(args):
    add = args[args.index("--add-dir") + 1]
    lines = []
    for label, path in zip(("INSIDE", "OUTSIDE"), re.findall(r"file (/\S+?\.txt)", stdin)):
        ok = path.startswith(add + "/") or os.environ.get("FAKE_NO_CONFINE")
        lines.append(label + "=" + (open(path).read().strip() if ok else "REFUSED"))
    result = "\n".join(lines)
elif "Claim to verify" in stdin:
    result = json.dumps(VERIFY)
else:
    result = json.dumps(REVIEW)
print(json.dumps([{"type": "system"}, {"type": "result", "result": result, "total_cost_usd": 0.01,
      "usage": {"input_tokens": 1, "output_tokens": 1}, "modelUsage": {"fake-model": {}}}]))
"""


def make_fake_claude(dirpath, review=None, verify=None):
    review = review if review is not None else strong_review()
    verify = verify if verify is not None else verdict("confirmed", "major")
    src = FAKE_TEMPLATE.replace("__PY__", sys.executable)
    src = f"REVIEW = {review!r}\nVERIFY = {verify!r}\n" + src.split("\n", 1)[1]
    src = f"#!{sys.executable}\n" + src
    path = Path(dirpath) / "fakeclaude"
    path.write_text(src)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def read_log(p):
    if not Path(p).exists():
        return []
    return [json.loads(line) for line in Path(p).read_text().splitlines() if line.strip()]


def neutral_test_root():
    """A neutral stage root under /run/user/<uid>; None if unavailable (tests then skip)."""
    import random
    base = Path(f"/run/user/{os.getuid()}")
    if not (base.is_dir() and os.access(base, os.W_OK)):
        return None
    root = base / ("pgradetest" + "".join(random.choice("abcdefghijklmnop") for _ in range(8)))
    return root


class FakeClaudeCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tmpdir()
        self.t = Path(self._tmp.name)
        self.log = self.t / "fake.log"
        os.environ["PR_GRADER_FAKE_LOG"] = str(self.log)
        self.root = neutral_test_root()
        if self.root is None:
            self.skipTest("no /run/user/<uid> to host a neutral stage root")
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        os.environ.pop("PR_GRADER_FAKE_LOG", None)
        for k in ("FAKE_VERSION", "FAKE_NO_RESTRICTED", "FAKE_NO_CONFINE", "FAKE_CONTEXT_LEAK"):
            os.environ.pop(k, None)
        if self.root and self.root.exists():
            pg.make_tree_writable(self.root)
            shutil.rmtree(self.root, ignore_errors=True)
        self._tmp.cleanup()


class NeutralPathAndLeakTests(FakeClaudeCase):
    def run_grade(self, extra=(), out_name="out"):
        repo = make_fixture_repo(self.t)
        issue = self.t / "issue.txt"
        issue.write_text("# Fix thing\nMake f add one.\n")
        out = self.t / out_name
        fake = make_fake_claude(self.t)
        rc = pg.main(["grade", "--repo-path", str(repo), "--merge-commit", "HEAD", "--label", "arm-label",
                      "--issue-file", str(issue), "--pr-number", "99", "--out", str(out),
                      "--stage-root", str(self.root), "--claude", fake, "--reviewers", "2",
                      "--max-verifications", "3", *extra])
        return rc, repo, out

    def test_nothing_a_reviewer_receives_names_the_project_user_or_scratch(self):
        rc, repo, out = self.run_grade()
        self.assertEqual(rc, 0)
        records = [r for r in read_log(self.log) if "-p" in r["argv"]]
        self.assertGreaterEqual(len(records), 3)  # two reviewers and at least one verifier
        self.assertTrue(any("Claim to verify" in r["stdin"] for r in records))
        # project names: every non-generic directory above the artifact, e.g. the repository and
        # sub-project this test file is checked out in
        core, derived = pg.derive_leak_terms(out, repo, Path(*HERE.parts[:-3]), self.t)
        forbidden = set(core) | set(derived) | {getpass.getuser(), ".scratch", self.t.name}
        forbidden = {f.lower() for f in forbidden if f}
        self.assertIn(".scratch", forbidden)
        self.assertIn(getpass.getuser().lower(), forbidden)
        for rec in records:
            received = "\n".join(rec["argv"]) + "\n" + rec["cwd"] + "\n" + str(rec["pwd"]) + "\n" + rec["stdin"]
            low = received.lower()
            for term in forbidden:
                # user name and `.scratch` as substrings; path words as whole tokens ("fixtures" is not "fixture")
                pat = re.escape(term) if term in (".scratch", getpass.getuser().lower()) \
                    else rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
                self.assertIsNone(re.search(pat, low), f"{term!r} reached a reviewer")
            self.assertTrue(rec["cwd"].startswith(str(self.root)))
            self.assertEqual(rec["pwd"], rec["cwd"])
            self.assertTrue(rec["argv"][rec["argv"].index("--add-dir") + 1].startswith(str(self.root)))
            self.assertEqual(os.listdir(rec["cwd"]), [])  # neutral and empty
        manifest = json.loads((out / "arm-label" / "inputs_manifest.json").read_text())
        self.assertTrue(manifest["blinding_scan"]["ok"])
        self.assertEqual(manifest["blinding_scan"]["reviewer_input_hits"], [])
        self.assertTrue(manifest["stage_dir"].startswith(str(self.root)))
        grade = json.loads((out / "arm-label" / "grade.json").read_text())
        self.assertIn("assessable_fraction", grade["aggregate"])
        self.assertIn("ambient_strict", grade["blinding_counts"])

    def test_stage_root_with_identifying_words_is_refused(self):
        for bad in (".scratch/x", getpass.getuser() + "/x", "projectzzzz/x"):
            root = Path(self.t) / bad
            with self.assertRaises(pg.LeakError, msg=bad):
                pg.resolve_stage_root(str(root), Path(self.t) / "out" / "projectzzzz", self.t)
        with self.assertRaises(pg.GraderError):
            pg.resolve_stage_root("relative/path", self.t, self.t)

    def test_default_stage_root_uses_uid_not_user_name(self):
        r = pg.default_stage_root()
        self.assertEqual(str(r), f"/run/user/{os.getuid()}/pgrade")
        self.assertNotIn(getpass.getuser(), str(r))

    def test_leak_scan_covers_prompts_argv_paths_and_pwd(self):
        core, derived = ["alice", ".scratch"], ["somerepo"]
        base = dict(argv="-p\n--add-dir\n/run/pg/x/in", system_prompt="s", user_prompt="u",
                    stage_dir="/run/pg/x/in", cwd="/run/pg/x/cwd", env_PWD="/run/pg/x/cwd")
        self.assertEqual(pg.scan_reviewer_inputs(base, core, derived), [])
        for field, bad in [("argv", "--add-dir /home/alice/in"), ("system_prompt", "see .scratch/n"),
                           ("user_prompt", "SomeRepo docs"), ("stage_dir", "/x/somerepo/in"),
                           ("cwd", "/home/alice"), ("env_PWD", "/work/.scratch/c")]:
            f = dict(base)
            f[field] = bad
            hits = pg.scan_reviewer_inputs(f, core, derived)
            self.assertEqual([h["field"] for h in hits], [field], field)
        # reviewer-authored claim text: only core terms (user name, .scratch) are checked
        f = dict(base, user_prompt="the somerepo module")
        self.assertEqual(pg.scan_reviewer_inputs(f, core, derived, soft_fields=("user_prompt",)), [])
        f = dict(base, user_prompt="fixtures of somerepos")  # whole tokens only
        self.assertEqual(pg.scan_reviewer_inputs(f, core, derived), [])
        f = dict(base, user_prompt="alice wrote this")
        self.assertTrue(pg.scan_reviewer_inputs(f, core, derived, soft_fields=("user_prompt",)))

    def test_execute_role_refuses_a_leaking_path_before_any_model_call(self):
        stage = self.t / ".scratch" / "in"
        stage.mkdir(parents=True)
        cwd = self.t / "cwd"
        cwd.mkdir()
        core, derived = pg.derive_leak_terms(self.t)
        ctx = {"resume": False, "claude": make_fake_claude(self.t), "model": "opus", "effort": "high",
               "stage_dir": stage, "max_budget_usd": 1, "cwd": cwd, "timeout": 20,
               "manifest_file_count": 0, "manifest_sha256": "0", "leak_core": core, "leak_derived": derived}
        with self.assertRaises(pg.LeakError):
            pg.execute_role("reviewer:1", self.t / "run", ctx, "S", "U", REVIEW_SCHEMA)
        self.assertEqual(read_log(self.log), [])

    def test_strip_list_flows_through_stage_command_and_reports_counts(self):
        repo = make_fixture_repo(self.t)
        issue = self.t / "issue.txt"
        issue.write_text("# T\nB\n")
        strip = self.t / "strip.txt"
        strip.write_text("# c\ndocs/guide.md\nnot/there/**\n")
        out = self.t / "out"
        rc = pg.main(["stage", "--repo-path", str(repo), "--merge-commit", "HEAD", "--label", "l",
                      "--issue-file", str(issue), "--out", str(out), "--stage-root", str(self.root),
                      "--strip-list", str(strip)])
        self.assertEqual(rc, 0)
        m = json.loads((out / "l" / "inputs_manifest.json").read_text())
        self.assertEqual(m["tree"]["strip_patterns_unmatched"], ["not/there/**"])
        self.assertFalse(any(f["path"].endswith("docs/guide.md") for f in m["files"]))
        self.assertIn("ambient_domain_ambiguous_by_term", m["blinding_scan"]["counts"])


class ResumeTests(FakeClaudeCase):
    def ctx(self, **over):
        stage = self.t / "stage"
        cwd = self.t / "cwd"
        stage.mkdir(exist_ok=True)
        cwd.mkdir(exist_ok=True)
        c = {"resume": True, "claude": make_fake_claude(self.t), "model": "opus", "effort": "high",
             "stage_dir": stage, "max_budget_usd": 1, "cwd": cwd, "timeout": 30,
             "manifest_file_count": 3, "manifest_sha256": "m" * 64}
        c.update(over)
        return c

    def run_role(self, ctx, system="S", user="U"):
        return pg.execute_role("reviewer:1", self.t / "run", ctx, system, user, REVIEW_SCHEMA)

    def test_matching_stored_result_is_reused_without_a_model_call(self):
        first = self.run_role(self.ctx())
        self.assertTrue(first["ok"])
        self.assertEqual(len(read_log(self.log)), 1)
        again = self.run_role(self.ctx())
        self.assertEqual(again["parsed"], first["parsed"])
        self.assertEqual(len(read_log(self.log)), 1)

    def test_stale_results_are_refused_with_a_clear_message(self):
        self.run_role(self.ctx())
        cases = [("prompt", dict(user="U changed")), ("system prompt", dict(system="S changed")),
                 ("inputs", dict(ctx=self.ctx(manifest_sha256="z" * 64))),
                 ("model", dict(ctx=self.ctx(model="sonnet"))),
                 ("effort", dict(ctx=self.ctx(effort="low")))]
        for name, kw in cases:
            kw = dict(kw)
            c = kw.pop("ctx", None) or self.ctx()
            with self.assertRaises(pg.StaleResultError, msg=name) as cm:
                self.run_role(c, **kw)
            self.assertIn("stale stored result", str(cm.exception))
            self.assertIn("--no-resume", str(cm.exception))
        self.assertEqual(len(read_log(self.log)), 1)  # never called the model again
        # --no-resume regenerates
        self.run_role(self.ctx(resume=False), user="U changed")
        self.assertEqual(len(read_log(self.log)), 2)

    def test_legacy_result_without_hashes_is_refused(self):
        self.run_role(self.ctx())
        f = self.t / "run" / "result.json"
        d = json.loads(f.read_text())
        del d["input_hashes"]
        f.write_text(json.dumps(d))
        with self.assertRaises(pg.StaleResultError) as cm:
            self.run_role(self.ctx())
        self.assertIn("no input hashes", str(cm.exception))

    def test_grade_command_exits_4_on_stale_results(self):
        repo = make_fixture_repo(self.t)
        issue = self.t / "issue.txt"
        issue.write_text("# Fix thing\nMake f add one.\n")
        out = self.t / "out"
        args = ["grade", "--repo-path", str(repo), "--merge-commit", "HEAD", "--label", "l",
                "--issue-file", str(issue), "--out", str(out), "--stage-root", str(self.root),
                "--claude", make_fake_claude(self.t), "--reviewers", "1", "--max-verifications", "1"]
        self.assertEqual(pg.main(args), 0)
        n = len(read_log(self.log))
        self.assertEqual(pg.main(args), 0)  # same inputs: resumed, no model calls
        self.assertEqual(len(read_log(self.log)), n)
        # same label, different issue text: the staged inputs differ, so stored results are stale
        issue.write_text("# Fix thing\nMake f add TWO.\n")
        self.assertEqual(pg.main(args), 4)
        self.assertEqual(len(read_log(self.log)), n)


class PreflightTests(FakeClaudeCase):
    def test_pure_checks(self):
        self.assertEqual(pg.parse_version("2.1.292 (Claude Code)"), (2, 1, 292))
        self.assertIsNone(pg.parse_version("garbage"))
        helpt = "Options:\n  --restricted      Restricted mode\n"
        self.assertTrue(pg.check_cli("c", help_text=helpt, version_text="2.1.292 (Claude Code)")["ok"])
        self.assertTrue(pg.check_cli("c", help_text=helpt, version_text="3.0.0")["ok"])
        r = pg.check_cli("c", help_text=helpt, version_text="2.1.100 (Claude Code)")
        self.assertFalse(r["ok"])
        self.assertIn("older than the minimum", r["problems"][0])
        r = pg.check_cli("c", help_text="Options:\n  --add-dir x\n", version_text="2.1.292")
        self.assertFalse(r["restricted_flag"])
        self.assertIn("--restricted", r["problems"][0])
        self.assertFalse(pg.check_cli("c", help_text=helpt, version_text="nonsense")["ok"])
        self.assertEqual(pg.judge_read_probe("INSIDE=INaaa\nOUTSIDE=REFUSED", "INaaa", "OUTbbb"), [])
        self.assertTrue(pg.judge_read_probe("INSIDE=INaaa\nOUTSIDE=OUTbbb", "INaaa", "OUTbbb"))
        self.assertTrue(pg.judge_read_probe("INSIDE=REFUSED\nOUTSIDE=REFUSED", "INaaa", "OUTbbb"))

    def run_preflight(self, *extra):
        return pg.main(["preflight", "--claude", make_fake_claude(self.t), "--stage-root", str(self.root),
                        "--out", str(self.t / "out"), *extra])

    def test_preflight_command_with_fake_cli(self):
        self.assertEqual(self.run_preflight("--no-live"), 0)
        self.assertEqual(read_log(self.log), [])
        self.assertEqual(self.run_preflight(), 0)  # live probe: inside read works, outside refused
        self.assertEqual(len(read_log(self.log)), 2)  # read probe and context probe
        os.environ["FAKE_NO_CONFINE"] = "1"
        self.assertEqual(self.run_preflight(), 5)  # a CLI that does not confine reads fails
        del os.environ["FAKE_NO_CONFINE"]
        os.environ["FAKE_NO_RESTRICTED"] = "1"
        self.assertEqual(self.run_preflight("--no-live"), 5)
        del os.environ["FAKE_NO_RESTRICTED"]
        os.environ["FAKE_VERSION"] = "2.0.1 (Claude Code)"
        self.assertEqual(self.run_preflight("--no-live"), 5)

    def test_context_probe_judging_and_warning(self):
        self.assertEqual(pg.judge_context_probe("/x/y\nuser alice here", ["alice", ".scratch", "bob"]),
                         ["alice"])
        self.assertEqual(pg.judge_context_probe("NONE", ["alice"]), [])
        import contextlib
        import io
        for leak, expect_warning in (("NONE", False), (getpass.getuser() + "@example.invalid", True)):
            os.environ["FAKE_CONTEXT_LEAK"] = leak
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = self.run_preflight()
            self.assertEqual(rc, 0)  # a warning, not a failure: the runner cannot remove CLI-injected text
            self.assertEqual("WARNING: the CLI itself puts identifying text" in buf.getvalue(), expect_warning)
            self.assertNotIn(leak, buf.getvalue()) if expect_warning else None

    def test_config_dir_is_passed_to_the_cli_environment(self):
        self.assertEqual(pg.child_env("/c", "/neutral/cfg")["CLAUDE_CONFIG_DIR"], "/neutral/cfg")
        self.assertNotEqual(pg.child_env("/c").get("CLAUDE_CONFIG_DIR"), "/neutral/cfg")
        self.assertEqual(self.run_preflight("--config-dir", str(self.t / "cfg")), 0)
        self.assertEqual({r["config_dir"] for r in read_log(self.log)}, {str(self.t / "cfg")})

    def test_grade_stops_before_any_model_call_on_a_bad_cli(self):
        repo = make_fixture_repo(self.t)
        issue = self.t / "issue.txt"
        issue.write_text("# T\nB\n")
        os.environ["FAKE_NO_RESTRICTED"] = "1"
        rc = pg.main(["grade", "--repo-path", str(repo), "--merge-commit", "HEAD", "--label", "l",
                      "--issue-file", str(issue), "--out", str(self.t / "out"), "--stage-root",
                      str(self.root), "--claude", make_fake_claude(self.t), "--reviewers", "1"])
        self.assertEqual(rc, 5)
        self.assertEqual(read_log(self.log), [])


if __name__ == "__main__":
    unittest.main()
