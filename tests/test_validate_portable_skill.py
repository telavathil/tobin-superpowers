"""Tests for scripts/validate-portable-skill.py.

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


def rules(findings, severity=None):
    return {f.rule for f in findings if severity is None or f.severity == severity}


def run_cli(*args):
    return subprocess.run([sys.executable, H.VALIDATOR, *args], capture_output=True, text=True,
                          encoding="utf-8")


class TempStagingCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.staging = H.copy_candidate(self.tmp)
        self.skill = os.path.join(self.staging, "skill")
        self.skill_md = os.path.join(self.skill, "SKILL.md")
        self.manifest_path = os.path.join(self.staging, "manifest.json")

    def findings(self, **kwargs):
        return VP.validate_path(self.staging, **kwargs)

    def edit_manifest(self, **changes):
        manifest = H.read_json(self.manifest_path)
        manifest.update(changes)
        H.write_json(self.manifest_path, manifest)
        return manifest

    def add_file(self, rel, text, listed=True):
        H.write(os.path.join(self.skill, rel), text)
        if listed:
            manifest = H.read_json(self.manifest_path)
            manifest["files"].append(rel)
            H.write_json(self.manifest_path, manifest)


class CandidateStructureTests(TempStagingCase):
    def test_fixture_candidate_has_no_findings(self):
        self.assertEqual(self.findings(), [])

    def test_valid_frontmatter_passes_in_skill_only_mode(self):
        self.assertEqual(VP.validate_path(self.skill), [])

    def test_missing_skill_md(self):
        os.remove(self.skill_md)
        found = self.findings()
        self.assertIn("structure", rules(found, "error"))

    def test_missing_manifest_and_review(self):
        os.remove(self.manifest_path)
        os.remove(os.path.join(self.staging, "REVIEW.md"))
        messages = " ".join(f.message for f in self.findings() if f.rule == "structure")
        self.assertIn("manifest.json", messages)
        self.assertIn("REVIEW.md", messages)

    def test_missing_frontmatter_fields(self):
        H.write(self.skill_md, "---\nname: diagram-as-code\n---\n\n# Body\n")
        self.assertIn("frontmatter", rules(self.findings(), "error"))
        H.write(self.skill_md, "# No frontmatter\n")
        self.assertIn("frontmatter", rules(self.findings(), "error"))

    def test_missing_referenced_file(self):
        os.remove(os.path.join(self.skill, "references", "style.md"))
        found = self.findings()
        self.assertIn("reference", rules(found, "error"))
        self.assertIn("files", rules(found, "error"))

    def test_reference_through_plugin_root_is_resolved(self):
        os.remove(os.path.join(self.skill, "scripts", "check_mermaid.py"))
        messages = [f.message for f in self.findings() if f.rule == "reference"]
        self.assertTrue(any("scripts/check_mermaid.py" in m for m in messages), messages)

    def test_unlisted_file_is_an_error(self):
        self.add_file("references/extra.md", "# Extra\n", listed=False)
        self.assertIn("files", rules(self.findings(), "error"))

    def test_unexpected_top_level_entry(self):
        self.add_file("assets/logo.txt", "logo\n")
        self.assertIn("layout", rules(self.findings(), "error"))

    def test_invalid_or_unsafe_names(self):
        for bad in ("Diagram_As_Code", "../evil", "a" * 65, "", "-lead", "trail-", "x--y"):
            with self.subTest(name=bad):
                self.assertFalse(VP.valid_name(bad))
        for good in ("diagram-as-code", "mermaid2", "a"):
            with self.subTest(name=good):
                self.assertTrue(VP.valid_name(good))

    def test_name_rules_in_frontmatter_and_manifest(self):
        text = H.read(self.skill_md).replace("name: diagram-as-code", "name: Diagram_As_Code")
        H.write(self.skill_md, text)
        self.assertIn("name", rules(self.findings(), "error"))

    def test_name_mismatch_with_manifest(self):
        self.edit_manifest(name="other-name")
        self.assertIn("name", rules(self.findings(), "error"))

    def test_reserved_names_are_rejected(self):
        for reserved in ("writing-plans", "brainstorming", "hybrid-planning", "html-companion",
                         "promote-skill", "shared"):
            with self.subTest(name=reserved):
                text = H.read(os.path.join(H.CANDIDATE, "skill", "SKILL.md"))
                H.write(self.skill_md, text.replace("name: diagram-as-code", "name: " + reserved))
                self.edit_manifest(name=reserved)
                self.assertIn("name", rules(self.findings(), "error"))

    def test_manifest_path_escape(self):
        for bad in ("../outside.txt", "/etc/passwd", "C:\\Windows\\x", "references/../../x"):
            with self.subTest(entry=bad):
                manifest = H.read_json(os.path.join(H.CANDIDATE, "manifest.json"))
                manifest["files"].append(bad)
                H.write_json(self.manifest_path, manifest)
                self.assertIn("path-escape", rules(self.findings(), "error"))

    def test_reference_path_escape(self):
        H.write(self.skill_md, H.read(self.skill_md) + "\nSee [notes](../../notes.md).\n")
        self.assertIn("path-escape", rules(self.findings(), "error"))

    def test_symlink_is_rejected(self):
        target = os.path.join(self.tmp, "outside.md")
        H.write(target, "outside\n")
        link = os.path.join(self.skill, "references", "linked.md")
        try:
            os.symlink(target, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this platform")
        manifest = H.read_json(self.manifest_path)
        manifest["files"].append("references/linked.md")
        H.write_json(self.manifest_path, manifest)
        self.assertIn("symlink", rules(self.findings(), "error"))

    def test_symlinked_skill_dir_is_rejected(self):
        real = os.path.join(self.tmp, "real-skill")
        shutil.move(self.skill, real)
        try:
            os.symlink(real, self.skill, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this platform")
        self.assertIn("symlink", rules(self.findings(), "error"))

    def test_validator_never_modifies_candidate(self):
        before = H.tree_hashes(self.staging)
        self.findings()
        run_cli(self.staging, "--json")
        run_cli(self.staging, "--digest")
        self.assertEqual(H.tree_hashes(self.staging), before)


class ManifestTests(TempStagingCase):
    def test_invalid_json(self):
        H.write(self.manifest_path, "{not json")
        self.assertIn("manifest", rules(self.findings(), "error"))

    def test_schema_version_and_required_keys(self):
        manifest = H.read_json(self.manifest_path)
        for key in VP.MANIFEST_KEYS:
            with self.subTest(missing=key):
                broken = dict(manifest)
                del broken[key]
                H.write_json(self.manifest_path, broken)
                self.assertIn("manifest", rules(self.findings(), "error"))
        H.write_json(self.manifest_path, dict(manifest, schema_version=2))
        self.assertIn("manifest", rules(self.findings(), "error"))

    def test_enumerations(self):
        for key, value in (("mode", "work"), ("status", "shipped")):
            with self.subTest(key=key):
                H.write_json(self.manifest_path,
                             dict(H.read_json(os.path.join(H.CANDIDATE, "manifest.json")), **{key: value}))
                self.assertIn("manifest", rules(self.findings(), "error"))

    def test_manifest_must_not_carry_private_details(self):
        manifest = H.read_json(self.manifest_path)
        for field, value in (("description", "From /Users/jdoe/work/skills/diagram"),
                             ("description", "See https://wiki.examplecorp.internal/x"),
                             ("description", H.fake_secrets()["github"])):
            with self.subTest(value=value[:12]):
                H.write_json(self.manifest_path, dict(manifest, **{field: value}))
                self.assertIn("manifest-private", rules(self.findings(), "error"))

    def test_validation_commands_are_listed_not_run(self):
        marker = os.path.join(self.tmp, "ran")
        self.edit_manifest(validation_commands=["%s -c \"open(%r, 'w')\"" % (sys.executable, marker)])
        self.findings()
        run_cli(self.staging)
        self.assertFalse(os.path.exists(marker))


class PortabilityTests(TempStagingCase):
    def test_generic_skill_passes(self):
        self.assertEqual([f for f in self.findings() if f.severity != "info"], [])

    def test_absolute_paths(self):
        for path in ("/Users/jdoe/work/templates", "/home/jdoe/src", "C:\\Users\\jdoe\\docs",
                     "/Volumes/Work/share"):
            with self.subTest(path=path):
                H.write(self.skill_md, H.read(os.path.join(H.CANDIDATE, "skill", "SKILL.md"))
                        + "\nTemplates: %s\n" % path)
                self.assertIn("absolute-path", rules(self.findings()))

    def test_internal_urls(self):
        for url in ("https://wiki.examplecorp.internal/eng", "http://jira/browse/X-1",
                    "https://git.corp.example.com/team/repo", "http://10.1.2.3:8080/",
                    "http://192.168.0.5/admin", "git@git.examplecorp.internal:team/repo.git"):
            with self.subTest(url=url):
                H.write(self.skill_md, H.read(os.path.join(H.CANDIDATE, "skill", "SKILL.md"))
                        + "\nLink: %s\n" % url)
                self.assertIn("internal-url", rules(self.findings()))

    def test_public_and_loopback_urls_pass(self):
        H.write(self.skill_md, H.read(self.skill_md)
                + "\nhttps://mermaid.js.org/intro/ and http://localhost:8080/ and http://127.0.0.1/\n")
        self.assertNotIn("internal-url", rules(self.findings()))

    def test_credentials_flagged_without_printing_values(self):
        secrets = H.fake_secrets()
        H.write(os.path.join(self.skill, "references", "style.md"),
                H.read(os.path.join(self.skill, "references", "style.md"))
                + "\n".join(secrets.values()) + "\n")
        found = [f for f in self.findings() if f.rule == "credential"]
        self.assertGreaterEqual(len(found), len(secrets))
        self.assertTrue(all(f.severity == "error" for f in found))
        text_out = run_cli(self.staging)
        json_out = run_cli(self.staging, "--json")
        self.assertEqual(text_out.returncode, 1)
        for value in secrets.values():
            secret_part = value.split("'")[1] if "'" in value else value
            if "PRIVATE" in value:
                continue  # a header carries no secret material
            with self.subTest(kind=secret_part[:4]):
                for output in (text_out.stdout, text_out.stderr, json_out.stdout):
                    self.assertNotIn(secret_part, output)
                    self.assertNotIn(secret_part[4:16], output)
        self.assertIn("redacted", text_out.stdout)

    def test_placeholders_are_not_credentials(self):
        H.write(self.skill_md, H.read(self.skill_md)
                + "\napi_key = '<your-api-key>'\ntoken: ${GITHUB_TOKEN}\npassword = 'changeme'\n")
        self.assertNotIn("credential", rules(self.findings()))

    def test_company_config_and_confidential_markers(self):
        H.write(self.skill_md, H.read(self.skill_md)
                + "\nSet `registry=` in `.npmrc` to the Artifactory mirror.\n"
                  "Example Corp confidential - internal use only.\n")
        found = rules(self.findings(), "warning")
        self.assertIn("company-config", found)
        self.assertIn("confidential-marker", found)

    def test_deny_terms_from_external_file(self):
        terms = os.path.join(self.tmp, "deny.txt")
        H.write(terms, "# employer terms, kept outside the candidate\nExampleCorp\nproject-falcon\n")
        H.write(self.skill_md, H.read(self.skill_md) + "\nBuilt for Project-Falcon.\n")
        found = [f for f in self.findings(deny_terms=VP.load_deny_terms(terms)) if f.rule == "deny-term"]
        self.assertEqual(len(found), 1)
        self.assertNotIn("falcon", found[0].message.lower())
        cli = run_cli(self.staging, "--deny-terms", terms)
        self.assertEqual(cli.returncode, 1)
        self.assertNotIn("falcon", cli.stdout.lower())

    def test_missing_python_dependency(self):
        self.add_file("scripts/render.py", "import yaml\nimport json\nfrom check_mermaid import check\n")
        found = [f for f in self.findings() if f.rule == "dependency"]
        self.assertEqual(len(found), 1)
        self.assertIn("yaml", found[0].message)
        self.assertEqual(found[0].severity, "error")

    def test_declared_non_stdlib_dependency_is_advisory(self):
        self.add_file("scripts/render.py", "import yaml\n")
        manifest = H.read_json(self.manifest_path)
        manifest["requires"]["dependencies"].append("yaml (PyYAML)")
        H.write_json(self.manifest_path, manifest)
        found = rules(self.findings())
        self.assertNotIn("dependency", found)
        self.assertIn("unsupported-dependency", found)

    def test_source_fixture_is_flagged_but_untouched(self):
        before = H.tree_hashes(H.SOURCE_SKILL)
        found = rules(VP.validate_path(H.SOURCE_SKILL))
        for rule in ("absolute-path", "internal-url", "company-config", "confidential-marker"):
            with self.subTest(rule=rule):
                self.assertIn(rule, found)
        self.assertEqual(H.tree_hashes(H.SOURCE_SKILL), before)


class ReviewAndApprovalTests(TempStagingCase):
    def test_missing_review_section(self):
        review = os.path.join(self.staging, "REVIEW.md")
        H.write(review, H.read(review).replace("## Risks", "## Worries"))
        self.assertIn("review", rules(self.findings(), "error"))

    def test_review_status_must_match_manifest(self):
        self.edit_manifest(status="blocked")
        self.assertIn("review-status", rules(self.findings(), "error"))

    def test_approved_candidate_with_matching_digest_passes(self):
        H.approve(self.staging, VP)
        self.assertEqual(self.findings(), [])

    def test_change_after_approval_invalidates_digest(self):
        H.approve(self.staging, VP)
        H.write(self.skill_md, H.read(self.skill_md) + "\nOne more line.\n")
        self.assertIn("digest-mismatch", rules(self.findings(), "error"))

    def test_approved_status_requires_user_approval_flag(self):
        manifest = H.approve(self.staging, VP)
        manifest["approval"]["approved_by_user"] = False
        H.write_json(self.manifest_path, manifest)
        self.assertIn("approval", rules(self.findings(), "error"))

    def test_approval_flag_without_approved_status_is_inconsistent(self):
        manifest = H.read_json(self.manifest_path)
        manifest["approval"]["approved_by_user"] = True
        H.write_json(self.manifest_path, manifest)
        self.assertIn("approval", rules(self.findings(), "error"))

    def test_passing_validation_never_sets_approval(self):
        self.assertEqual(self.findings(), [])
        run_cli(self.staging)
        manifest = H.read_json(self.manifest_path)
        self.assertEqual(manifest["status"], "draft")
        self.assertFalse(manifest["approval"]["approved_by_user"])

    def test_digest_is_stable_and_content_sensitive(self):
        first = VP.compute_digest(self.skill)
        self.assertRegex(first, r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(VP.compute_digest(self.skill), first)
        cli = run_cli(self.staging, "--digest")
        self.assertEqual(cli.stdout.strip(), first)
        H.write(self.skill_md, H.read(self.skill_md) + " ")
        self.assertNotEqual(VP.compute_digest(self.skill), first)


class CliTests(TempStagingCase):
    def test_exit_codes(self):
        self.assertEqual(run_cli(self.staging).returncode, 0)
        os.remove(self.skill_md)
        self.assertEqual(run_cli(self.staging).returncode, 1)
        self.assertEqual(run_cli(os.path.join(self.tmp, "missing")).returncode, 2)

    def test_json_output(self):
        data = json.loads(run_cli(self.staging, "--json").stdout)
        self.assertEqual(data["summary"], {"errors": 0, "warnings": 0})
        self.assertEqual(data["kind"], "staging")
        self.assertEqual(data["digest"], VP.compute_digest(self.skill))


if __name__ == "__main__":
    unittest.main()
