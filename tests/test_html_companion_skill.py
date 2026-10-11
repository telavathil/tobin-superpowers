"""Contract tests for the standalone skills/html-companion skill.

The skill is self-contained: everything Claude needs is in SKILL.md, because
the Skill tool delivers a skill's own text without a Read permission while
other plugin files are unreadable in headless runs (seen in Phase 3
integration testing).

Run: python3 -m unittest discover -s tests -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")
SKILL_DIR = os.path.join(SKILLS_DIR, "html-companion")
SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")
GUIDE = os.path.join(SKILLS_DIR, "shared", "html-companion-guide.md")

# Official superpowers workflow -> (section title, exact offer question,
# rendering-priority bullet leads). The questions and leads were migrated from
# the former copied skills in Phase 3 and are pinned here so they cannot be
# lost or silently reworded.
ARTIFACTS = {
    "superpowers:brainstorming": (
        "Design Spec",
        "Would you like an HTML companion for this design spec to share with your team? (yes/no)",
        ["Decisions summary at the top.", "Section navigation.",
         "Approach comparison (if the spec contains multiple approaches).",
         "Open questions, callouts.", "Body sections", "Footer."],
    ),
    "superpowers:writing-plans": (
        "Implementation Plan",
        "Would you like an HTML companion for this implementation plan to share with your team? (yes/no)",
        ["Plan summary header.", "Phase or subsystem grouping.",
         "Tasks as a structured checklist.", "Risk and dependency callouts.",
         "Body content", "Footer."],
    ),
    "superpowers:requesting-code-review": (
        "Code Review Report",
        "Would you like an HTML companion for this code review report to share with your team? (yes/no)",
        ["Summary bar at the top.", "Jump links.", "Findings as severity-coded rows.",
         "Annotated diff (if available).", "Assessment at the bottom.", "Footer."],
    ),
    "superpowers:subagent-driven-development": (
        "Run Summary",
        "Would you like an HTML companion for this subagent run summary to share as an async team update? (yes/no)",
        ["Status summary at the top.", "Concerns and blocked tasks first.",
         "Source plan reference.", "Full task list.", "Final reviewer assessment.", "Footer."],
    ),
}


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def flat(text):
    """Unwrap blockquote continuation lines and collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"\n> ?", " ", text))


def skill_section(title):
    """Text of '## Companion: <title>' in SKILL.md, up to the next '## '."""
    text = read(SKILL_MD)
    marker = "\n## Companion: %s\n" % title
    if marker not in text:
        return ""
    return text.split(marker, 1)[1].split("\n## ", 1)[0]


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL_MD)
        self.frontmatter = self.text.split("---\n")[1]

    def test_frontmatter(self):
        self.assertTrue(self.text.startswith("---\n"))
        self.assertIn("name: html-companion\n", self.frontmatter)
        description = re.search(r"^description: (.+)$", self.frontmatter, re.M).group(1)
        for phrase in ("HTML companion", "design spec", "implementation plan",
                       "code review report", "run summary", "only if the user says yes"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, description)

    def test_no_allowed_tools(self):
        # A skill that pre-approves tools needs a permission prompt to load,
        # which is denied in non-interactive runs (Phase 3 integration test).
        self.assertNotIn("allowed-tools", self.frontmatter)

    def test_skill_is_single_file(self):
        self.assertEqual(os.listdir(SKILL_DIR), ["SKILL.md"])

    def test_does_not_depend_on_reading_other_plugin_files(self):
        self.assertNotIn("references/", self.text)
        self.assertNotIn("Read `${CLAUDE_PLUGIN_ROOT}", self.text)

    def test_skill_size_bounded(self):
        # Above the docs' ~500-line tip because the shared guide is embedded;
        # it is only loaded after the user says yes.
        self.assertLess(len(self.text.splitlines()), 600)


