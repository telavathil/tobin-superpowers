"""Tests for scripts/validate-html-companion.py.

Run: python3 -m unittest discover -s tests -v
"""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "validate-html-companion.py")
COMPANIONS = os.path.join(REPO_ROOT, "tests", "fixtures", "companions")
PLAN_MD = os.path.join(COMPANIONS, "plans", "2026-01-01-demo.md")
PLAN_HTML = os.path.join(COMPANIONS, "plans", "2026-01-01-demo.html")
REVIEW_MD = os.path.join(COMPANIONS, "reviews", "2026-01-01-demo-review.md")
REVIEW_HTML = os.path.join(COMPANIONS, "reviews", "2026-01-01-demo-review.html")
EXTERNAL = os.path.join(COMPANIONS, "plans", "external-assets.html")
MISSING = os.path.join(COMPANIONS, "plans", "missing-structure.html")
DUMP = os.path.join(COMPANIONS, "plans", "markdown-dump.html")


def load_module():
    spec = importlib.util.spec_from_file_location("validate_html_companion", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VH = load_module()


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def rules(findings, severity=None):
    return {f.rule for f in findings if severity is None or f.severity == severity}


def run_cli(*args):
    return subprocess.run([sys.executable, SCRIPT, *args],
                          capture_output=True, text=True, timeout=10)


def write(tmp, name, text):
    path = os.path.join(tmp, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


class ValidCompanionTests(unittest.TestCase):
    def test_valid_plan_companion_is_clean(self):
        self.assertEqual(VH.validate_file(PLAN_HTML, source=PLAN_MD), [])

    def test_valid_review_companion_is_clean(self):
        self.assertEqual(VH.validate_file(REVIEW_HTML, source=REVIEW_MD), [])

    def test_valid_without_source_finds_sibling(self):
        self.assertEqual(VH.validate_file(PLAN_HTML), [])

    def test_data_uri_and_anchor_links_allowed(self):
        text = read(PLAN_HTML).replace(
            "<h2 id=\"tasks\">Tasks</h2>",
            '<img src="data:image/png;base64,iVBORw0KGgo=" alt="x">'
            '<a href="#tasks">jump</a><a href="https://example.com/pr/1">PR</a>'
            '<h2 id="tasks">Tasks</h2>')
        self.assertEqual(rules(VH.validate_text(text, html_path=PLAN_HTML)), set())


class ExternalResourceTests(unittest.TestCase):
    def setUp(self):
        self.findings = VH.validate_file(EXTERNAL)
        self.external = [f for f in self.findings if f.rule == "external-resource"]

    def test_each_external_reference_is_an_error(self):
        messages = " | ".join(f.message for f in self.external)
        for needle in ("https://cdn.example.com/x.css", "https://cdn.example.com/x.js",
                       "fonts.googleapis.com", "@font-face", "logo.png", "bg.png"):
            with self.subTest(needle=needle):
                self.assertIn(needle, messages)
        self.assertTrue(all(f.severity == "error" for f in self.external))

    def test_data_uri_image_not_flagged(self):
        self.assertNotIn("data:image", " ".join(f.message for f in self.external))

    def test_external_findings_have_lines(self):
        self.assertTrue(all(isinstance(f.line, int) and f.line > 0 for f in self.external))

    def test_other_external_forms(self):
        cases = {
            "base": '<base href="https://x.example/">',
            "iframe": '<iframe src="https://x.example/"></iframe>',
            "object": '<object data="chart.svg"></object>',
            "srcset": '<img src="data:image/png;base64,AA==" srcset="big.png 2x">',
            "svg image": '<svg><image href="pic.png"/></svg>',
            "protocol-relative": '<script src="//cdn.example.com/a.js"></script>',
            "relative stylesheet": '<link rel="stylesheet" href="style.css">',
            "icon": '<link rel="icon" href="favicon.ico">',
        }
        for name, snippet in cases.items():
            with self.subTest(case=name):
                text = read(PLAN_HTML).replace("<h2 id=\"tasks\">", snippet + "<h2 id=\"tasks\">")
                self.assertIn("external-resource",
                              rules(VH.validate_text(text, html_path=PLAN_HTML), "error"))


class StructureTests(unittest.TestCase):
    def test_missing_structure_errors(self):
        found = rules(VH.validate_file(MISSING), "error")
        for rule in ("doctype", "charset", "title", "header", "footer-source"):
            with self.subTest(rule=rule):
                self.assertIn(rule, found)

    def test_missing_structure_warnings(self):
        found = rules(VH.validate_file(MISSING), "warning")
        self.assertIn("script", found)
        self.assertIn("viewport", found)

    def test_header_needs_companion_label_and_date(self):
        for old, new in (("Companion to the implementation plan", "A page"),
                         (" · 2026-01-01", "")):
            with self.subTest(remove=old):
                text = read(PLAN_HTML).replace(old, new)
                self.assertIn("header", rules(VH.validate_text(text, html_path=PLAN_HTML), "error"))

    def test_absolute_footer_path_is_error(self):
        text = read(PLAN_HTML).replace(
            "tests/fixtures/companions/plans/2026-01-01-demo.md",
            "/Users/someone/repo/tests/fixtures/companions/plans/2026-01-01-demo.md")
        self.assertIn("footer-source", rules(VH.validate_text(text, html_path=PLAN_HTML), "error"))

    def test_footer_pointing_at_other_markdown_is_error(self):
        text = read(PLAN_HTML).replace("2026-01-01-demo.md</code>", "other.md</code>")
        found = VH.validate_text(text, html_path=PLAN_HTML, source_path=PLAN_MD)
        self.assertIn("footer-source", rules(found, "error"))

    def test_filename_must_match_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = write(tmp, "plans/renamed.html", read(PLAN_HTML))
            md = write(tmp, "plans/2026-01-01-demo.md", read(PLAN_MD))
            self.assertIn("filename", rules(VH.validate_file(html, source=md), "error"))

    def test_missing_sibling_markdown_is_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = write(tmp, "plans/2026-01-01-demo.html", read(PLAN_HTML))
            findings = VH.validate_file(html)
            self.assertIn("filename", rules(findings, "warning"))
            self.assertNotIn("filename", rules(findings, "error"))


class AntiPatternTests(unittest.TestCase):
    def test_markdown_dump_is_warning(self):
        findings = VH.validate_file(DUMP)
        self.assertIn("markdown-dump", rules(findings, "warning"))
        self.assertNotIn("markdown-dump", rules(findings, "error"))

    def test_short_code_block_is_not_a_dump(self):
        text = read(PLAN_HTML).replace(
            "<h2 id=\"tasks\">", "<pre><code>python3 -m unittest -v</code></pre><h2 id=\"tasks\">")
        self.assertNotIn("markdown-dump", rules(VH.validate_text(text, html_path=PLAN_HTML)))

    def test_type_structure_warnings(self):
        plan = read(PLAN_HTML).replace('class="checklist"', 'class="tasks"')
        self.assertIn("type-structure", rules(VH.validate_text(plan, html_path=PLAN_HTML), "warning"))
        review = read(REVIEW_HTML).replace('class="toc"', 'class="nav"')
        self.assertIn("type-structure", rules(VH.validate_text(review, html_path=REVIEW_HTML), "warning"))

    def test_type_structure_suggestion_points_at_skill_section(self):
        plan = read(PLAN_HTML).replace('class="checklist"', 'class="tasks"')
        finding = [f for f in VH.validate_text(plan, html_path=PLAN_HTML) if f.rule == "type-structure"][0]
        self.assertIn("Companion: Implementation Plan", finding.suggestion)
        self.assertNotIn("references/", finding.suggestion)

    def test_unknown_type_has_no_type_structure_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = write(tmp, "notes/2026-01-01-demo.html",
                         read(PLAN_HTML).replace('class="checklist"', 'class="tasks"'))
            write(tmp, "notes/2026-01-01-demo.md", read(PLAN_MD))
            self.assertNotIn("type-structure", rules(VH.validate_file(html)))


class CliTests(unittest.TestCase):
    def test_valid_exits_0(self):
        result = run_cli(PLAN_HTML, "--source", PLAN_MD)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 errors, 0 warnings", result.stdout)

    def test_invalid_exits_1_with_locations(self):
        result = run_cli(EXTERNAL)
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, r"external-assets\.html:\d+: error \[external-resource\]")
        self.assertIn("fix:", result.stdout)

    def test_warnings_only_exits_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            rel = os.path.relpath(os.path.dirname(PLAN_MD), REPO_ROOT)  # matches the footer path
            html = write(tmp, os.path.join(rel, "2026-01-01-demo.html"), read(DUMP))
            md = write(tmp, os.path.join(rel, "2026-01-01-demo.md"), read(PLAN_MD))
            result = run_cli(html, "--source", md)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("warning [markdown-dump]", result.stdout)
        self.assertNotIn("error [", result.stdout)

    def test_json_output(self):
        data = json.loads(run_cli(MISSING, "--json").stdout)
        self.assertGreater(data["summary"]["errors"], 0)
        self.assertEqual(set(data["findings"][0]), {"rule", "severity", "line", "message", "suggestion"})

    def test_invalid_invocations_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = write(tmp, "bad.html", "")
            with open(binary, "wb") as f:
                f.write(b"\xff\xfe\x00bad")
            cases = {
                "no args": (),
                "missing file": (os.path.join(tmp, "nope.html"),),
                "directory": (tmp,),
                "not utf-8": (binary,),
                "missing source": (PLAN_HTML, "--source", os.path.join(tmp, "nope.md")),
            }
            for name, args in cases.items():
                with self.subTest(case=name):
                    result = run_cli(*args)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_never_modifies_html_or_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in os.listdir(os.path.join(COMPANIONS, "plans")):
                shutil.copy(os.path.join(COMPANIONS, "plans", name), tmp)
            paths = sorted(os.path.join(tmp, n) for n in os.listdir(tmp))
            before = {p: (sha256(p), os.stat(p).st_mtime_ns) for p in paths}
            for p in paths:
                if p.endswith(".html"):
                    run_cli(p)
                    run_cli(p, "--json", "--source", os.path.join(tmp, "2026-01-01-demo.md"))
            after = {p: (sha256(p), os.stat(p).st_mtime_ns) for p in paths}
            self.assertEqual(before, after)
            self.assertEqual(sorted(os.listdir(tmp)), [os.path.basename(p) for p in paths])


if __name__ == "__main__":
    unittest.main()
