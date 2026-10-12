"""Tests for scripts/inject-plan-standards.py and its hook wiring.

Run: python3 -m unittest discover -s tests -v
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "inject-plan-standards.py")
HOOKS_JSON = os.path.join(REPO_ROOT, "hooks", "hooks.json")
STANDARDS = (
    "comments", "dependencies", "edge-cases", "fallbacks", "logging",
    "plan-code", "reuse", "shims", "testing", "trust-types", "type-safety",
)
STANDARDS_DIR = os.path.join(REPO_ROOT, "standards")
_spec = importlib.util.spec_from_file_location("inject_plan_standards", SCRIPT)
inject = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(inject)


def run_hook(stdin_text, part="1"):
    return subprocess.run(
        [sys.executable, SCRIPT, part],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=10,
    )


def skill_payload(skill):
    return json.dumps({"tool_name": "Skill", "tool_input": {"skill": skill}})


class InjectPlanStandardsTests(unittest.TestCase):
    def test_writing_plans_injects_every_global_standard(self):
        context = ""
        for part in ("1", "2"):
            result = run_hook(skill_payload("superpowers:writing-plans"), part)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)["hookSpecificOutput"]
            self.assertEqual(output["hookEventName"], "PreToolUse")
            context += output["additionalContext"]
        self.assertIn("# Agent OS code standards", context)
        self.assertIn("## index.yml", context)
        for name in STANDARDS:
            with self.subTest(name=name):
                self.assertIn("## global/%s.md" % name, context)
        self.assertIn(os.path.join(REPO_ROOT, "standards"), context)

    def test_plan_skill_without_prefix_matches(self):
        for skill in ("writing-plans", "plan"):
            with self.subTest(skill=skill):
                self.assertIn("additionalContext", run_hook(skill_payload(skill)).stdout)

    def test_other_skill_is_silent(self):
        result = run_hook(skill_payload("superpowers:brainstorming"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_tolerates_bad_input(self):
        result = run_hook("not json")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_hooks_json_registers_skill_matcher(self):
        with open(HOOKS_JSON, encoding="utf-8") as f:
            groups = json.load(f)["hooks"]["PreToolUse"]
        self.assertEqual(groups[0]["matcher"], "Skill")
        hooks = groups[0]["hooks"]
        self.assertEqual([h["args"] for h in hooks], [
            ["${CLAUDE_PLUGIN_ROOT}/scripts/inject-plan-standards.py", "1"],
            ["${CLAUDE_PLUGIN_ROOT}/scripts/inject-plan-standards.py", "2"],
        ])
        for hook in hooks:
            self.assertEqual(hook["command"], "python3")
            self.assertEqual(hook["timeout"], 10)

    def test_each_part_stays_under_hook_context_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-q", tmp], check=True)
            marker = inject.marker_path(tmp, tmp)
            os.makedirs(os.path.dirname(marker))
            with open(marker, "w", encoding="utf-8") as f:
                f.write("Checked: 2026-10-12\nDebt location: Jira PROJ\n\n## Configs\n"
                        + "- packages/service-name/eslint.config.mjs: gap PR offered\n" * 25)
            for part in (1, 2):
                for data in (tmp, os.path.join(tmp, "empty")):
                    with self.subTest(part=part, data=data):
                        ctx = inject.build_context("writing-plans", tmp, STANDARDS_DIR, data, part)
                        self.assertLess(len(ctx), 9000)


class LintCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = os.path.join(self.tmp.name, "repo")
        self.data = os.path.join(self.tmp.name, "data")
        os.makedirs(self.repo)
        os.makedirs(self.data)
        subprocess.run(["git", "init", "-q", self.repo], check=True)

    def marker_path(self):
        return inject.marker_path(self.repo, self.data)

    def context(self, cwd=None, data="unset"):
        return "\n".join(inject.build_context(
            "writing-plans",
            self.repo if cwd is None else cwd,
            STANDARDS_DIR,
            self.data if data == "unset" else data,
            part,
        ) for part in (1, 2))

    def test_worktree_shares_main_repo_marker(self):
        subprocess.run(["git", "-C", self.repo, "-c", "user.name=t", "-c", "user.email=t@t",
                        "commit", "-q", "--allow-empty", "-m", "init"], check=True)
        tree = os.path.join(self.tmp.name, "tree")
        subprocess.run(["git", "-C", self.repo, "worktree", "add", "-q", tree], check=True)
        self.assertEqual(inject.marker_path(tree, self.data), self.marker_path())
        self.assertEqual(inject.marker_path(os.path.join(self.repo, ".git"), self.data),
                         self.marker_path())

    def test_no_marker_adds_lint_check(self):
        ctx = self.context()
        self.assertIn("## Lint baseline check (first plan in this repo)", ctx)
        self.assertIn(os.path.join(REPO_ROOT, "lint", "check.md"), ctx)
        self.assertIn(self.marker_path(), ctx)

    def test_marker_present_injects_state(self):
        path = self.marker_path()
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write("Checked: 2026-10-12\nDebt location: Jira PROJ\n")
        ctx = self.context()
        self.assertIn("Debt location: Jira PROJ", ctx)
        self.assertNotIn("Lint baseline check", ctx)

    def test_unreadable_marker_still_injects_standards(self):
        path = self.marker_path()
        os.makedirs(path)
        self.assertIn("## global/plan-code.md", self.context())
        os.rmdir(path)
        with open(path, "wb") as f:
            f.write(b"\xff\xfe\x00bad")
        ctx = self.context()
        self.assertIn("## global/plan-code.md", ctx)
        self.assertNotIn("Lint baseline check", ctx)

    def test_repo_key(self):
        self.assertEqual(inject.repo_key("/home/x/repo"), "home-x-repo")
        self.assertEqual(inject.repo_key("C:\\Users\\x\\repo"), "Users-x-repo")

    def test_non_git_cwd_skips_lint_section(self):
        ctx = self.context(cwd=self.tmp.name)
        self.assertIn("## global/plan-code.md", ctx)
        self.assertNotIn("Lint baseline check", ctx)

    def test_no_plugin_data_skips_lint_section(self):
        ctx = self.context(data=None)
        self.assertIn("## global/plan-code.md", ctx)
        self.assertNotIn("Lint baseline check", ctx)


if __name__ == "__main__":
    unittest.main()