class OfferAndConsentTests(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL_MD)

    def test_timing_table_names_each_official_workflow(self):
        table = self.text.split("## When to Offer", 1)[1].split("\n## ", 1)[0]
        for workflow, (title, _, _) in ARTIFACTS.items():
            short = workflow.split(":", 1)[1]
            with self.subTest(workflow=workflow):
                row = next(l for l in table.splitlines() if "`%s`" % short in l)
                self.assertIn("Companion: %s" % title, row)
        for timing in ("after the user approves the written spec",
                       "after the plan's self-review is clean, before the execution handoff",
                       "Critical/Important issues are fixed or deferred",
                       "once, after the final review approves",
                       "asking to continue to the next step (\"write the plan\", \"go ahead\", \"next\") counts as approval"):
            with self.subTest(timing=timing):
                self.assertIn(timing, table)

    def test_implicit_spec_approval_in_section(self):
        section = skill_section("Design Spec").split("### The Offer", 1)[0]
        self.assertIn("asking to continue to the next step (\"write the plan\", \"go ahead\", \"next\") counts as approval", section)
        self.assertIn("ask the offer question as its own short message first", section)
        self.assertIn("wait for the answer; do not start writing-plans in the same turn", section)

    def test_deferral_and_run_completion_handoffs(self):
        table = self.text.split("## When to Offer", 1)[1].split("\n## ", 1)[0]
        self.assertIn("the user deferring them counts", table)
        self.assertIn("when you report the run complete, even if the branch-finishing step is skipped", table)
        review = skill_section("Code Review Report").split("### The Offer", 1)[0]
        self.assertIn("If the user defers the findings, offer right after acknowledging the deferral.", review)
        run = skill_section("Run Summary").split("### The Offer", 1)[0]
        self.assertIn("If the workflow reports the run complete without invoking "
                      "`superpowers:finishing-a-development-branch`, offer in that same message.", run)

    def test_consent_rules(self):
        for phrase in (
            "Ask once per artifact",
            "as its own short message",
            "Would you like an HTML companion for this <artifact> to share with your team? (yes/no)",
            "Only generate after an explicit yes",
            "Silence, \"maybe\", or a non-interactive",
            "If the user says no",
            "do not ask a second time",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_no_fork_terminology(self):
        self.assertNotRegex(self.text.lower(), r"\bfork(ed)?\b")


class ArtifactSectionTests(unittest.TestCase):
    def test_each_section_has_offer_question_and_priorities(self):
        for workflow, (title, question, leads) in ARTIFACTS.items():
            section = skill_section(title)
            with self.subTest(workflow=workflow):
                self.assertTrue(section.strip(), title)
                self.assertIn(question, flat(section))
                self.assertIn("### When to Offer", section)
                self.assertIn("### Rendering Priorities for", section)
            for lead in leads:
                with self.subTest(workflow=workflow, lead=lead):
                    self.assertIn("- **%s**" % lead, section)

    def test_each_section_names_its_official_workflow(self):
        for workflow, (title, _, _) in ARTIFACTS.items():
            with self.subTest(workflow=workflow):
                self.assertIn("`%s`" % workflow, skill_section(title))

    def test_persistence_paths_for_unsaved_artifacts(self):
        self.assertIn("docs/superpowers/reviews/YYYY-MM-DD-<feature-or-task-slug>-review.md",
                      skill_section("Code Review Report"))
        self.assertIn("docs/superpowers/run-summaries/YYYY-MM-DD-<feature-or-plan-slug>-summary.md",
                      skill_section("Run Summary"))

    def test_source_paths_for_saved_artifacts(self):
        self.assertIn("docs/superpowers/specs/", skill_section("Design Spec"))
        self.assertIn("docs/superpowers/plans/", skill_section("Implementation Plan"))


class OutputRuleTests(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL_MD)
        self.on_yes = self.text.split("## On Yes", 1)[1].split("\n## ", 1)[0]

    def test_markdown_preserved_and_html_unstaged(self):
        for phrase in ("same base name", "same directory",
                       "Never modify the source Markdown",
                       "Never stage or commit the HTML", "no `git add`",
                       "Confirm both paths"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.on_yes)

    def test_self_contained_output_required(self):
        for phrase in ("self-contained", "no CDN", "web fonts", "`data:` URIs"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.on_yes)

    def test_validator_by_plugin_path_with_fallback(self):
        self.assertIn("python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate-html-companion.py"
                      " <file>.html --source <file>.md", self.on_yes)
        self.assertTrue(os.path.isfile(os.path.join(REPO_ROOT, "scripts", "validate-html-companion.py")))
        self.assertIn("If the validator cannot run", self.on_yes)


class SharedGuideTests(unittest.TestCase):
    def test_embeds_shared_guide_verbatim(self):
        guide_body = read(GUIDE).split("\n", 1)[1].strip()  # drop the guide's H1
        self.assertIn(guide_body, read(SKILL_MD))

    def test_guide_points_at_standalone_skill(self):
        guide = read(GUIDE)
        self.assertIn("html-companion", guide)
        self.assertNotRegex(guide.lower(), r"\bfork(ed)?\b")
        self.assertNotIn("Each skill's `SKILL.md` includes", guide)

    def test_guide_keeps_self_containment_and_palette(self):
        guide = read(GUIDE)
        for phrase in ("Self-contained.", "No web fonts", "Never modify the markdown",
                       "#82071e", "#1a7f37", "<!DOCTYPE html>", "companion-footer"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide)


if __name__ == "__main__":
    unittest.main()
