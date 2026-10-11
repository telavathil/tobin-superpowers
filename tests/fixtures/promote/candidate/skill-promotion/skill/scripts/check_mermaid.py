#!/usr/bin/env python3
"""Check Mermaid blocks in a Markdown file.

Usage: python3 check_mermaid.py FILE.md
Exit codes: 0 every block passed, 1 problems found, 2 unreadable input.
"""

import re
import sys

KNOWN = ("flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram-v2",
         "erDiagram", "gantt", "pie", "mindmap")
BLOCK_RE = re.compile(r"^```mermaid\s*\n(.*?)^```", re.M | re.S)


def check(text):
    """Return a list of problems, one string per finding."""
    problems = []
    for number, match in enumerate(BLOCK_RE.finditer(text), 1):
        body = match.group(1).strip()
        first = body.split(None, 1)[0] if body else ""
        if first not in KNOWN:
            problems.append("block %d: unknown diagram type %r" % (number, first))
        if body.count("[") != body.count("]") or body.count("(") != body.count(")"):
            problems.append("block %d: unbalanced brackets" % number)
    return problems


def main(argv):
    if len(argv) != 1:
        print("usage: check_mermaid.py FILE.md", file=sys.stderr)
        return 2
    try:
        with open(argv[0], encoding="utf-8") as handle:
            found = check(handle.read())
    except OSError as exc:
        print("check_mermaid: %s" % exc, file=sys.stderr)
        return 2
    print("\n".join(found) or "ok")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
