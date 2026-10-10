"""Contract tests for skills/html-companion and the forked skills it replaces.

Run: python3 -m unittest discover -s tests -v
"""

import hashlib
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(REPO_ROOT, "skills", "html-companion")
SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")
GUIDE = os.path.join(REPO_ROOT, "skills", "shared", "html-companion-guide.md")
FENCE_RE = re.compile(
    r"<!-- tobin-superpowers:html-companion:start -->.*?<!-- tobin-superpowers:html-companion:end -->",
    re.S)

# Forked skill -> SKILL.md section holding its migrated rendering priorities.
# Everything lives in SKILL.md: the Skill tool delivers it without a Read
# permission, while separate plugin files are unreadable in headless runs
# (seen in the Phase 3 integration test).
ARTIFACTS = {
    "brainstorming": "Design Spec",
    "writing-plans": "Implementation Plan",
    "requesting-code-review": "Code Review Report",
    "subagent-driven-development": "Run Summary",
}

# SHA-256 of the fork-owned fenced blocks and the shared guide at the start of
# Phase 3. Phase 3 must not change them; Phase 4 retires the forks deliberately.
FORK_BLOCK_SHA = {
    "brainstorming": "84b04d2a86087132feac55e17e6eeb24f86bd102a31b2aa15be2f47ef1041a84",
    "writing-plans": "8d0705fcbf7fede8c07ff4da641869f6e6e01b5943424fcadcb51f15bf3fbfe9",
    "requesting-code-review": "b4ff8945b6d11e38ec4f21724b893330b204f59b620c4e96c80f69726da6f5e2",
    "subagent-driven-development": "907a7d4d8b2b1c6356bbd4b9c102e8b192bc47706f93799c8417e07fe50a2ca8",
}
GUIDE_SHA = "ad87f0144b295ff69ade00319515d00b09b2c3a4722c4df2cab68d6bb887b47d"


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def fork_blocks(skill):
    return FENCE_RE.findall(read(os.path.join(REPO_ROOT, "skills", skill, "SKILL.md")))


def fork_block_sha(skill):
    return hashlib.sha256("\n".join(fork_blocks(skill)).encode("utf-8")).hexdigest()


def skill_section(title):
    """Text of '## Companion: <title>' in SKILL.md, up to the next '## '."""
    text = read(SKILL_MD)
    marker = "\n## Companion: %s\n" % title
    if marker not in text:
        return ""
    return text.split(marker, 1)[1].split("\n## ", 1)[0]


def priority_leads(skill):
    """Bold lead phrases of the fork's 'Rendering Priorities' bullets."""
    block = fork_blocks(skill)[-1]
    section = block.split("### Rendering Priorities", 1)[1].split("\n### ", 1)[0]
    return re.findall(r"^- \*\*(.+?)\*\*", section, re.M)


class SkillContractTests(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL_MD)
        self.frontmatter = self.text.split("---\n")[1]

    def test_frontmatter(self):
        self.assertTrue(self.text.startswith("---\n"))
        self.assertIn("name: html-companion\n", self.frontmatter)
        self.assertRegex(self.frontmatter, r"description: .*HTML companion")
        # No allowed-tools: a skill that pre-approves tools needs a permission
        # prompt to load, which is denied in non-interactive runs (seen in the
        # Phase 3 integration test). The validator runs as a normal Bash call.
        self.assertNotIn("allowed-tools", self.frontmatter)

    def test_offer_and_consent_rules(self):
        for phrase in (
            "Would you like an HTML companion for this",
            "(yes/no)",
            "Ask once per artifact",
            "Only generate after an explicit yes",
            "If the user says no",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_output_rules(self):
        for phrase in (
            "same base name",
            "Never stage or commit the HTML",
            "Never modify the source Markdown",
            "Confirm both paths",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_validator_by_plugin_path_with_fallback(self):
        self.assertIn("python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate-html-companion.py", self.text)
        self.assertIn("--source", self.text)
        self.assertIn("If the validator cannot run", self.text)

    def test_does_not_depend_on_reading_other_plugin_files(self):
        self.assertNotIn("references/", self.text)
        self.assertNotIn("Read `${CLAUDE_PLUGIN_ROOT}", self.text)

    def test_embeds_shared_guide_verbatim(self):
        guide_body = read(GUIDE).split("\n", 1)[1].strip()  # drop the guide's H1
        self.assertIn(guide_body, self.text)

    def test_all_artifacts_and_triggers_listed(self):
        for phrase in ("design spec", "implementation plan", "code review report", "run summary",
                       "docs/superpowers/reviews/", "docs/superpowers/run-summaries/"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_section_per_artifact(self):
        for title in ARTIFACTS.values():
            with self.subTest(title=title):
                self.assertTrue(skill_section(title).strip(), title)

    def test_no_supporting_files(self):
        self.assertEqual(os.listdir(SKILL_DIR), ["SKILL.md"])

    def test_skill_size_bounded(self):
        # Above the docs' ~500-line tip because the shared guide is embedded
        # (see ARTIFACTS note); it is only loaded after the user says yes.
        self.assertLess(len(self.text.splitlines()), 600)


class MigrationTests(unittest.TestCase):
    def test_every_fork_priority_is_migrated(self):
        for skill, title in ARTIFACTS.items():
            leads = priority_leads(skill)
            self.assertGreaterEqual(len(leads), 5, skill)
            text = skill_section(title)
            for lead in leads:
                with self.subTest(skill=skill, lead=lead):
                    self.assertIn("**%s**" % lead, text)

    def test_fork_offer_wording_migrated(self):
        def flat(text):  # unwrap blockquote continuation lines and whitespace
            return re.sub(r"\s+", " ", re.sub(r"\n> ?", " ", text))

        for skill, title in ARTIFACTS.items():
            offer = re.search(r'"(Would you like an HTML companion for this .+?\(yes/no\))"',
                              flat(fork_blocks(skill)[-1])).group(1)
            with self.subTest(skill=skill):
                self.assertIn(offer, flat(skill_section(title)))

    def test_persistence_paths_migrated(self):
        self.assertIn("docs/superpowers/reviews/YYYY-MM-DD-<feature-or-task-slug>-review.md",
                      skill_section("Code Review Report"))
        self.assertIn("docs/superpowers/run-summaries/YYYY-MM-DD-<feature-or-plan-slug>-summary.md",
                      skill_section("Run Summary"))


class ForkPreservationTests(unittest.TestCase):
    def test_fork_blocks_unchanged(self):
        for skill, expected in FORK_BLOCK_SHA.items():
            with self.subTest(skill=skill):
                self.assertTrue(fork_blocks(skill), skill)
                self.assertEqual(fork_block_sha(skill), expected)

    def test_shared_guide_unchanged(self):
        with open(GUIDE, "rb") as f:
            self.assertEqual(hashlib.sha256(f.read()).hexdigest(), GUIDE_SHA)


if __name__ == "__main__":
    unittest.main()
