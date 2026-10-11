"""Functional tests for scripts/check_mermaid.py (run from the skill folder)."""

import importlib.util
import os
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "check_mermaid.py")
SPEC = importlib.util.spec_from_file_location("check_mermaid", SCRIPT)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)

FENCE = "```"


def doc(body):
    return "# Doc\n\n%smermaid\n%s\n%s\n" % (FENCE, body, FENCE)


class CheckMermaidTests(unittest.TestCase):
    def test_valid_flowchart_passes(self):
        self.assertEqual(CHECK.check(doc("flowchart LR\n  a[Start] --> b(End)")), [])

    def test_unknown_type_is_reported(self):
        self.assertEqual(CHECK.check(doc("flowchat LR\n  a --> b")),
                         ["block 1: unknown diagram type 'flowchat'"])

    def test_unbalanced_brackets_are_reported(self):
        self.assertEqual(CHECK.check(doc("flowchart LR\n  a[Start --> b")),
                         ["block 1: unbalanced brackets"])

    def test_text_without_blocks_passes(self):
        self.assertEqual(CHECK.check("no diagrams here"), [])


if __name__ == "__main__":
    unittest.main()
