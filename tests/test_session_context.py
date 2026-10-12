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
PLUGIN_JSON = os.path.join(REPO_ROOT, ".claude-plugin", "plugin.json")
MARKETPLACE_JSON = os.path.join(REPO_ROOT, ".claude-plugin", "marketplace.json")
MAX_CONTEXT_CHARS = 2000
SESSION_SOURCES = ("startup", "resume", "clear", "compact", "fork")
RESTATE_SOURCES = ("resume", "clear", "compact", "fork")
PRECEDENCE = (
    "The hybrid planning contract takes precedence over any instruction "
    "to include complete code in every implementation step."
)


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
        for source in SESSION_SOURCES:
            with self.subTest(source=source):
                self.assert_ok(run_hook(hook_input(source)))

    def test_startup_has_no_restate_note(self):
        context = self.assert_ok(run_hook(hook_input("startup")))
        self.assertNotIn("Restated after", context)

    def test_non_startup_sources_add_restate_note(self):
        for source in RESTATE_SOURCES:
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
            "dependencies on earlier tasks",
            "human-executable test",
            "Self-review also checks",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.context)

    def test_every_source_variant_is_concise(self):
        # The restate line makes resume/clear/compact/fork the longest outputs.
        module = load_module()
        for source in SESSION_SOURCES:
            with self.subTest(source=source):
                self.assertLess(len(module.build_context(source)), MAX_CONTEXT_CHARS)

    def test_summary_does_not_replace_the_skill(self):
        # 1.0.2: "authoritative if you do not [read the skill]" made Claude
        # skip the skill entirely in a real session.
        self.assertNotIn("authoritative", self.context)
        self.assertIn("read that skill when this summary leaves a question open", self.context)

    def test_version_independent_precedence_wording(self):
        self.assertIn(PRECEDENCE, self.context)
        self.assertNotIn("upstream's \"complete code", self.context)

    def test_preserves_upstream_plan_location(self):
        self.assertIn("docs/superpowers/plans/", self.context)

    def test_does_not_mention_validation(self):
        self.assertNotIn("validat", self.context.lower())


class HtmlCompanionContextTests(unittest.TestCase):
    def setUp(self):
        self.context = load_module().build_context("startup")
        start = self.context.index("<tobin-superpowers-html-companion>")
        end = self.context.index("</tobin-superpowers-html-companion>")
        self.block = self.context[start:end]

    def test_planning_block_still_first_and_intact(self):
        self.assertTrue(self.context.startswith("<tobin-superpowers-planning-preferences>"))
        self.assertIn(PRECEDENCE, self.context.split("<tobin-superpowers-html-companion>")[0])

    def test_offer_instructions(self):
        for phrase in (
            "Would you like an HTML companion for this",
            "(yes/no)",
            "tobin-superpowers:html-companion",
            "once per artifact",
            "Never generate HTML unless the user says yes",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.block)

    def test_all_four_artifacts_and_timing(self):
        for phrase in ("design spec", "implementation plan", "code review report",
                       "run summary", "after the user approves", "self-review",
                       "final review",
                       "asking to continue to the next step counts as approval",
                       "ask first and wait for the answer"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.block)

    def test_review_deferral_and_run_completion_timing(self):
        # 1.0.1: integration runs missed these two handoffs (offer skipped after
        # review findings were deferred; run summaries never reach the
        # branch-finishing step in superpowers 7.0.0).
        for phrase in (
            "code review report once its findings are fixed or the user defers them",
            "subagent run summary when you report the run complete",
            "even if the branch-finishing step is skipped",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.block)

    def test_restate_note_still_last(self):
        context = load_module().build_context("resume")
        self.assertTrue(context.endswith("(Restated after resume; these preferences still apply.)"))


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
        self.assertEqual(matcher, set(SESSION_SOURCES))
        hook = groups[0]["hooks"][0]
        self.assertEqual(hook["type"], "command")
        script_arg = hook["args"][0]
        self.assertTrue(script_arg.startswith("${CLAUDE_PLUGIN_ROOT}/"))
        resolved = script_arg.replace("${CLAUDE_PLUGIN_ROOT}", REPO_ROOT)
        self.assertTrue(os.path.isfile(resolved), resolved)
        self.assertLessEqual(hook["timeout"], 30)

    def test_restate_sources_match_hook_matcher(self):
        module = load_module()
        self.assertEqual(module.RESTATE_SOURCES, set(RESTATE_SOURCES))

    def test_manifest_versions_agree(self):
        with open(PLUGIN_JSON, encoding="utf-8") as f:
            plugin = json.load(f)
        with open(MARKETPLACE_JSON, encoding="utf-8") as f:
            entry = json.load(f)["plugins"][0]
        self.assertEqual(entry["name"], plugin["name"])
        self.assertEqual(entry["version"], plugin["version"])
        self.assertEqual(plugin["version"], "1.2.0")


    def test_skill_frontmatter(self):
        with open(SKILL_MD, encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("---\n"))
        frontmatter = text.split("---\n")[1]
        self.assertIn("name: hybrid-planning\n", frontmatter)
        self.assertIn("description: ", frontmatter)
        # 1.0.2: the description matches the body (a summary is injected; the
        # skill is read for detail) instead of telling Claude to load it always.
        self.assertIn("that a SessionStart hook summarizes", frontmatter)
        self.assertNotIn("Use alongside", frontmatter)
        self.assertIn(PRECEDENCE, text)
        self.assertNotIn('"Complete code in every step"', text)


if __name__ == "__main__":
    unittest.main()
