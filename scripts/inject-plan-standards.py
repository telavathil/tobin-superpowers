#!/usr/bin/env python3
"""PreToolUse hook for the Skill tool: inject code standards at plan time.

When a plan-writing skill is invoked, prints a PreToolUse hookSpecificOutput
object whose additionalContext holds the standards under standards/. Informs,
never blocks: always exits 0, and unparseable input or other skills produce no
output.

Claude Code moves any one hook's additionalContext over 10,000 characters to a
file and shows only a short preview, so hooks.json runs this script twice: the
argument "1" prints the header, index and first half of global/, and "2" prints
the rest plus the repo's lint state.
"""

import json
import os
import re
import subprocess
import sys

STANDARDS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "standards"
)
PLAN_SKILL = re.compile(r"(^|:)(writing-plans|plan)$")

HEADER = """\
# Agent OS code standards

Loaded automatically because a plan-writing skill was invoked. These are the
user's standing code standards and they apply in every repository.

Two obligations for the plan you are about to write:

1. Every code block in the plan must comply with these standards.
2. Copy the binding rules of every standard that applies, verbatim, into the
   plan's Global Constraints section. Implementers and reviewers see only the
   plan, never these files.

A project's own agent-os/standards/ adds to these; where they conflict, the
project's wins.

Source: %s
"""

LINT_CHECK = """\
## Lint baseline check (first plan in this repo)

No standards state is recorded for this repo yet. Before writing the plan, read
%s and follow it. Then write the repo's state
to %s in the format check.md gives.
"""

CONTINUED = """\
# Agent OS code standards (part 2 of 2)

The rest of the standards for this plan. The obligations in part 1 apply.
"""

REPO_STATE = "## This repo's recorded standards state\n\n"


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def build_context(skill, cwd, standards_dir, data_dir, part):
    if not PLAN_SKILL.search(skill) or not os.path.isdir(standards_dir):
        return None
    global_dir = os.path.join(standards_dir, "global")
    names = sorted(n for n in os.listdir(global_dir) if n.endswith(".md"))
    half = len(names) // 2
    if part == 1:
        parts = [HEADER % standards_dir]
        index = os.path.join(standards_dir, "index.yml")
        if os.path.isfile(index):
            parts.append("## index.yml\n\n" + read(index))
        names = names[:half]
    else:
        parts = [CONTINUED]
        names = names[half:]
    for name in names:
        parts.append("## global/%s\n\n%s" % (name, read(os.path.join(global_dir, name))))
    if part == 1:
        return "\n".join(parts)
    marker = marker_path(cwd, data_dir)
    if marker and os.path.exists(marker):
        try:
            parts.append(REPO_STATE + read(marker))
        except (OSError, ValueError):
            pass
    elif marker:
        check = os.path.join(os.path.dirname(standards_dir), "lint", "check.md")
        parts.append(LINT_CHECK % (check, marker))
    return "\n".join(parts)


def marker_path(cwd, data_dir):
    if not data_dir or not cwd:
        return None
    try:
        top = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if top.returncode != 0 or not top.stdout.strip():
        return None
    root = top.stdout.strip()
    if os.path.basename(root) == ".git":
        root = os.path.dirname(root)
    return os.path.join(data_dir, "repos", repo_key(root) + ".md")


def repo_key(toplevel):
    return re.sub(r"[/\\]", "-", re.sub(r"^([A-Za-z]:)?[/\\]", "", toplevel))


def main():
    try:
        payload = json.loads(sys.stdin.read())
        skill = payload["tool_input"]["skill"]
        context = build_context(
            skill,
            payload.get("cwd", ""),
            STANDARDS_DIR,
            os.environ.get("CLAUDE_PLUGIN_DATA"),
            2 if sys.argv[1:] == ["2"] else 1,
        )
    except (OSError, ValueError, KeyError, TypeError):
        return 0
    if context:
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": context,
        }}, sys.stdout)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
