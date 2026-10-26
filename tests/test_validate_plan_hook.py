"""Tests for scripts/validate-plan-hook.py (PostToolUse adapter).

Run: python3 -m unittest discover -s tests -v
"""

import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO_ROOT, "scripts", "validate-plan-hook.py")
HOOKS_JSON = os.path.join(REPO_ROOT, "hooks", "hooks.json")
FIXTURES = os.path.join(REPO_ROOT, "tests", "fixtures")
PLAN_DIR = os.path.join("docs", "superpowers", "plans")
SPEC_DIR = os.path.join("docs", "superpowers", "specs")
PLAN_REMINDER = ("Plan has no validation errors. Run the self-review, then offer the HTML "
                 "companion as its own message before the execution handoff "
                 "(skip if already offered for this plan).")
SPEC_REMINDER = ("When the user approves this spec, or asks to continue to the plan, offer "
                 "the HTML companion as its own message first and wait for the answer "
                 "before starting the plan (skip if already offered for this spec).")

WARNING_ONLY_PLAN = """# Plan

### Task 1: Greeting

**Files:**
- Modify: `src/app.py`

**Interfaces:**
- Produces: `greet(name: str) -> str`

- [ ] **Step 1: Write failing test**: `greet("Ann") == "Hi Ann"`
- [ ] **Step 2: Verify** `python3 -m unittest -v` → Expected: PASS
"""


