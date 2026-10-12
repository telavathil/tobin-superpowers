"""Tests for the promote-skill workflow: skill contract, plugin integration,
and an end-to-end dry run with the synthetic diagram-as-code skill in both
modes. No real work skill is ever used.

Run: python3 -m unittest discover -s tests -v
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import promote_helpers as H  # noqa: E402

VP = H.load_script("validate_portable_skill", H.VALIDATOR)
IP = H.load_script("import_portable_skill", H.IMPORTER)
SKILL_MD = os.path.join(H.REPO_ROOT, "skills", "promote-skill", "SKILL.md")
NAME = "diagram-as-code"

SAFETY_BOUNDARIES = (
    "Automatically scan unrelated directories for skills.",
    "Synchronize work and personal repositories.",
    "Upload source files to GitHub without explicit authorization.",
    "Copy secrets, internal URLs, or confidential examples into personal artifacts.",
    "Assume company-created material belongs to the user.",
    "Modify the original source skill.",
    "Execute untrusted scripts without approval.",
    "Never execute untrusted candidate scripts simply because they are listed in the manifest.",
    "Overwrite existing skills silently.",
    "Automatically commit, push, publish, or open a PR.",
    "Modify official Superpowers skills.",
    "Do not claim that automated checks establish legal ownership or guarantee confidentiality.",
)
LIFECYCLE = ("Discover", "Assess", "Design", "Prepare", "Validate", "Review", "Approve", "Guided Import")
# Planted in the synthetic source; none may reach a candidate.
PLANTED = ("examplecorp", "Example Corp", "/Users/jdoe", "jdoe", ".npmrc", "registry=",
           "internal use only", "arch-review")


def flat(text):
    return " ".join(text.split())


def fenced_block(text, language):
    match = re.search(r"^```%s\n(.*?)^```" % language, text, re.M | re.S)
    return match.group(1)


class SkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = H.read(SKILL_MD)
        cls.frontmatter = cls.text.split("---\n")[1]

    def test_frontmatter(self):
        self.assertIn("name: promote-skill\n", self.frontmatter)
        self.assertIn("disable-model-invocation: true\n", self.frontmatter)
        self.assertRegex(self.frontmatter, r"description: \S")
        self.assertNotIn("allowed-tools", self.frontmatter)

    def test_single_file_skill(self):
        self.assertEqual(os.listdir(os.path.dirname(SKILL_MD)), ["SKILL.md"])

    def test_safety_boundaries_are_stated(self):
        text = flat(self.text)
        for boundary in SAFETY_BOUNDARIES:
            with self.subTest(boundary=boundary[:40]):
                self.assertIn(boundary.rstrip("."), text)

    def test_clean_room_offer(self):
        self.assertIn("## When Permission Is Unclear", self.text)
        self.assertIn("clean-room implementation", flat(self.text))

    def test_two_modes(self):
        self.assertIn("**Source mode**", self.text)
        self.assertIn("**Personal mode**", self.text)

    def test_lifecycle_order(self):
        positions = [self.text.index("### %d. %s" % (i, step)) for i, step in enumerate(LIFECYCLE, 1)]
        self.assertEqual(positions, sorted(positions))

    def test_staging_layout(self):
        for entry in ("skill-promotion/", "manifest.json", "REVIEW.md", "skill/", "SKILL.md",
                      "references/", "scripts/", "tests/"):
            with self.subTest(entry=entry):
                self.assertIn(entry, self.text)

    def test_manifest_template_matches_validator(self):
        manifest = json.loads(fenced_block(self.text, "json"))
        self.assertEqual(tuple(manifest), VP.MANIFEST_KEYS)
        self.assertEqual(VP.check_manifest(manifest), [])
        self.assertEqual(manifest["status"], "draft")
        self.assertEqual(manifest["approval"], {"approved_by_user": False, "digest": None,
                                                "transfer_authorized": False,
                                                "publication_authorized": False})

    def test_review_template_matches_validator(self):
        review = fenced_block(self.text, "markdown")
        headings = tuple(re.findall(r"^## (.+)$", review, re.M))
        self.assertEqual(headings, VP.REVIEW_SECTIONS)
        manifest = json.loads(fenced_block(self.text, "json"))
        self.assertEqual(VP.check_review(review, manifest), [])

    def test_script_references_exist(self):
        scripts = set(re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/scripts/([\w.-]+)", self.text))
        self.assertEqual(scripts, {"validate-portable-skill.py", "import-portable-skill.py"})
        for name in scripts:
            self.assertTrue(os.path.isfile(os.path.join(H.SCRIPTS, name)))

    def test_approval_and_transfer_are_separate(self):
        text = flat(self.text)
        self.assertIn("transfer authorization, a separate confirmation", text)
        self.assertIn("Approval does not imply publication permission", text)
        self.assertIn("A passing validator never sets approval", text)

    def test_import_stops_before_commit(self):
        text = flat(self.text)
        self.assertIn("Stop. Do not commit, push, or open a pull request", text)
        self.assertIn("do not change versions or release metadata unless the user explicitly asks", text)
        self.assertIn("If the destination is unavailable, keep the candidate", text)

    def test_limitations_disclaim_permission(self):
        self.assertIn("Portability does not establish permission to reuse employer-owned material",
                      flat(self.text))

    def test_skill_passes_portability_scan(self):
        found = [f for f in VP.validate_path(os.path.dirname(SKILL_MD)) if f.rule != "name"]
        self.assertEqual(found, [])


class IntegrationTests(unittest.TestCase):
    def test_hooks_unchanged(self):
        hooks = H.read_json(os.path.join(H.REPO_ROOT, "hooks", "hooks.json"))["hooks"]
        self.assertEqual(set(hooks), {"SessionStart", "PreToolUse", "PostToolUse"})
        args = sorted(a for groups in hooks.values() for g in groups for h in g["hooks"] for a in h["args"])
        self.assertEqual(args, ["${CLAUDE_PLUGIN_ROOT}/scripts/ask-new-package.py",
                                "${CLAUDE_PLUGIN_ROOT}/scripts/inject-plan-standards.py",
                                "${CLAUDE_PLUGIN_ROOT}/scripts/inject-plan-standards.py",
                                "${CLAUDE_PLUGIN_ROOT}/scripts/session-context.py",
                                "${CLAUDE_PLUGIN_ROOT}/scripts/validate-plan-hook.py",
                                "1", "2"])

    def test_session_context_does_not_mention_promotion(self):
        out = subprocess.run([sys.executable, os.path.join(H.SCRIPTS, "session-context.py")],
                             input='{"source": "startup"}', capture_output=True, text=True,
                             encoding="utf-8", check=True)
        self.assertNotIn("promote", out.stdout.lower())

    def test_existing_skills_still_present(self):
        for skill in ("hybrid-planning", "html-companion"):
            with self.subTest(skill=skill):
                self.assertTrue(os.path.isfile(os.path.join(H.REPO_ROOT, "skills", skill, "SKILL.md")))

    def test_ci_discovers_new_tests(self):
        workflow = H.read(os.path.join(H.REPO_ROOT, ".github", "workflows", "ci.yml"))
        self.assertIn("unittest discover -s tests", workflow)
        tests_dir = os.path.join(H.REPO_ROOT, "tests")
        for name in ("test_validate_portable_skill.py", "test_import_portable_skill.py", "test_promote_skill.py"):
            with self.subTest(name=name):
                self.assertTrue(os.path.isfile(os.path.join(tests_dir, name)))

    @unittest.skipUnless(shutil.which("claude"), "claude CLI not installed")
    def test_plugin_validation_passes(self):
        for target in (".", os.path.join(".claude-plugin", "plugin.json")):
            with self.subTest(target=target):
                run = subprocess.run([shutil.which("claude"), "plugin", "validate", "--strict", target],
                                     cwd=H.REPO_ROOT, capture_output=True, text=True, timeout=300)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


class EndToEndTests(unittest.TestCase):
    """Synthetic diagram-as-code skill, promoted in both modes."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.fixture_before = H.tree_hashes(H.FIXTURES)
        self.addCleanup(lambda: self.assertEqual(H.tree_hashes(H.FIXTURES), self.fixture_before))
        # The work skill, with a credential planted at runtime.
        self.source = os.path.join(self.tmp, "work", "diagram-as-code")
        shutil.copytree(H.SOURCE_SKILL, self.source)
        self.secret = H.fake_secrets()["github"]
        with open(os.path.join(self.source, "scripts", "check_mermaid.py"), "a", encoding="utf-8") as f:
            f.write("\nPREVIEW_TOKEN = \"%s\"\n" % self.secret)
        self.deny = os.path.join(self.tmp, "private", "deny-terms.txt")
        H.write(self.deny, "Example Corp\nexamplecorp\njdoe\n")

    def prepare(self, mode):
        """What Claude writes in Prepare: a fresh candidate in a new staging folder."""
        staging = H.copy_candidate(os.path.join(self.tmp, mode))
        manifest = H.read_json(os.path.join(staging, "manifest.json"))
        H.write_json(os.path.join(staging, "manifest.json"), dict(manifest, mode=mode))
        return staging

    def assert_clean(self, staging):
        for rel, _ in H.tree_hashes(staging).items():
            text = H.read(os.path.join(staging, *rel.split("/")))
            for planted in PLANTED + (self.secret,):
                with self.subTest(file=rel, planted=planted[:12]):
                    self.assertNotIn(planted.lower(), text.lower())
        deny_terms = VP.load_deny_terms(self.deny)
        self.assertEqual(VP.validate_path(staging, deny_terms), [])

    def run_candidate_tests(self, staging):
        # Trusted synthetic fixture: running it here stands in for the user's
        # approval to run validation_commands in step 5.
        run = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                             cwd=os.path.join(staging, "skill"), capture_output=True, text=True,
                             env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_source_mode_assess_flags_and_preserves_source(self):
        before = H.tree_hashes(self.source)
        run = subprocess.run([sys.executable, H.VALIDATOR, self.source, "--deny-terms", self.deny, "--json"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(run.returncode, 1)
        self.assertNotIn(self.secret, run.stdout + run.stderr)
        self.assertNotIn("jdoe", run.stdout.replace("/Users/jdoe", ""))
        found = {f["rule"] for f in json.loads(run.stdout)["findings"]}
        self.assertTrue({"absolute-path", "internal-url", "credential", "company-config",
                         "confidential-marker", "deny-term"} <= found, found)
        self.assertEqual(H.tree_hashes(self.source), before)

    @unittest.skipIf(os.environ.get(IP.NESTED_ENV), "nested run inside an import check")
    def test_source_mode_end_to_end(self):
        source_before = H.tree_hashes(self.source)
        staging = self.prepare("source")
        self.assert_clean(staging)
        self.run_candidate_tests(staging)

        checkout = H.make_checkout(self.tmp)
        head, commits = H.head_commit(checkout), H.commit_count(checkout)
        self.assertFalse(IP.plan_import(staging, checkout).ok)       # draft: refused

        H.approve(staging, VP, transfer=True, publication=False)
        self.assertEqual(VP.validate_path(staging), [])
        plan = IP.plan_import(staging, checkout)
        self.assertTrue(plan.ok, plan.refusals)
        result = subprocess.run([sys.executable, H.IMPORTER, staging, "--dest", checkout, "--apply", "--json"],
                                capture_output=True, text=True, encoding="utf-8")
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, json.dumps(data["checks"], indent=2)[-3000:])
        statuses = {c["name"]: c["status"] for c in data["checks"]}
        self.assertEqual(statuses["candidate validation"], "passed")
        self.assertEqual(statuses["repository tests"], "passed")
        self.assertIn(statuses["plugin validation"], ("passed", "skipped"))

        target = os.path.join(checkout, "skills", NAME)
        self.assertEqual(H.tree_hashes(target), H.tree_hashes(os.path.join(staging, "skill")))
        self.assertEqual((H.head_commit(checkout), H.commit_count(checkout)), (head, commits))
        self.assertEqual(H.git(checkout, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip(),
                         "promote-skill/" + NAME)
        self.assertEqual(H.tree_hashes(self.source), source_before)

    def test_personal_mode_end_to_end(self):
        description = H.read(H.PERSONAL_DESCRIPTION)
        for planted in PLANTED:
            self.assertNotIn(planted.lower(), description.lower())
        staging = self.prepare("personal")
        self.assert_clean(staging)
        self.run_candidate_tests(staging)
        self.assertEqual(H.read_json(os.path.join(staging, "manifest.json"))["mode"], "personal")

        H.approve(staging, VP, transfer=False)
        checkout = H.make_checkout(self.tmp)
        self.assertFalse(IP.plan_import(staging, checkout).ok)        # no transfer authorization
        H.approve(staging, VP, transfer=True)
        plan = IP.plan_import(staging, checkout)
        self.assertTrue(plan.ok, plan.refusals)
        result = IP.apply_import(plan, run_checks=False)
        self.assertTrue(result.ok, result.problems)
        self.assertEqual(sorted(result.copied), sorted(plan.files))
        self.assertEqual(VP.validate_path(plan.target), [])


if __name__ == "__main__":
    unittest.main()
