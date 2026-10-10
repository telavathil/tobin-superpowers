"""Tests for scripts/session-context.py and its hook wiring.

Run: python3 -m unittest discover -s tests -v
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "session-context.py")
HOOKS_JSON = os.path.join(REPO_ROOT, "hooks", "hooks.json")
SKILL_MD = os.path.join(REPO_ROOT, "skills", "hybrid-planning", "SKILL.md")
MAX_CONTEXT_CHARS = 1500


def load_module():
    spec = importlib.util.spec_from_file_location("session_context", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_hook(stdin_text, cwd=None):
    return subprocess.run(
        [sys.executable, SCRIPT],
        input=stdin_text,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=10,
    )


def hook_input(source):
    return json.dumps({
        "session_id": "abc123",
        "transcript_path": "/tmp/t.jsonl",
        "cwd": "/tmp",
        "hook_event_name": "SessionStart",
        "source": source,
    })


class HookInputHandlingTests(unittest.TestCase):
    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        out = json.loads(result.stdout)
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")
        return out["hookSpecificOutput"]["additionalContext"]

    def test_all_matched_sources_succeed(self):
        for source in ("startup", "resume", "clear", "compact"):
            with self.subTest(source=source):
                self.assert_ok(run_hook(hook_input(source)))

    def test_startup_has_no_restate_note(self):
        context = self.assert_ok(run_hook(hook_input("startup")))
        self.assertNotIn("Restated after", context)

    def test_resume_clear_compact_add_restate_note(self):
        for source in ("resume", "clear", "compact"):
            with self.subTest(source=source):
                context = self.assert_ok(run_hook(hook_input(source)))
                self.assertIn("Restated after %s" % source, context)

    def test_tolerates_bad_input(self):
        cases = {
            "empty": "",
            "whitespace": "  \n",
            "malformed": "{not json",
            "array": "[1, 2]",
            "missing_source": json.dumps({"session_id": "x"}),
            "non_string_source": json.dumps({"source": 5}),
            "unknown_source": hook_input("something-new"),
        }
        for name, stdin_text in cases.items():
            with self.subTest(case=name):
                context = self.assert_ok(run_hook(stdin_text))
                self.assertIn("hybrid-planning", context)
                self.assertNotIn("Restated after", context)

    def test_independent_of_working_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_ok(run_hook(hook_input("startup"), cwd=tmp))


class OutputContentTests(unittest.TestCase):
    def setUp(self):
        self.context = load_module().build_context("startup")

    def test_is_concise(self):
        self.assertLess(len(self.context), MAX_CONTEXT_CHARS)

    def test_points_to_skill_and_upstream(self):
        self.assertIn("tobin-superpowers:hybrid-planning", self.context)
        self.assertIn("superpowers:writing-plans", self.context)

    def test_contains_contract_preferences(self):
        for phrase in (
            "token-efficient",
            "executable by a human without AI assistance",
            "exact file paths",
            "interfaces",
            "ordered steps",
            "codebase pattern",
            "test assertions",
            "verification commands",
            "Pseudocode or reference code",
            "No full code listings for routine changes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.context)

    def test_preserves_upstream_plan_location(self):
        self.assertIn("docs/superpowers/plans/", self.context)

    def test_does_not_mention_validation(self):
        self.assertNotIn("validat", self.context.lower())


class FailureBehaviorTests(unittest.TestCase):
    def test_internal_error_exits_1_with_one_line_stderr(self):
        module = load_module()

        def boom(_source):
            raise RuntimeError("kaboom")

        module.build_context = boom
        out, err = io.StringIO(), io.StringIO()
        code = module.main(stdin=io.StringIO(hook_input("startup")), stdout=out, stderr=err)
        self.assertEqual(code, 1)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue().count("\n"), 1)
        self.assertIn("kaboom", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_unreadable_stdin_still_succeeds(self):
        module = load_module()

        class BrokenStdin:
            def read(self):
                raise OSError("closed")

        out, err = io.StringIO(), io.StringIO()
        code = module.main(stdin=BrokenStdin(), stdout=out, stderr=err)
        self.assertEqual(code, 0)
        self.assertEqual(err.getvalue(), "")
        json.loads(out.getvalue())


class WiringTests(unittest.TestCase):
    def test_hooks_json_registers_session_start(self):
        with open(HOOKS_JSON, encoding="utf-8") as f:
            config = json.load(f)
        groups = config["hooks"]["SessionStart"]
        self.assertEqual(len(groups), 1)
        matcher = set(groups[0]["matcher"].split("|"))
        self.assertTrue({"startup", "resume"} <= matcher)
        hook = groups[0]["hooks"][0]
        self.assertEqual(hook["type"], "command")
        script_arg = hook["args"][0]
        self.assertTrue(script_arg.startswith("${CLAUDE_PLUGIN_ROOT}/"))
        resolved = script_arg.replace("${CLAUDE_PLUGIN_ROOT}", REPO_ROOT)
        self.assertTrue(os.path.isfile(resolved), resolved)

    def test_skill_frontmatter(self):
        with open(SKILL_MD, encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("---\n"))
        frontmatter = text.split("---\n")[1]
        self.assertIn("name: hybrid-planning\n", frontmatter)
        self.assertIn("description: ", frontmatter)


if __name__ == "__main__":
    unittest.main()
