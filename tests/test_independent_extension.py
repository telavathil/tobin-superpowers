"""Regression tests: tobin-superpowers is an independent extension, not a fork.

Official obra/superpowers provides every original workflow; this plugin ships
only its own skills, hooks, and scripts.

Run: python3 -m unittest discover -s tests -v
"""

import ast
import json
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")
THIS_FILE = os.path.abspath(__file__)

EXTENSION_SKILLS = {"hybrid-planning", "html-companion"}

# Skills shipped by official superpowers (7.0.0 plus names used by earlier
# releases). None of them may be copied into this plugin.
UPSTREAM_SKILLS = {
    "brainstorming", "diagnosing-superpowers", "dispatching-parallel-agents",
    "executing-plans", "finishing-a-development-branch", "receiving-code-review",
    "requesting-code-review", "subagent-driven-development", "systematic-debugging",
    "test-driven-development", "using-git-worktrees", "using-superpowers",
    "verification-before-completion", "writing-plans", "writing-skills",
}

REMOVED_PATHS = ("skills/brainstorming", "skills/writing-plans",
                 "skills/requesting-code-review", "skills/subagent-driven-development")

TEXT_SUFFIXES = (".md", ".py", ".json", ".html", ".sh", ".txt")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def repo_text_files():
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for name in files:
            path = os.path.join(root, name)
            if name.endswith(TEXT_SUFFIXES) and os.path.abspath(path) != THIS_FILE:
                yield path


def skill_dirs():
    return {d for d in os.listdir(SKILLS_DIR)
            if os.path.isfile(os.path.join(SKILLS_DIR, d, "SKILL.md"))}


class NoCopiedUpstreamSkillsTests(unittest.TestCase):
    def test_no_upstream_skill_directories(self):
        present = UPSTREAM_SKILLS.intersection(os.listdir(SKILLS_DIR))
        self.assertEqual(present, set(), "copied upstream skills: %s" % sorted(present))

    def test_only_extension_skills_are_discoverable(self):
        self.assertEqual(skill_dirs(), EXTENSION_SKILLS)

    def test_no_skill_name_shadows_upstream(self):
        for skill in skill_dirs():
            text = read(os.path.join(SKILLS_DIR, skill, "SKILL.md"))
            name = re.search(r"^name:\s*(\S+)", text, re.M).group(1)
            with self.subTest(skill=skill):
                self.assertNotIn(name, UPSTREAM_SKILLS)
                self.assertEqual(name, skill)

    def test_skills_dir_contents(self):
        self.assertEqual(set(os.listdir(SKILLS_DIR)), EXTENSION_SKILLS | {"shared"})
        self.assertEqual(os.listdir(os.path.join(SKILLS_DIR, "shared")), ["html-companion-guide.md"])


class NoStaleReferencesTests(unittest.TestCase):
    def test_no_references_to_removed_skill_paths(self):
        for path in repo_text_files():
            text = read(path)
            for removed in REMOVED_PATHS:
                with self.subTest(path=os.path.relpath(path, REPO_ROOT), removed=removed):
                    self.assertNotIn(removed + "/", text)

    def test_tobin_skill_references_exist(self):
        for path in repo_text_files():
            for name in re.findall(r"tobin-superpowers:([a-z][\w-]*)", read(path)):
                with self.subTest(path=os.path.relpath(path, REPO_ROOT), name=name):
                    self.assertIn(name, EXTENSION_SKILLS)

    def test_superpowers_skill_references_are_official(self):
        for path in repo_text_files():
            for name in re.findall(r"(?<![\w-])superpowers:([a-z][\w-]*)", read(path)):
                with self.subTest(path=os.path.relpath(path, REPO_ROOT), name=name):
                    self.assertIn(name, UPSTREAM_SKILLS)

    def test_no_fork_merge_procedure_in_docs(self):
        for doc in ("README.md", "MAINTAINING.md"):
            text = read(os.path.join(REPO_ROOT, doc))
            with self.subTest(doc=doc):
                self.assertNotIn("html-companion:start", text)
                self.assertNotRegex(text, r"(?i)personal fork|forked skill|fenced block|merge (updates|changes) from upstream")


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.plugin = json.loads(read(os.path.join(REPO_ROOT, ".claude-plugin", "plugin.json")))
        self.marketplace = json.loads(read(os.path.join(REPO_ROOT, ".claude-plugin", "marketplace.json")))
        self.entry = self.marketplace["plugins"][0]

    def test_versions_agree_at_1_0_2(self):
        self.assertEqual(self.plugin["version"], "1.0.2")
        self.assertEqual(self.entry["version"], self.plugin["version"])
        self.assertEqual(self.entry["name"], self.plugin["name"])
        self.assertEqual(self.plugin["name"], "tobin-superpowers")
        self.assertEqual(self.marketplace["name"], "tobin-superpowers-dev")
        self.assertEqual(self.entry["source"], "./")

    def test_descriptions_describe_independent_extension(self):
        for label, text in (("plugin", self.plugin["description"]),
                            ("entry", self.entry["description"]),
                            ("marketplace", self.marketplace["description"])):
            with self.subTest(label=label):
                self.assertNotRegex(text.lower(), r"\bfork")
                self.assertIn("superpowers", text.lower())
        self.assertIn("extension", self.plugin["description"].lower())
        self.assertEqual(self.entry["description"], self.plugin["description"])

    def test_keywords_have_no_fork(self):
        self.assertNotIn("fork", [k.lower() for k in self.plugin.get("keywords", [])])


class HookAndScriptTests(unittest.TestCase):
    def test_hook_script_paths_resolve(self):
        config = json.loads(read(os.path.join(REPO_ROOT, "hooks", "hooks.json")))["hooks"]
        args = [a for groups in config.values() for g in groups for h in g["hooks"] for a in h.get("args", [])]
        self.assertTrue(args)
        for arg in args:
            with self.subTest(arg=arg):
                self.assertTrue(arg.startswith("${CLAUDE_PLUGIN_ROOT}/"))
                self.assertTrue(os.path.isfile(arg.replace("${CLAUDE_PLUGIN_ROOT}", REPO_ROOT)))

    def test_scripts_use_standard_library_only(self):
        stdlib = set(sys.stdlib_module_names)
        scripts = os.path.join(REPO_ROOT, "scripts")
        for name in sorted(os.listdir(scripts)):
            if not name.endswith(".py"):
                continue
            tree = ast.parse(read(os.path.join(scripts, name)))
            modules = {alias.name.split(".")[0] for node in ast.walk(tree)
                       if isinstance(node, ast.Import) for alias in node.names}
            modules |= {node.module.split(".")[0] for node in ast.walk(tree)
                        if isinstance(node, ast.ImportFrom) and node.module}
            with self.subTest(script=name):
                self.assertEqual(modules - stdlib, set())


if __name__ == "__main__":
    unittest.main()
