"""Tests for scripts/import-portable-skill.py.

Every destination is a throwaway git checkout under a temporary folder; no test
touches this repository's own git state.

Run: python3 -m unittest discover -s tests -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import promote_helpers as H  # noqa: E402

VP = H.load_script("validate_portable_skill", H.VALIDATOR)
IP = H.load_script("import_portable_skill", H.IMPORTER)
NAME = "diagram-as-code"
BRANCH = "promote-skill/" + NAME


def run_cli(*args):
    return subprocess.run([sys.executable, H.IMPORTER, *args], capture_output=True, text=True,
                          encoding="utf-8")


class ImportCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.mkdtemp()
        cls.baseline = H.make_checkout(cls.base, "baseline")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, ignore_errors=True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.staging = H.copy_candidate(self.tmp)
        self.dest = os.path.join(self.tmp, "checkout")
        shutil.copytree(self.baseline, self.dest, symlinks=True)
        self.target = os.path.join(self.dest, "skills", NAME)

    def approve(self, **kwargs):
        return H.approve(self.staging, VP, **kwargs)

    def plan(self, **kwargs):
        return IP.plan_import(self.staging, self.dest, **kwargs)

    def assert_refused(self, plan, fragment):
        self.assertFalse(plan.ok)
        self.assertTrue(any(fragment in r for r in plan.refusals), plan.refusals)

    def current_branch(self, cwd=None):
        return H.git(cwd or self.dest, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


class ApprovalGateTests(ImportCase):
    def test_unapproved_candidate_is_refused(self):
        self.assert_refused(self.plan(), "not approved")

    def test_blocked_candidate_is_refused(self):
        self.approve(status="blocked", transfer=False)
        self.assert_refused(self.plan(), "blocked")

    def test_needs_changes_candidate_is_refused(self):
        self.approve(status="needs-changes", transfer=False)
        self.assert_refused(self.plan(), "needs-changes")

    def test_missing_transfer_authorization_is_refused(self):
        self.approve(transfer=False)
        self.assert_refused(self.plan(), "transfer")

    def test_approval_does_not_imply_publication(self):
        self.approve(transfer=True, publication=False)
        plan = self.plan()
        self.assertTrue(plan.ok, plan.refusals)
        self.assertFalse(plan.publication_authorized)
        self.assertIn("publication is not authorized", IP.format_plan(plan).lower())

    def test_change_after_approval_is_refused(self):
        self.approve()
        with open(os.path.join(self.staging, "skill", "SKILL.md"), "a", encoding="utf-8") as f:
            f.write("\nEdited after approval.\n")
        self.assert_refused(self.plan(), "digest-mismatch")

    def test_approval_flag_alone_is_not_enough(self):
        manifest = H.read_json(os.path.join(self.staging, "manifest.json"))
        manifest["approval"]["transfer_authorized"] = True
        manifest["approval"]["approved_by_user"] = True
        H.write_json(os.path.join(self.staging, "manifest.json"), manifest)
        self.assertFalse(self.plan().ok)


class DestinationTests(ImportCase):
    def test_plan_targets_skills_name_and_changes_nothing(self):
        self.approve()
        before = H.tree_hashes(self.dest)
        plan = self.plan()
        self.assertTrue(plan.ok, plan.refusals)
        self.assertEqual(os.path.realpath(plan.target), os.path.realpath(self.target))
        self.assertEqual(plan.branch, BRANCH)
        self.assertEqual(plan.files, H.read_json(os.path.join(self.staging, "manifest.json"))["files"])
        self.assertEqual(H.tree_hashes(self.dest), before)
        self.assertEqual(self.current_branch(), "main")

    def test_existing_skill_is_not_overwritten_without_approval(self):
        self.approve()
        H.write(os.path.join(self.target, "SKILL.md"), "---\nname: diagram-as-code\ndescription: old\n---\n")
        H.git(self.dest, "add", "-A")
        H.git(self.dest, "commit", "-q", "-m", "old skill")
        self.assert_refused(self.plan(), "already exists")
        plan = self.plan(allow_overwrite=True)
        self.assertTrue(plan.ok, plan.refusals)
        IP.apply_import(plan, run_checks=False)
        self.assertEqual(H.read(os.path.join(self.target, "SKILL.md")),
                         H.read(os.path.join(self.staging, "skill", "SKILL.md")))

    def test_builtin_skills_cannot_be_replaced(self):
        for name in ("hybrid-planning", "writing-plans"):
            with self.subTest(name=name):
                manifest = H.read_json(os.path.join(H.CANDIDATE, "manifest.json"))
                H.write_json(os.path.join(self.staging, "manifest.json"), dict(manifest, name=name))
                skill_md = H.read(os.path.join(H.CANDIDATE, "skill", "SKILL.md"))
                H.write(os.path.join(self.staging, "skill", "SKILL.md"),
                        skill_md.replace("name: " + NAME, "name: " + name))
                self.approve()
                self.assertFalse(self.plan(allow_overwrite=True).ok)

    def test_dirty_worktree_is_refused_and_left_alone(self):
        self.approve()
        readme = os.path.join(self.dest, "README.md")
        H.write(readme, H.read(readme) + "\nlocal edit\n")
        H.write(os.path.join(self.dest, "notes.txt"), "untracked\n")
        before = H.tree_hashes(self.dest)
        self.assert_refused(self.plan(), "uncommitted")
        self.assertEqual(run_cli(self.staging, "--dest", self.dest, "--apply").returncode, 1)
        self.assertEqual(H.tree_hashes(self.dest), before)
        self.assertEqual(self.current_branch(), "main")

    def test_dirty_worktree_with_separate_worktree(self):
        self.approve()
        readme = os.path.join(self.dest, "README.md")
        H.write(readme, H.read(readme) + "\nlocal edit\n")
        before = H.tree_hashes(self.dest)
        tree = os.path.join(self.tmp, "promote-tree")
        plan = self.plan(worktree=tree)
        self.assertTrue(plan.ok, plan.refusals)
        IP.apply_import(plan, run_checks=False)
        self.assertEqual(H.tree_hashes(self.dest), before)
        self.assertEqual(self.current_branch(), "main")
        self.assertEqual(self.current_branch(tree), BRANCH)
        self.assertTrue(os.path.isfile(os.path.join(tree, "skills", NAME, "SKILL.md")))
        self.assertNotIn("local edit", H.read(os.path.join(tree, "README.md")))

    def test_existing_branch_is_refused(self):
        self.approve()
        H.git(self.dest, "branch", BRANCH)
        self.assert_refused(self.plan(), "branch")

    def test_not_a_tobin_superpowers_checkout(self):
        self.approve()
        other = os.path.join(self.tmp, "other")
        os.makedirs(other)
        H.git(other, "init", "-q", "-b", "main")
        plan = IP.plan_import(self.staging, other)
        self.assert_refused(plan, "tobin-superpowers")

    def test_subfolder_of_checkout_is_refused(self):
        self.approve()
        plan = IP.plan_import(self.staging, os.path.join(self.dest, "skills"))
        self.assert_refused(plan, "root")

    def test_unavailable_destination_keeps_candidate(self):
        self.approve()
        before = H.tree_hashes(self.staging)
        result = run_cli(self.staging, "--dest", os.path.join(self.tmp, "nowhere"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("kept", result.stderr)
        self.assertIn(self.staging, result.stderr)
        self.assertEqual(H.tree_hashes(self.staging), before)


class TraversalAndSymlinkTests(ImportCase):
    def symlink(self, src, dst, directory=False):
        try:
            os.symlink(src, dst, target_is_directory=directory)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this platform")

    def test_manifest_traversal_is_refused(self):
        manifest = H.read_json(os.path.join(self.staging, "manifest.json"))
        manifest["files"].append("../manifest.json")
        H.write_json(os.path.join(self.staging, "manifest.json"), manifest)
        self.approve()
        self.assert_refused(self.plan(), "path-escape")

    def test_symlink_in_candidate_is_refused(self):
        outside = os.path.join(self.tmp, "secret.txt")
        H.write(outside, "outside\n")
        self.symlink(outside, os.path.join(self.staging, "skill", "references", "secret.txt"))
        manifest = H.read_json(os.path.join(self.staging, "manifest.json"))
        manifest["files"].append("references/secret.txt")
        H.write_json(os.path.join(self.staging, "manifest.json"), manifest)
        self.approve()
        self.assert_refused(self.plan(), "symlink")

    def test_symlinked_target_is_refused(self):
        self.approve()
        elsewhere = os.path.join(self.tmp, "elsewhere")
        os.makedirs(elsewhere)
        self.symlink(elsewhere, self.target, directory=True)
        H.git(self.dest, "add", "-A")
        H.git(self.dest, "commit", "-q", "-m", "link")
        self.assertFalse(self.plan(allow_overwrite=True).ok)
        self.assertEqual(os.listdir(elsewhere), [])

    def test_symlinked_skills_folder_is_refused(self):
        self.approve()
        skills = os.path.join(self.dest, "skills")
        moved = os.path.join(self.tmp, "real-skills")
        shutil.move(skills, moved)
        self.symlink(moved, skills, directory=True)
        H.git(self.dest, "add", "-A")
        H.git(self.dest, "commit", "-q", "-m", "link skills")
        self.assert_refused(self.plan(), "symbolic link")


class ApplyTests(ImportCase):
    def test_apply_copies_only_approved_files_without_committing(self):
        self.approve()
        bare = os.path.join(self.tmp, "remote.git")
        H.git(self.tmp, "init", "-q", "--bare", bare)
        H.git(self.dest, "remote", "add", "origin", bare)
        H.write(os.path.join(self.staging, "skill", "scripts", "__pycache__", "x.pyc"), "cache")
        head, commits = H.head_commit(self.dest), H.commit_count(self.dest)
        unrelated = H.tree_hashes(self.dest, skip=("skills/" + NAME,))
        staging_before = H.tree_hashes(self.staging)
        result = IP.apply_import(self.plan(), run_checks=False)
        self.assertTrue(result.ok, result.problems)
        copied = sorted(H.tree_hashes(self.target))
        self.assertEqual(copied, sorted(H.read_json(os.path.join(self.staging, "manifest.json"))["files"]))
        self.assertEqual(H.tree_hashes(self.dest, skip=("skills/" + NAME,)), unrelated)
        self.assertEqual(H.tree_hashes(self.staging), staging_before)
        self.assertEqual(self.current_branch(), BRANCH)
        self.assertEqual(H.head_commit(self.dest), head)
        self.assertEqual(H.commit_count(self.dest), commits)
        self.assertEqual(H.git(bare, "for-each-ref").stdout, "")
        status = H.git(self.dest, "status", "--porcelain", "--untracked-files=all").stdout
        self.assertTrue(all(line[3:].startswith("skills/" + NAME + "/") for line in status.splitlines()), status)
        self.assertEqual(VP.compute_digest(self.target),
                         H.read_json(os.path.join(self.staging, "manifest.json"))["approval"]["digest"])

    def test_cli_plans_by_default(self):
        self.approve()
        before = H.tree_hashes(self.dest)
        result = run_cli(self.staging, "--dest", self.dest)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("plan only", result.stdout.lower())
        self.assertEqual(H.tree_hashes(self.dest), before)
        data = json.loads(run_cli(self.staging, "--dest", self.dest, "--json").stdout)
        self.assertTrue(data["ok"])
        self.assertFalse(data["applied"])

    def test_script_never_commits_pushes_or_opens_prs(self):
        source = H.read(H.IMPORTER)
        for word in ('"commit"', '"push"', '"pull-request"', '"gh"', '"merge"', '"tag"'):
            with self.subTest(word=word):
                self.assertNotIn(word, source)

    @unittest.skipIf(os.environ.get(IP.NESTED_ENV), "nested run inside an import check")
    def test_apply_runs_validation_suite_and_reports(self):
        self.approve()
        result = run_cli(self.staging, "--dest", self.dest, "--apply", "--skip-plugin-validate", "--json")
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, json.dumps(data, indent=2)[-3000:])
        names = [c["name"] for c in data["checks"]]
        self.assertEqual(names, ["candidate validation", "repository tests", "plugin validation"])
        self.assertEqual([c["status"] for c in data["checks"]], ["passed", "passed", "skipped"])
        self.assertIn("not committed", "\n".join(data["next_steps"]).lower())


if __name__ == "__main__":
    unittest.main()
