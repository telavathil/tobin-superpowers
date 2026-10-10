"""Tests for scripts/validate-plan.py.

Run: python3 -m unittest discover -s tests -v
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "validate-plan.py")
FIXTURES = os.path.join(REPO_ROOT, "tests", "fixtures")
VALID = os.path.join(FIXTURES, "valid-plan.md")
INCOMPLETE = os.path.join(FIXTURES, "incomplete-plan.md")


def load_module():
    spec = importlib.util.spec_from_file_location("validate_plan", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VP = load_module()


def run_cli(*args):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        capture_output=True, text=True, timeout=10,
    )


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def keyed(findings):
    return {(f.rule, f.task) for f in findings}


def task(body, number=1, title="Thing"):
    """Build a one-task plan from a dedented body."""
    return "# Plan\n\n### Task %d: %s\n\n%s\n" % (number, title, textwrap.dedent(body).strip())


GOOD_TASK = """
    **Files:**
    - Modify: `src/app.py:10-20`
    - Test: `tests/test_app.py`

    **Interfaces:**
    - Produces: `greet(name: str) -> str`

    **Pattern to follow:** `src/util.py:5`

    - [ ] **Step 1: Write failing test**: `greet("Ann") == "Hi Ann"`
    - [ ] **Step 2: Implement** `greet` with an f-string.
    - [ ] **Step 3: Verify** `python3 -m unittest tests.test_app -v` → Expected: PASS
