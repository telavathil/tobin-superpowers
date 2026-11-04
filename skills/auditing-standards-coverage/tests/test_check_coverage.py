import os, pathlib, subprocess, sys, tempfile, unittest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "check-coverage.py"

STANDARD = """# Naming
- Use **descriptive** names.
- Avoid `abbreviations`.

```
- not a rule
```
"""


def run(*args):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True)


class CheckCoverageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.std = self.tmp / "standards"
        self.std.mkdir()
        (self.std / "naming.md").write_text(STANDARD)
        self.plan = self.tmp / "plan.md"
        # plan is older than the standard unless a test says otherwise
        os.utime(self.std / "naming.md", (2_000_000_000, 2_000_000_000))

    def test_all_rules_present(self):
        self.plan.write_text("Rules:\n- Use descriptive   names.\n- Avoid abbreviations.\n")
        os.utime(self.plan, (2_100_000_000, 2_100_000_000))
        r = run(str(self.plan), str(self.std))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("naming: 2/2 verbatim\n", r.stdout)
        self.assertNotIn("NEWER", r.stdout)
        self.assertNotIn("not a rule", r.stdout)

    def test_missing_rule_and_newer_standard(self):
        self.plan.write_text("- Use descriptive names.\n")
        os.utime(self.plan, (1_900_000_000, 1_900_000_000))
        r = run(str(self.plan), str(self.std))
        self.assertEqual(r.returncode, 1)
        self.assertIn("naming: 1/2 verbatim (STANDARD NEWER THAN PLAN)", r.stdout)
        self.assertIn("MISSING: Avoid `abbreviations`.", r.stdout)
        self.assertIn("TOTAL: 1/2", r.stdout)

    def test_requires_standards_dir(self):
        self.plan.write_text("x")
        r = run(str(self.plan))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("Usage", r.stderr)


if __name__ == "__main__":
    unittest.main()