def load_hook():
    spec = importlib.util.spec_from_file_location("validate_plan_hook", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class HookTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.project = os.path.join(self.tmp, "project")
        self.plans = os.path.join(self.project, PLAN_DIR)
        os.makedirs(self.plans)
        self.incomplete = self.copy_fixture("incomplete-plan.md", "2026-01-01-incomplete.md")
        self.valid = self.copy_fixture("valid-plan.md", "2026-01-01-valid.md")
        self.hook = load_hook()

    def copy_fixture(self, name, dest_name, dest_dir=None):
        dest = os.path.join(dest_dir or self.plans, dest_name)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copyfile(os.path.join(FIXTURES, name), dest)
        return dest

    def payload(self, file_path, tool="Write", cwd=None):
        tool_input = {"file_path": file_path}
        if tool == "Write":
            tool_input["content"] = "..."
        else:
            tool_input.update(old_string="a", new_string="b", replace_all=False)
        return {
            "session_id": "s",
            "transcript_path": "/tmp/t.jsonl",
            "cwd": cwd or self.project,
            "hook_event_name": "PostToolUse",
            "tool_name": tool,
            "tool_input": tool_input,
            "tool_response": {"filePath": file_path, "success": True},
            "tool_use_id": "toolu_1",
        }

    def run_main(self, stdin_text, environ=None):
        out, err = io.StringIO(), io.StringIO()
        code = self.hook.main(
            stdin=io.StringIO(stdin_text), stdout=out, stderr=err,
            environ=environ if environ is not None else {},
        )
        return code, out.getvalue(), err.getvalue()

    def run_payload(self, payload, environ=None):
        return self.run_main(json.dumps(payload), environ)

    def assert_silent(self, result):
        code, out, err = result
        self.assertEqual((code, out, err), (0, "", ""))

    def assert_feedback(self, result):
        code, out, err = result
        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
        data = json.loads(out)
        self.assertNotIn("decision", data)
        spec = data["hookSpecificOutput"]
        self.assertEqual(spec["hookEventName"], "PostToolUse")
        return data


class FeedbackTests(HookTestCase):
    def test_incomplete_plan_gets_actionable_feedback(self):
        data = self.assert_feedback(self.run_payload(self.payload(self.incomplete)))
        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("docs/superpowers/plans/2026-01-01-incomplete.md", context)
        self.assertIn(":28: error [placeholder] Task 2:", context)
        self.assertIn("fix:", context)
        self.assertIn("advisory", context.lower())
        self.assertIn("already", context.lower())
        self.assertIn("has 6 errors, 4 warnings.", context)
        self.assertIn("Summary: 6 errors, 4 warnings —", context)
        self.assertNotIn(PLAN_REMINDER, context)  # errors first; reminder once they are fixed
        self.assertNotIn("info", context)
        self.assertIn("6 errors", data["systemMessage"])
        self.assertNotIn(self.tmp, data["systemMessage"])

    def test_clean_plan_gets_offer_reminder(self):
        # 1.0.2: the reminder sits next to the handoff instead of only in
        # session-start context (lost in long sessions).
        data = self.assert_feedback(self.run_payload(self.payload(self.valid)))
        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn(PLAN_REMINDER, context)
        self.assertIn("docs/superpowers/plans/2026-01-01-valid.md", context)
        self.assertNotIn("error [", context)
        self.assertNotIn("warning [", context)
        self.assertNotIn("systemMessage", data)

    def test_warnings_only_have_context_but_no_system_message(self):
        path = os.path.join(self.plans, "warn.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(WARNING_ONLY_PLAN)
        data = self.assert_feedback(self.run_payload(self.payload(path)))
        self.assertNotIn("systemMessage", data)
        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("warning [pattern]", context)
        self.assertNotIn("error [", context)
        self.assertIn("has 0 errors, 1 warning.", context)
        self.assertNotIn("info", context)
        self.assertIn(PLAN_REMINDER, context)

    def test_single_error_is_singular(self):
        path = os.path.join(self.plans, "one.md")
        with open(self.valid, encoding="utf-8") as f:
            text = f.read().replace(
                "**Interfaces:**\n- Produces: `count_syllables(word: str) -> int` — always ≥ 1.\n", "")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        data = self.assert_feedback(self.run_payload(self.payload(path)))
        self.assertIn("has 1 error, 0 warnings.", data["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn(PLAN_REMINDER, data["hookSpecificOutput"]["additionalContext"])
        self.assertIn("Plan validation: 1 error, 0 warnings in", data["systemMessage"])

    def test_edit_tool_validates_file_on_disk(self):
        data = self.assert_feedback(self.run_payload(self.payload(self.incomplete, tool="Edit")))
        self.assertIn("[placeholder]", data["hookSpecificOutput"]["additionalContext"])

    def test_info_findings_never_reported(self):
        path = os.path.join(self.plans, "long.md")
        code = "\n".join("x%d = %d" % (i, i) for i in range(45))
        with open(self.valid, encoding="utf-8") as f:
            text = f.read().replace("## Self-Review", "```python\n%s\n```\n\n## Self-Review" % code)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        data = self.assert_feedback(self.run_payload(self.payload(path)))
        context = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn(PLAN_REMINDER, context)
        self.assertNotIn("long-code", context)

    def test_plan_is_never_modified(self):
        before = sha256(self.incomplete), os.stat(self.incomplete).st_mtime_ns
        self.run_payload(self.payload(self.incomplete))
        self.run_payload(self.payload(self.incomplete, tool="Edit"))
        self.assertEqual((sha256(self.incomplete), os.stat(self.incomplete).st_mtime_ns), before)

    def test_subprocess_end_to_end(self):
        result = subprocess.run(
            [sys.executable, HOOK], input=json.dumps(self.payload(self.incomplete)),
            capture_output=True, text=True, timeout=10, cwd=self.tmp,
            env={k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[placeholder]", json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"])


class BytecodeTests(HookTestCase):
    def test_hook_leaves_no_bytecode_cache_in_plugin(self):
        # The hook imports validate-plan.py from the installed plugin; that must
        # not write __pycache__ into the plugin directory (1.0.1).
        scripts = os.path.join(self.tmp, "plugin", "scripts")
        shutil.copytree(os.path.join(REPO_ROOT, "scripts"), scripts,
                        ignore=shutil.ignore_patterns("__pycache__"))
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_PROJECT_DIR", "PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")}
        result = subprocess.run(
            [sys.executable, os.path.join(scripts, "validate-plan-hook.py")],
            input=json.dumps(self.payload(self.incomplete)),
            capture_output=True, text=True, timeout=10, env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[placeholder]", result.stdout)
        self.assertFalse(os.path.exists(os.path.join(scripts, "__pycache__")),
                         os.listdir(scripts))


class SpecReminderTests(HookTestCase):
    """1.0.2: spec writes get a reminder close to the spec handoff."""

    def setUp(self):
        super().setUp()
        self.spec_dir = os.path.join(self.project, SPEC_DIR)
        self.spec = self.copy_fixture("incomplete-plan.md", "2026-01-01-topic-design.md", self.spec_dir)

    def test_spec_write_and_edit_get_reminder(self):
        for tool in ("Write", "Edit"):
            with self.subTest(tool=tool):
                data = self.assert_feedback(self.run_payload(self.payload(self.spec, tool=tool)))
                context = data["hookSpecificOutput"]["additionalContext"]
                self.assertIn(SPEC_REMINDER, context)
                self.assertIn("docs/superpowers/specs/2026-01-01-topic-design.md", context)
                self.assertNotIn("error [", context)  # specs are not plan-validated
                self.assertNotIn("systemMessage", data)

    def test_relative_spec_path(self):
        rel = os.path.join(SPEC_DIR, "2026-01-01-topic-design.md")
        self.assertIn(SPEC_REMINDER, self.assert_feedback(
            self.run_payload(self.payload(rel)))["hookSpecificOutput"]["additionalContext"])

    def test_spec_lookalikes_and_other_files_ignored(self):
        cases = (
            (os.path.join("docs", "superpowers", "specs-old"), "s.md"),
            (os.path.join("other", "docs", "superpowers", "specs"), "s.md"),
            (SPEC_DIR, "s.txt"),
        )
        for rel_dir, name in cases:
            with self.subTest(rel_dir=rel_dir, name=name):
                path = self.copy_fixture("incomplete-plan.md", name, os.path.join(self.project, rel_dir))
                self.assert_silent(self.run_payload(self.payload(path)))

    def test_spec_outside_project_and_missing_file_ignored(self):
        outside = self.copy_fixture("incomplete-plan.md", "s.md", os.path.join(self.tmp, SPEC_DIR))
        self.assert_silent(self.run_payload(self.payload(outside)))
        self.assert_silent(self.run_payload(self.payload(os.path.join(self.spec_dir, "gone.md"))))

    def test_spec_never_modified(self):
        before = sha256(self.spec), os.stat(self.spec).st_mtime_ns
        self.run_payload(self.payload(self.spec))
        self.assertEqual((sha256(self.spec), os.stat(self.spec).st_mtime_ns), before)


class PathMatchingTests(HookTestCase):
    def test_relative_path_resolved_against_cwd(self):
        rel = os.path.join(PLAN_DIR, "2026-01-01-incomplete.md")
        self.assert_feedback(self.run_payload(self.payload(rel)))

    def test_relative_path_from_subdirectory_cwd(self):
        sub = os.path.join(self.project, "docs")
        rel = os.path.join("superpowers", "plans", "2026-01-01-incomplete.md")
        env = {"CLAUDE_PROJECT_DIR": self.project}
        self.assert_feedback(self.run_payload(self.payload(rel, cwd=sub), env))

    def test_project_dir_env_takes_precedence(self):
        # cwd is a subdirectory; without CLAUDE_PROJECT_DIR the plan would not be
        # under <cwd>/docs/superpowers/plans.
        sub = os.path.join(self.project, "src")
        os.makedirs(sub)
        payload = self.payload(self.incomplete, cwd=sub)
        self.assert_silent(self.run_payload(payload))
        self.assert_feedback(self.run_payload(payload, {"CLAUDE_PROJECT_DIR": self.project}))

    def test_markdown_outside_plan_dir_ignored(self):
        for rel in ("README.md", os.path.join("docs", "notes.md"),
                    os.path.join("docs", "superpowers", "reviews", "review.md")):
            with self.subTest(rel=rel):
                path = self.copy_fixture("incomplete-plan.md", os.path.basename(rel),
                                         os.path.join(self.project, os.path.dirname(rel)))
                self.assert_silent(self.run_payload(self.payload(path)))

    def test_lookalike_paths_ignored(self):
        lookalikes = (
            os.path.join("docs", "superpowers", "plans-old"),
            os.path.join("docs", "superpowers", "plansx"),
            os.path.join("other", "docs", "superpowers", "plans"),
            os.path.join("docs", "superpowers-plans"),
        )
        for rel_dir in lookalikes:
            with self.subTest(rel_dir=rel_dir):
                path = self.copy_fixture("incomplete-plan.md", "p.md",
                                         os.path.join(self.project, rel_dir))
                self.assert_silent(self.run_payload(self.payload(path)))

    def test_plan_dir_outside_project_ignored(self):
        outside = self.copy_fixture("incomplete-plan.md", "p.md", os.path.join(self.tmp, PLAN_DIR))
        self.assert_silent(self.run_payload(self.payload(outside)))

    def test_traversal_out_of_plan_dir_ignored(self):
        notes = self.copy_fixture("incomplete-plan.md", "notes.md", self.project)
        sneaky = os.path.join(self.plans, "..", "..", "..", "notes.md")
        self.assertTrue(os.path.exists(sneaky))
        self.assert_silent(self.run_payload(self.payload(sneaky)))
        self.assertTrue(os.path.exists(notes))

    def test_traversal_into_plan_dir_accepted(self):
        path = os.path.join(self.project, "docs", "..", PLAN_DIR, "2026-01-01-incomplete.md")
        self.assert_feedback(self.run_payload(self.payload(path)))

    def test_nested_plan_subdirectory_accepted(self):
        path = self.copy_fixture("incomplete-plan.md", "p.md", os.path.join(self.plans, "archive"))
        self.assert_feedback(self.run_payload(self.payload(path)))

    def test_non_markdown_in_plan_dir_ignored(self):
        for name in ("plan.txt", "plan.md.bak", "plan.html"):
            with self.subTest(name=name):
                path = self.copy_fixture("incomplete-plan.md", name)
                self.assert_silent(self.run_payload(self.payload(path)))

    def test_uppercase_md_extension_accepted(self):
        path = self.copy_fixture("incomplete-plan.md", "PLAN.MD")
        self.assert_feedback(self.run_payload(self.payload(path)))

    @unittest.skipIf(not hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlink_escaping_plan_dir_ignored(self):
        outside = self.copy_fixture("incomplete-plan.md", "outside.md", self.tmp)
        link = os.path.join(self.plans, "link.md")
        try:
            os.symlink(outside, link)
        except OSError:
            self.skipTest("cannot create symlink")
        self.assert_silent(self.run_payload(self.payload(link)))


class InputRobustnessTests(HookTestCase):
    def test_bad_input_is_silent(self):
        cases = {
            "empty": "",
            "malformed": "{not json",
            "array": "[1, 2]",
            "string": '"hi"',
            "no tool_input": json.dumps({"tool_name": "Write", "cwd": self.project}),
            "tool_input not dict": json.dumps({"tool_name": "Write", "tool_input": "x"}),
            "file_path not str": json.dumps({"tool_name": "Write", "tool_input": {"file_path": 5}}),
            "empty file_path": json.dumps({"tool_name": "Write", "tool_input": {"file_path": ""}}),
            "cwd not str": json.dumps({"tool_name": "Write", "cwd": 3,
                                       "tool_input": {"file_path": "docs/superpowers/plans/x.md"}}),
        }
        for name, stdin_text in cases.items():
            with self.subTest(case=name):
                self.assert_silent(self.run_main(stdin_text))

    def test_other_tools_ignored(self):
        for tool in ("Read", "Bash", "NotebookEdit"):
            with self.subTest(tool=tool):
                payload = self.payload(self.incomplete)
                payload["tool_name"] = tool
                self.assert_silent(self.run_payload(payload))

    def test_missing_file_is_silent(self):
        path = os.path.join(self.plans, "deleted.md")
        self.assert_silent(self.run_payload(self.payload(path)))

    def test_unreadable_file_is_silent(self):
        path = os.path.join(self.plans, "binary.md")
        with open(path, "wb") as f:
            f.write(b"\xff\xfe\x00bad")
        self.assert_silent(self.run_payload(self.payload(path)))

    def test_directory_named_like_plan_is_silent(self):
        os.makedirs(os.path.join(self.plans, "dir.md"))
        self.assert_silent(self.run_payload(self.payload(os.path.join(self.plans, "dir.md"))))

    def test_internal_error_exits_1_with_one_line_stderr(self):
        def boom(_path):
            raise RuntimeError("kaboom")

        self.hook.load_validator = lambda: type("V", (), {"validate_file": staticmethod(boom)})
        code, out, err = self.run_payload(self.payload(self.incomplete))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertEqual(err.count("\n"), 1)
        self.assertIn("kaboom", err)
        self.assertNotIn("Traceback", err)


class HookConfigTests(unittest.TestCase):
    def setUp(self):
        with open(HOOKS_JSON, encoding="utf-8") as f:
            self.config = json.load(f)["hooks"]

    def test_post_tool_use_registered_for_write_and_edit(self):
        groups = self.config["PostToolUse"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["matcher"], "Write|Edit")
        hook = groups[0]["hooks"][0]
        self.assertEqual(hook["type"], "command")
        self.assertEqual(hook["command"], "python3")
        self.assertEqual(hook["args"], ["${CLAUDE_PLUGIN_ROOT}/scripts/validate-plan-hook.py"])
        self.assertLessEqual(hook["timeout"], 30)
        self.assertTrue(os.path.isfile(HOOK))

    def test_session_start_unchanged(self):
        groups = self.config["SessionStart"]
        self.assertEqual(groups, [{
            "matcher": "startup|resume|clear|compact|fork",
            "hooks": [{
                "type": "command",
                "command": "python3",
                "args": ["${CLAUDE_PLUGIN_ROOT}/scripts/session-context.py"],
                "timeout": 10,
            }],
        }])

    def test_only_expected_events(self):
        self.assertEqual(set(self.config), {"SessionStart", "PreToolUse", "PostToolUse", "UserPromptSubmit"})


if __name__ == "__main__":
    unittest.main()
