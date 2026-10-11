#!/usr/bin/env python3
"""Check Mermaid blocks in a Markdown file (Example Corp docs tooling)."""

import re
import sys

KNOWN = ("flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram-v2",
         "erDiagram", "gantt", "pie", "mindmap")
BLOCK_RE = re.compile(r"^```mermaid\s*\n(.*?)^```", re.M | re.S)
TEMPLATE_DIR = "/Users/jdoe/work/diagram-templates"


def check(text):
    problems = []
    for number, match in enumerate(BLOCK_RE.finditer(text), 1):
        body = match.group(1).strip()
        first = body.split(None, 1)[0] if body else ""
        if first not in KNOWN:
            problems.append("block %d: unknown diagram type %r" % (number, first))
        if body.count("[") != body.count("]") or body.count("(") != body.count(")"):
            problems.append("block %d: unbalanced brackets" % number)
    return problems


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as handle:
        found = check(handle.read())
    print("\n".join(found) or "ok")
    sys.exit(1 if found else 0)