"""


class ValidPlanTests(unittest.TestCase):
    def test_fixture_has_no_errors_or_warnings(self):
        findings = VP.validate_text(open(VALID, encoding="utf-8").read())
        noisy = [f for f in findings if f.severity in ("error", "warning")]
        self.assertEqual(noisy, [], [f.message for f in noisy])

    def test_pseudocode_instead_of_complete_code_passes(self):
        # Task 2 of the valid fixture uses a pseudocode block and no real code.
        text = open(VALID, encoding="utf-8").read()
        self.assertIn("**Algorithm:**", text)
        self.assertNotIn("def count_syllables", text)
        self.assertEqual(VP.errors(VP.validate_text(text)), [])

    def test_concise_prose_steps_without_code_pass(self):
        self.assertEqual(VP.validate_text(task(GOOD_TASK)), [])

    def test_equivalent_formatting_is_accepted(self):
        body = """
            Files: create `src/app.py`; test in `tests/test_app.py`.

            Signatures: `greet(name: str) -> str`

            Follows the existing pattern in `src/util.py:5`.

            1. Add a test asserting `greet("Ann") == "Hi Ann"`.
            2. Implement `greet`.
            3. Run `pytest tests/test_app.py -q` (expect `1 passed`).
        """
        findings = VP.validate_text(task(body).replace("### Task 1:", "## Task 1 —"))
        self.assertEqual([f for f in findings if f.severity != "info"], [])

    def test_explicit_no_interface_and_no_pattern_accepted(self):
        body = GOOD_TASK.replace(
            "**Interfaces:**\n    - Produces: `greet(name: str) -> str`",
            "**Interfaces:** No new interfaces.",
        ).replace("**Pattern to follow:** `src/util.py:5`", "**Pattern to follow:** none")
        self.assertEqual(VP.validate_text(task(body)), [])


class MissingInformationTests(unittest.TestCase):
    def test_missing_interfaces_reported(self):
        body = GOOD_TASK.replace("**Interfaces:**\n    - Produces: `greet(name: str) -> str`\n", "")
        self.assertIn(("interfaces", 1), keyed(VP.errors(VP.validate_text(task(body)))))

    def test_missing_verification_reported(self):
        body = GOOD_TASK.replace(
            "- [ ] **Step 3: Verify** `python3 -m unittest tests.test_app -v` → Expected: PASS",
            "- [ ] **Step 3:** Commit.",
        )
        self.assertIn(("verification", 1), keyed(VP.errors(VP.validate_text(task(body)))))

    def test_command_without_expected_result_is_warning(self):
        body = GOOD_TASK.replace(" → Expected: PASS", "")
        findings = VP.validate_text(task(body))
        self.assertEqual(VP.errors(findings), [])
        self.assertIn(("expected-result", 1), keyed(findings))

    def test_missing_files_reported(self):
        body = GOOD_TASK.replace(
            "**Files:**\n    - Modify: `src/app.py:10-20`\n    - Test: `tests/test_app.py`\n", ""
        )
        self.assertIn(("files", 1), keyed(VP.errors(VP.validate_text(task(body)))))

    def test_inexact_path_is_warning(self):
        body = GOOD_TASK.replace("`src/app.py:10-20`", "`src/*.py`")
        self.assertIn(("inexact-path", 1), keyed(VP.validate_text(task(body))))

    def test_missing_steps_reported(self):
        body = GOOD_TASK.replace("- [ ] **Step 2: Implement** `greet` with an f-string.\n", "")
        body = body.replace("- [ ] **Step 1: Write failing test**: ", "Test: ")
        body = body.replace("- [ ] **Step 3: Verify** ", "Verify: ")
        self.assertIn(("steps", 1), keyed(VP.errors(VP.validate_text(task(body)))))

    def test_missing_test_cases_reported(self):
        body = GOOD_TASK.replace(': `greet("Ann") == "Hi Ann"`', " for greet.")
        self.assertIn(("tests", 1), keyed(VP.errors(VP.validate_text(task(body)))))

    def test_explicit_no_tests_with_reason_accepted(self):
        body = GOOD_TASK.replace(
            '- [ ] **Step 1: Write failing test**: `greet("Ann") == "Hi Ann"`',
            "- [ ] **Step 1:** No tests: documentation-only change.",
        )
        self.assertNotIn(("tests", 1), keyed(VP.validate_text(task(body))))

    def test_docs_only_task_without_tests_is_warning(self):
        body = GOOD_TASK.replace("`src/app.py:10-20`", "`docs/guide.md`").replace(
            "- Test: `tests/test_app.py`\n", "").replace(': `greet("Ann") == "Hi Ann"`', ".")
        findings = VP.validate_text(task(body))
        self.assertEqual(VP.errors(findings), [])
        self.assertIn(("tests", 1), keyed(findings))

    def test_code_task_without_tests_stays_error(self):
        body = GOOD_TASK.replace(': `greet("Ann") == "Hi Ann"`', ".")
        self.assertIn(("tests", 1), keyed(VP.errors(VP.validate_text(task(body)))))

    def test_explicit_no_files_accepted(self):
        body = GOOD_TASK.replace(
            "**Files:**\n    - Modify: `src/app.py:10-20`\n    - Test: `tests/test_app.py`",
            "**Files:** none (scratch only).")
        self.assertNotIn(("files", 1), keyed(VP.validate_text(task(body))))

    def test_missing_pattern_is_warning_only(self):
        body = GOOD_TASK.replace("**Pattern to follow:** `src/util.py:5`\n", "")
        findings = VP.validate_text(task(body))
        self.assertEqual(VP.errors(findings), [])
        self.assertIn(("pattern", 1), keyed(findings))

    def test_no_tasks_reported(self):
        findings = VP.validate_text("# Plan\n\nJust prose.\n")
        self.assertEqual([(f.rule, f.severity) for f in findings], [("no-tasks", "error")])


class PlaceholderTests(unittest.TestCase):
    def test_placeholders_are_errors(self):
        for phrase in ("TBD", "TODO", "FIXME", "implement later", "fill in the details",
                       "Write tests for the above"):
            with self.subTest(phrase=phrase):
                body = GOOD_TASK.replace("with an f-string.", "with an f-string. %s" % phrase)
                self.assertIn(("placeholder", 1), keyed(VP.errors(VP.validate_text(task(body)))))

    def test_vague_instructions_are_warnings(self):
        for phrase in ("handle edge cases", "add appropriate error handling",
                       "add validation", "similar to Task 1"):
            with self.subTest(phrase=phrase):
                body = GOOD_TASK.replace("with an f-string.", "and %s." % phrase)
                findings = VP.validate_text(task(body))
                self.assertIn(("vague-instruction", 1), keyed(findings))
                self.assertEqual(VP.errors(findings), [])

    def test_placeholders_inside_code_are_ignored(self):
        body = GOOD_TASK + '\n    ```python\n    # TODO stays in code\n    assert parse("TBD") is None\n    ```\n'
        self.assertEqual(VP.validate_text(task(body)), [])

    def test_mentions_of_placeholders_ignored(self):
        body = GOOD_TASK.replace(
            "with an f-string.", 'with an f-string; reject "TBD" values and strip TODO markers.')
        self.assertEqual(VP.validate_text(task(body)), [])

    def test_nested_fences_stay_code(self):
        nested = (
            "\n    ```markdown\n    Example:\n    ```bash\n    echo TODO\n    ```\n"
            "    Leave TBD here\n    ```\n"
        )
        self.assertEqual(VP.validate_text(task(GOOD_TASK + nested)), [])

    def test_placeholder_words_inside_identifiers_ignored(self):
        body = GOOD_TASK.replace("with an f-string.", "and update `todo_list` in `TODOS.md`.")
        self.assertEqual(VP.validate_text(task(body)), [])


class MultiTaskLocationTests(unittest.TestCase):
    def setUp(self):
        self.findings = VP.validate_text(open(INCOMPLETE, encoding="utf-8").read())
        self.by_key = {(f.rule, f.task): f for f in self.findings}

    def test_expected_findings_and_lines(self):
        expected = {
            ("interfaces", 1): ("error", 5),
            ("verification", 2): ("error", 17),
            ("placeholder", 2): ("error", 28),
            ("pattern", 3): ("warning", 30),
            ("verification", 3): ("error", 30),
            ("tests", 3): ("error", 30),
            ("vague-instruction", 3): ("warning", 37),
            ("placeholder", 3): ("error", 38),
        }
        for key, (severity, line) in expected.items():
            with self.subTest(key=key):
                self.assertIn(key, self.by_key)
                self.assertEqual(self.by_key[key].severity, severity)
                self.assertEqual(self.by_key[key].line, line)
        self.assertEqual(keyed(self.findings), set(expected))

    def test_every_finding_has_explanation_and_suggestion(self):
        for f in self.findings:
            with self.subTest(rule=f.rule, task=f.task):
                self.assertTrue(f.message)
                self.assertTrue(f.suggestion)
                self.assertIn(f.severity, ("error", "warning", "info"))

    def test_findings_sorted_by_line(self):
        lines = [f.line for f in self.findings]
        self.assertEqual(lines, sorted(lines))


class LongCodeTests(unittest.TestCase):
    def test_long_code_block_is_info_only(self):
        code = "\n".join("    x%d = %d" % (i, i) for i in range(45))
        body = GOOD_TASK + "\n    ```python\n" + code + "\n    ```\n"
        findings = VP.validate_text(task(body))
        self.assertEqual([(f.rule, f.severity) for f in findings], [("long-code", "info")])


class CliTests(unittest.TestCase):
    def test_valid_plan_exits_0(self):
        result = run_cli(VALID)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 errors", result.stdout)

    def test_incomplete_plan_exits_1_with_locations(self):
        result = run_cli(INCOMPLETE)
        self.assertEqual(result.returncode, 1)
        self.assertIn("incomplete-plan.md:28: error [placeholder] Task 2:", result.stdout)
        self.assertIn("fix:", result.stdout)

    def test_json_output(self):
        result = run_cli(INCOMPLETE, "--json")
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertEqual(data["summary"]["errors"], 6)
        first = data["findings"][0]
        self.assertEqual(
            set(first), {"rule", "severity", "line", "task", "message", "suggestion"}
        )

    def test_warnings_only_exits_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "plan.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(task(GOOD_TASK.replace("**Pattern to follow:** `src/util.py:5`\n", "")))
            result = run_cli(path)
        self.assertEqual(result.returncode, 0)
        self.assertIn("warning [pattern]", result.stdout)

    def test_invalid_invocations_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = os.path.join(tmp, "bad.md")
            with open(binary, "wb") as f:
                f.write(b"\xff\xfe\x00bad")
            cases = {
                "no args": (),
                "missing file": (os.path.join(tmp, "nope.md"),),
                "directory": (tmp,),
                "not utf-8": (binary,),
                "two paths": (VALID, INCOMPLETE),
            }
            for name, args in cases.items():
                with self.subTest(case=name):
                    result = run_cli(*args)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_location_note_outside_plan_directory(self):
        result = run_cli(VALID)
        self.assertIn("info [location]", result.stdout)

    def test_no_location_note_inside_plan_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            plans = os.path.join(tmp, "docs", "superpowers", "plans")
            os.makedirs(plans)
            path = os.path.join(plans, "p.md")
            with open(VALID, encoding="utf-8") as src, open(path, "w", encoding="utf-8") as dst:
                dst.write(src.read())
            result = run_cli(path)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("[location]", result.stdout)

    def test_source_markdown_never_modified(self):
        for path in (VALID, INCOMPLETE):
            with self.subTest(path=os.path.basename(path)):
                before = (sha256(path), os.stat(path).st_mtime_ns)
                run_cli(path)
                run_cli(path, "--json")
                VP.validate_file(path)
                self.assertEqual((sha256(path), os.stat(path).st_mtime_ns), before)


if __name__ == "__main__":
    unittest.main()
